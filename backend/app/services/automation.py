"""Transactional PostgreSQL outbox; legacy in-process API kept for integrations.

Production routes use enqueue/process_job, never the legacy global event bus.
Handlers only perform local database work in the caller's transaction.
"""
import time
from datetime import timedelta
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, ValidationError
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.observability import record_event, request_id_context
from app.models import Activity, AutomationJob, Project, Quote, Subscription, Tenant, User
from app.models.tenant import utc_now_naive


from collections import deque
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Callable


@dataclass(frozen=True)
class AutomationEvent:
    name: str
    payload: dict
    created_at: datetime


@dataclass(frozen=True)
class AutomationAction:
    name: str
    handler: Callable[[AutomationEvent], None]


class AutomationEngine:
    def __init__(self) -> None:
        self._actions: dict[str, list[AutomationAction]] = {}
        self._results: deque[dict] = deque(maxlen=100)

    def register(self, event_name: str, action: AutomationAction) -> None:
        self._actions.setdefault(event_name, []).append(action)

    def emit(self, event_name: str, payload: dict | None = None) -> AutomationEvent:
        event = AutomationEvent(
            name=event_name,
            payload=payload or {},
            created_at=datetime.now(timezone.utc),
        )
        for action in self._actions.get(event_name, []):
            action.handler(event)
        return event

    @property
    def results(self) -> list[dict]:
        return list(self._results)

    def record_result(self, event: AutomationEvent, action: str, result: dict) -> None:
        self._results.append({
            "event": event.name,
            "action": action,
            "created_at": event.created_at.isoformat(),
            "result": result,
        })


engine = AutomationEngine()


def _prepare_quote_analysis(event: AutomationEvent) -> None:
    from app.services.quote_ai import analyze_quote

    payload = event.payload
    analysis = analyze_quote(
        base_cost=payload["base_cost"],
        suggested_total=payload["suggested_total"],
        profit_margin=payload["profit_margin"],
        use_provider=False,
    )
    engine.record_result(event, "analyze_quote", analysis)


def register_default_automations() -> None:
    """Register safe foundation automations exactly once."""
    if engine._actions:
        return

    engine.register(
        "user.created",
        AutomationAction(name="audit_user_created", handler=lambda event: None),
    )
    engine.register(
        "quote.created",
        AutomationAction(name="prepare_quote_analysis", handler=_prepare_quote_analysis),
    )


register_default_automations()


# Persistent engine. Payloads contain identifiers only, except the allowlisted
# subscription snapshot received through a verified Stripe signature.


class DomainPayload(BaseModel):
    model_config = ConfigDict(extra="forbid")
    entity_id: int = Field(gt=0)
    user_id: int | None = Field(default=None, gt=0)
    activity_id: int | None = Field(default=None, gt=0)


class SubscriptionPayload(BaseModel):
    model_config = ConfigDict(extra="forbid")
    subscription_id: str = Field(min_length=1, max_length=180)
    customer_id: str = Field(min_length=1, max_length=180)
    plan_code: Literal["starter", "professional", "business"]
    status: Literal["incomplete", "incomplete_expired", "trialing", "active", "past_due", "canceled", "unpaid", "paused"]
    event_created: int = Field(ge=0)
    current_period_end: datetime | None = None
    trial_end: datetime | None = None
    cancel_at_period_end: bool = False


class PermanentAutomationError(ValueError):
    pass


def _scope(db: Session, tenant_id: int) -> None:
    if not tenant_id or db.info.get("tenant_id") != tenant_id:
        raise PermanentAutomationError("tenant_scope")


def _insert(db: Session):
    if db.get_bind().dialect.name == "postgresql":
        from sqlalchemy.dialects.postgresql import insert
    else:
        from sqlalchemy.dialects.sqlite import insert
    return insert


def enqueue(db: Session, *, tenant_id: int, event_type: str, payload: dict,
            idempotency_key: str, available_at: datetime | None = None,
            max_attempts: int = 5) -> AutomationJob:
    _scope(db, tenant_id)
    if event_type not in HANDLERS or not 1 <= len(idempotency_key) <= 180 or not 1 <= max_attempts <= 20:
        raise PermanentAutomationError("invalid_event")
    schema = SubscriptionPayload if event_type == "subscription.changed" else DomainPayload
    clean = schema.model_validate(payload).model_dump(mode="json")
    if clean.get("user_id"):
        user = db.scalar(select(User).where(User.id == clean["user_id"], User.tenant_id == tenant_id))
        if user is None:
            raise PermanentAutomationError("tenant_reference")
    db.flush()
    db.execute(_insert(db)(AutomationJob).values(
        tenant_id=tenant_id, event_type=event_type, payload=clean,
        idempotency_key=idempotency_key, available_at=available_at or utc_now_naive(),
        request_id=request_id_context.get(), max_attempts=max_attempts,
    ).on_conflict_do_nothing(index_elements=["tenant_id", "idempotency_key"]))
    job = db.scalar(select(AutomationJob).where(
        AutomationJob.tenant_id == tenant_id, AutomationJob.idempotency_key == idempotency_key,
    ).with_for_update())
    if job.event_type != event_type or job.payload != clean:
        raise PermanentAutomationError("idempotency_conflict")
    return job


