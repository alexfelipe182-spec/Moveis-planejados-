import hashlib
import hmac
import json
import secrets
from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import settings
from app.models import BillingWebhookEvent, Plan, Subscription


ACTIVE_STATUSES = {"trial", "active"}
VALID_STATUSES = ACTIVE_STATUSES | {"past_due", "canceled"}


def now_naive() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)


def subscription_allows_access(subscription: Subscription | None, *, now: datetime | None = None) -> bool:
    """Return whether an organization can continue using paid workspace features."""
    if subscription is None:
        # Existing installations may be between migrations; keep their data
        # readable until the subscription row is created by the migration.
        return True
    current = now or now_naive()
    if subscription.status not in ACTIVE_STATUSES:
        return False
    return not (subscription.status == "trial" and subscription.trial_end and subscription.trial_end <= current)


def webhook_digest(raw_body: bytes) -> str:
    return hashlib.sha256(raw_body).hexdigest()


def verify_webhook_signature(raw_body: bytes, signature: str | None) -> bool:
    secret = settings.billing_webhook_secret
    if not secret:
        return settings.billing_provider == "sandbox" and settings.environment != "production"
    if not signature:
        return False
    expected = hmac.new(secret.get_secret_value().encode(), raw_body, hashlib.sha256).hexdigest()
    supplied = signature.removeprefix("sha256=").strip()
    return hmac.compare_digest(expected, supplied)


def checkout_session(*, organization_id: int, plan: Plan) -> dict[str, str | int]:
    if settings.billing_provider == "disabled":
        raise RuntimeError("BILLING_PROVIDER_NOT_CONFIGURED")
    session_id = f"sandbox_{secrets.token_urlsafe(18)}"
    return {
        "provider": settings.billing_provider,
        "session_id": session_id,
        "plan_code": plan.code,
        "organization_id": organization_id,
        "mode": "test" if settings.billing_provider == "sandbox" else "live-configured",
    }


def apply_webhook(db: Session, *, provider: str, payload: dict, raw_body: bytes) -> tuple[bool, str]:
    event_id = str(payload.get("id") or "").strip()
    event_type = str(payload.get("type") or "").strip()
    if not event_id or not event_type:
        raise ValueError("Webhook sem id ou tipo")

    existing = db.scalar(select(BillingWebhookEvent).where(
        BillingWebhookEvent.provider == provider,
        BillingWebhookEvent.event_id == event_id,
    ))
    if existing:
        # The provider event id is idempotent, but it is not a license to
        # silently accept a different payload under the same id.
        if existing.payload_hash != webhook_digest(raw_body):
            raise ValueError("Webhook repetido com payload diferente")
        return False, existing.status

    event = BillingWebhookEvent(
        provider=provider,
        event_id=event_id,
        payload_hash=webhook_digest(raw_body),
        payload=json.dumps(payload, sort_keys=True, separators=(",", ":")),
        status="received",
    )
    db.add(event)
    db.flush()

    data = payload.get("data") if isinstance(payload.get("data"), dict) else {}
    organization_id = data.get("organization_id")
    parsed_organization_id = None
    if organization_id is not None:
        try:
            parsed_organization_id = int(organization_id)
        except (TypeError, ValueError) as exc:
            raise ValueError("organization_id inválido no webhook") from exc
    provider_subscription_id = data.get("subscription_id")
    subscription = None
    if provider_subscription_id:
        subscription = db.scalar(select(Subscription).where(
            Subscription.provider == provider,
            Subscription.provider_subscription_id == str(provider_subscription_id),
        ))
    if subscription is None and parsed_organization_id:
        subscription = db.scalar(select(Subscription).where(Subscription.organization_id == parsed_organization_id))
    if subscription is None:
        event.status = "ignored"
        event.processed_at = now_naive()
        db.commit()
        return True, event.status
    if parsed_organization_id is not None and subscription.organization_id != parsed_organization_id:
        raise ValueError("Webhook não corresponde à organização da assinatura")

    plan_code = data.get("plan_code")
    if plan_code:
        plan = db.scalar(select(Plan).where(Plan.code == str(plan_code), Plan.is_active.is_(True)))
        if not plan:
            raise ValueError("Plano inválido no webhook")
        subscription.plan_id = plan.id
    requested_status = str(data.get("status") or "").lower()
    if requested_status in VALID_STATUSES:
        subscription.status = requested_status
    if provider_subscription_id:
        subscription.provider_subscription_id = str(provider_subscription_id)
    subscription.updated_at = now_naive()
    event.status = "processed"
    event.processed_at = now_naive()
    db.commit()
    return True, event.status