def _activity(db: Session, job: AutomationJob, *, action: str, entity: str,
              entity_id: int, description: str, user_id: int | None = None,
              effect_key: str | None = None) -> None:
    db.execute(_insert(db)(Activity).values(
        tenant_id=job.tenant_id, user_id=user_id, action=action, entity=entity,
        entity_id=entity_id, description=description, idempotency_key=effect_key or job.idempotency_key,
    ).on_conflict_do_nothing(index_elements=["tenant_id", "idempotency_key"]))


def _quote_accepted(db: Session, job: AutomationJob) -> None:
    payload = DomainPayload.model_validate(job.payload)
    quote = db.scalar(select(Quote).where(Quote.id == payload.entity_id, Quote.tenant_id == job.tenant_id).with_for_update())
    if quote is None or quote.status != "accepted":
        raise PermanentAutomationError("invalid_quote")
    project = db.scalar(select(Project).where(Project.quote_id == quote.id, Project.tenant_id == job.tenant_id))
    if project is None:
        project = Project(tenant_id=job.tenant_id, customer_id=quote.customer_id, quote_id=quote.id,
                          name=f"Projeto do orçamento #{quote.id}", description=quote.description,
                          measurements=quote.measurements, materials=quote.materials, status="planning")
        db.add(project)
        db.flush()
    _activity(db, job, action="created_from_quote", entity="project", entity_id=project.id,
              effect_key=f"project.from_quote:{quote.id}",
              user_id=payload.user_id,
              description=f"Criou automaticamente o projeto #{project.id} a partir do quote #{quote.id} aceito pelo cliente")


def _tenant_created(db: Session, job: AutomationJob) -> None:
    from app.services.plans import TRIAL_DAYS

    payload = DomainPayload.model_validate(job.payload)
    if payload.entity_id != job.tenant_id:
        raise PermanentAutomationError("tenant_reference")
    tenant = db.get(Tenant, job.tenant_id)
    subscription = db.scalar(select(Subscription).where(Subscription.tenant_id == job.tenant_id))
    if subscription is None:
        subscription = Subscription(tenant_id=tenant.id, provider="manual", plan_code=tenant.plan_code,
                                    status="trialing", trial_end=tenant.created_at + timedelta(days=TRIAL_DAYS))
        db.add(subscription)
        db.flush()
    if subscription.status == "trialing" and subscription.trial_end:
        schedule_trial(db, subscription)
    _activity(db, job, action="onboarding_started", entity="tenant", entity_id=tenant.id,
              user_id=payload.user_id, description="Onboarding iniciado com teste grátis de 30 dias")


def schedule_trial(db: Session, subscription: Subscription) -> AutomationJob:
    return enqueue(db, tenant_id=subscription.tenant_id, event_type="trial.expired",
                   payload={"entity_id": subscription.id},
                   idempotency_key=f"trial:{subscription.id}:{subscription.trial_end.isoformat()}",
                   available_at=subscription.trial_end)


def _trial_expired(db: Session, job: AutomationJob) -> None:
    payload = DomainPayload.model_validate(job.payload)
    subscription = db.scalar(select(Subscription).where(
        Subscription.id == payload.entity_id, Subscription.tenant_id == job.tenant_id,
    ).with_for_update())
    if subscription is None:
        raise PermanentAutomationError("invalid_subscription")
    if subscription.status != "trialing":
        return
    if subscription.trial_end and subscription.trial_end > utc_now_naive():
        schedule_trial(db, subscription)
        return
    subscription.status = "trial_expired"
    _activity(db, job, action="trial_expired", entity="tenant", entity_id=job.tenant_id,
              description="Teste grátis encerrado; cobrança permanece acessível")


def _subscription_changed(db: Session, job: AutomationJob) -> None:
    data = SubscriptionPayload.model_validate(job.payload)
    subscription = db.scalar(select(Subscription).where(Subscription.tenant_id == job.tenant_id).with_for_update())
    if subscription is None:
        raise PermanentAutomationError("invalid_subscription")
    if subscription.provider_subscription_id and subscription.provider_subscription_id != data.subscription_id:
        # A second provider subscription must be reconciled, never overwrite billing silently.
        raise PermanentAutomationError("subscription_conflict")
    if subscription.provider_customer_id and subscription.provider_customer_id != data.customer_id:
        raise PermanentAutomationError("customer_conflict")
    if data.event_created < subscription.provider_event_created:
        return
    subscription.provider = "stripe"
    subscription.provider_subscription_id = data.subscription_id
    subscription.provider_customer_id = data.customer_id
    subscription.plan_code = data.plan_code
    subscription.status = data.status
    subscription.provider_event_created = data.event_created
    subscription.current_period_end = data.current_period_end
    subscription.trial_end = data.trial_end
    subscription.cancel_at_period_end = data.cancel_at_period_end
    db.get(Tenant, job.tenant_id).plan_code = data.plan_code
    if subscription.status == "trialing" and subscription.trial_end:
        schedule_trial(db, subscription)
    _activity(db, job, action="subscription_changed", entity="tenant", entity_id=job.tenant_id,
              description="Estado comercial da assinatura atualizado")


def _audit_committed_change(db: Session, job: AutomationJob) -> None:
    # Domain state + activity were persisted atomically by the HTTP transaction.
    # Never regenerate costs or financial snapshots here: profitability reads SUM.
    payload = DomainPayload.model_validate(job.payload)
    if payload.activity_id is not None:
        activity = db.scalar(select(Activity).where(Activity.id == payload.activity_id, Activity.tenant_id == job.tenant_id))
        if activity is None:
            raise PermanentAutomationError("invalid_activity")


HANDLERS = {
    "quote.accepted": _quote_accepted, "tenant.created": _tenant_created,
    "trial.expired": _trial_expired, "subscription.changed": _subscription_changed,
    **{name: _audit_committed_change for name in (
        "quote.created", "quote.updated", "quote.deleted", "quote.approved", "quote.rejected",
        "quote.shared", "quote.declined", "project.status_changed", "project.cost_added", "record.changed",
    )},
}


def process_job(db: Session, job: AutomationJob) -> bool:
    """Caller owns row lock and transaction; savepoint rolls back every failed effect."""
    _scope(db, job.tenant_id)
    db.flush()
    job = db.scalar(select(AutomationJob).where(AutomationJob.id == job.id).with_for_update().execution_options(populate_existing=True))
    if job.status in {"completed", "failed"} or job.available_at > utc_now_naive():
        return job.status == "completed"
    started = time.perf_counter()
    job.attempts += 1
    db.flush()
    try:
        with db.begin_nested():
            handler = HANDLERS.get(job.event_type)
            if handler is None:
                raise PermanentAutomationError("unknown_event")
            if job.event_type != "subscription.changed":
                payload = DomainPayload.model_validate(job.payload)
                if payload.user_id and db.scalar(select(User.id).where(User.id == payload.user_id, User.tenant_id == job.tenant_id)) is None:
                    raise PermanentAutomationError("tenant_reference")
            handler(db, job)
            db.flush()
    except Exception as exc:
        permanent = isinstance(exc, (PermanentAutomationError, ValidationError))
        job.status = "failed" if permanent or job.attempts >= job.max_attempts else "retry"
        job.last_error = "invalid_event" if permanent else "temporary_failure"
        job.available_at = utc_now_naive() + timedelta(seconds=min(3600, 5 * 2 ** (job.attempts - 1)))
    else:
        job.status = "completed"
        job.processed_at = utc_now_naive()
        job.last_error = None
    record_event("automation.processed", tenant_id=job.tenant_id, job_id=job.id,
                 event_type=job.event_type, attempts=job.attempts, result=job.status,
                 error_code=job.last_error, duration_ms=round((time.perf_counter() - started) * 1000),
                 request_id=job.request_id)
    return job.status == "completed"


def record_change(db: Session, *, tenant_id: int, event_type: str, entity_id: int,
                  user_id: int, activity: Activity | None = None) -> AutomationJob:
    db.flush()
    activity_id = activity.id if activity else None
    # Each activity is a persisted occurrence, not a hash of mutable customer data.
    key = f"{event_type}:{activity_id}" if activity else f"{event_type}:{entity_id}"
    return enqueue(db, tenant_id=tenant_id, event_type=event_type,
                   payload={"entity_id": entity_id, "user_id": user_id, "activity_id": activity_id},
                   idempotency_key=key)
