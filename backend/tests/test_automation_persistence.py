from concurrent.futures import ThreadPoolExecutor
from datetime import timedelta
from decimal import Decimal
from types import SimpleNamespace
from uuid import uuid4

import openai
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import delete, func, select, update

from app.core.security import create_access_token
from app.database import SessionLocal
from app.main import app
from app.models import Activity, AIUsage, AutomationJob, Customer, Material, Project, ProjectCost, Quote, Subscription, Tenant, UsageCounter, User
from app.models.tenant import utc_now_naive
from app.services.automation import HANDLERS, PermanentAutomationError, enqueue, process_job, schedule_trial
from app.services.plans import increment_usage, usage_quantity
from app.services.quote_brief import extract_quote_brief_result
from app.worker import run_once, schedule_due_trials


@pytest.fixture
def businesses():
    rows = []
    for _ in range(2):
        with SessionLocal() as db:
            tenant = Tenant(name="Automation test", slug=uuid4().hex)
            user = User(tenant=tenant, name="Owner", email=f"{uuid4().hex}@example.com", password_hash="test-only", is_admin=True)
            db.add(user)
            db.flush()
            customer = Customer(name="Cliente reservado")
            db.add_all([customer, Subscription(tenant_id=tenant.id, status="trialing", trial_end=utc_now_naive() + timedelta(days=30))])
            db.commit()
            rows.append(SimpleNamespace(tenant_id=tenant.id, user_id=user.id, customer_id=customer.id))
    return rows


def factory(business):
    return lambda **kwargs: SessionLocal(info={"tenant_id": business.tenant_id})


def client_for(business):
    return TestClient(app, headers={"Authorization": f"Bearer {create_access_token(str(business.user_id))}"})


def job_for(db, business, event="record.changed", *, key="test-event", entity_id=None, attempts=5):
    return enqueue(db, tenant_id=business.tenant_id, event_type=event,
                   payload={"entity_id": entity_id or business.customer_id}, idempotency_key=key, max_attempts=attempts)


def test_outbox_rollback_unique_keys_and_tenant_isolation(businesses):
    a, b = businesses
    with factory(a)() as db:
        first = job_for(db, a)
        second = job_for(db, a)
        assert first.id == second.id
        db.rollback()
    with factory(a)() as db:
        assert db.scalar(select(func.count()).select_from(AutomationJob)) == 0
        first = job_for(db, a)
        db.commit()
    with factory(b)() as db:
        assert db.get(AutomationJob, first.id) is None
        second = job_for(db, b)
        db.commit()
        assert second.id != first.id
        with pytest.raises(PermanentAutomationError):
            job_for(db, a)


def test_retry_rolls_back_effects_and_recovers_after_restart(businesses, monkeypatch):
    a = businesses[0]
    original = HANDLERS["record.changed"]
    def broken(db, job):
        db.add(Activity(action="should_rollback", entity="test", description="rolled back"))
        db.flush()
        raise RuntimeError("JWT password secret must not be persisted")
    monkeypatch.setitem(HANDLERS, "record.changed", broken)
    with factory(a)() as db:
        job = job_for(db, a)
        db.commit()
        job_id = job.id
    assert run_once(factory(a))
    with factory(a)() as db:
        job = db.get(AutomationJob, job_id)
        assert job.status == "retry" and job.attempts == 1
        assert job.available_at > utc_now_naive()
        assert job.last_error == "temporary_failure"
        assert db.scalar(select(func.count()).select_from(Activity)) == 0
        job.available_at = utc_now_naive() - timedelta(seconds=1)
        db.commit()
    monkeypatch.setitem(HANDLERS, "record.changed", original)
    assert run_once(factory(a))
    assert not run_once(factory(a))
    with factory(a)() as db:
        job = db.get(AutomationJob, job_id)
        assert job.status == "completed" and job.attempts == 2
        assert job.last_error is None


def test_exhausted_or_invalid_job_is_terminal(businesses, monkeypatch):
    a = businesses[0]
    monkeypatch.setitem(HANDLERS, "record.changed", lambda *_: (_ for _ in ()).throw(RuntimeError("private")))
    with factory(a)() as db:
        job = job_for(db, a, attempts=1)
        db.commit()
        job_id = job.id
    run_once(factory(a))
    with factory(a)() as db:
        job = db.get(AutomationJob, job_id)
        assert job.status == "failed" and job.attempts == 1
        assert not process_job(db, job)
    assert not run_once(factory(a))


def test_worker_skip_locked_multiple_instances_and_interrupted_transaction(businesses):
    a = businesses[0]
    with factory(a)() as db:
        first = job_for(db, a, key="first")
        second = job_for(db, a, key="second")
        db.commit()
        ids = first.id, second.id
    with factory(a)() as held:
        job = held.scalar(select(AutomationJob).where(AutomationJob.id == ids[0]).with_for_update())
        with ThreadPoolExecutor(max_workers=1) as pool:
            assert pool.submit(run_once, factory(a)).result(timeout=10)
        process_job(held, job)
        held.rollback()  # Simulates termination before commit: success/effects must roll back.
    assert run_once(factory(a))
    with factory(a)() as db:
        rows = db.scalars(select(AutomationJob).order_by(AutomationJob.id)).all()
        assert [row.status for row in rows] == ["completed", "completed"]
        assert [row.attempts for row in rows] == [1, 1]


def test_negative_foreign_job_payload_and_bulk_writes(businesses):
    a, b = businesses
    with factory(a)() as db:
        job = job_for(db, a, event="quote.accepted", entity_id=b.customer_id)
        process_job(db, job)
        assert job.status == "failed"
        db.commit()
    with factory(b)() as db:
        result = db.execute(update(Customer).where(Customer.id == a.customer_id).values(name="invaded"))
        assert result.rowcount == 0
        result = db.execute(delete(Customer).where(Customer.id == a.customer_id))
        assert result.rowcount == 0
        with pytest.raises(ValueError):
            db.execute(update(Customer).values(tenant_id=a.tenant_id))
        db.rollback()
    with SessionLocal() as db:
        loaded = db.get(Customer, a.customer_id)
        db.info["tenant_id"] = b.tenant_id
        loaded.name = "invaded"
        with pytest.raises(ValueError):
            db.flush()
        db.rollback()


def test_trial_scheduler_and_repeated_processing(businesses):
    a = businesses[0]
    with factory(a)() as db:
        sub = db.scalar(select(Subscription))
        sub.trial_end = utc_now_naive() - timedelta(seconds=1)
        first = schedule_trial(db, sub)
        second = schedule_trial(db, sub)
        assert first.id == second.id
        db.commit()
    schedule_due_trials()
    run_once(factory(a))
    with factory(a)() as db:
        assert db.scalar(select(Subscription)).status == "trial_expired"
        assert db.scalar(select(func.count()).select_from(Activity).where(Activity.action == "trial_expired")) == 1
    with client_for(a) as client:
        assert client.get("/api/v1/customers").status_code == 402
        assert client.get("/api/v1/billing/subscription").status_code == 200


def test_quote_e2e_acceptance_and_costs_are_idempotent(businesses):
    a, b = businesses
    with client_for(a) as client, client_for(b) as other:
        draft = client.post("/api/v1/quotes/draft", json={"customer_id": a.customer_id, "request_text": "Armário de cozinha 3m x 2m em MDF branco"})
        assert draft.status_code == 200, draft.text
        assert draft.json()["interpretation_source"] == "assisted_local"
        payload = {"customer_id": a.customer_id, "description": "Armário revisado", "material_cost": "100.00",
                   "profit_margin": "30.00", "technical_brief": draft.json()["brief"], "human_reviewed": False}
        assert client.post("/api/v1/quotes", json=payload).status_code == 409
        payload["human_reviewed"] = True
        headers = {"Idempotency-Key": "quote-request-001"}
        quote = client.post("/api/v1/quotes", json=payload, headers=headers)
        assert quote.status_code == 201, quote.text
        quote_id = quote.json()["id"]
        assert quote.json()["total"] == "130.00"
        assert client.post("/api/v1/quotes", json=payload, headers=headers).json()["id"] == quote_id
        assert client.post("/api/v1/quotes", json=payload | {"material_cost": "200"}, headers=headers).status_code == 409
        assert other.get(f"/api/v1/quotes/{quote_id}").status_code == 404
        assert other.patch(f"/api/v1/quotes/{quote_id}/decision", json={"status": "approved"}).status_code == 404
        assert client.patch(f"/api/v1/quotes/{quote_id}/decision", json={"status": "approved"}).status_code == 200
        assert client.post(f"/api/v1/quotes/{quote_id}/shared").status_code == 200
        for _ in range(2):
            response = client.patch(f"/api/v1/quotes/{quote_id}/commercial-status", json={"status": "accepted"})
            assert response.status_code == 200, response.text
        project = client.get("/api/v1/projects").json()[0]
        project_id = project["id"]
        assert client.patch(f"/api/v1/projects/{project_id}/status", json={"status": "measurement"}).status_code == 200
        assert client.patch(f"/api/v1/projects/{project_id}/status", json={"status": "measurement"}).status_code == 409
        cost = {"project_id": project_id, "category": "material", "description": "Custo real", "quantity": "2", "unit_cost": "40"}
        cost_headers = {"Idempotency-Key": "cost-request-001"}
        first = client.post("/api/v1/project-costs", json=cost, headers=cost_headers)
        second = client.post("/api/v1/project-costs", json=cost, headers=cost_headers)
        assert first.status_code == second.status_code == 201
        assert first.json()["id"] == second.json()["id"]
        assert other.post("/api/v1/project-costs", json=cost).status_code == 404
        profit = client.get(f"/api/v1/projects/{project_id}/profitability").json()
        assert profit["real_cost"] == "80.00" and profit["real_profit"] == "50.00"
        assert other.get(f"/api/v1/projects/{project_id}/profitability").status_code == 404
        jobs = client.get("/api/v1/automations").json()
        assert jobs["counts"]["completed"] == 1
        assert all("payload" not in job for job in jobs["jobs"])
        assert other.get("/api/v1/automations").json()["jobs"] == []
    while run_once(factory(a)):
        pass
    with factory(a)() as db:
        assert db.scalar(select(func.count()).select_from(Project)) == 1
        assert db.scalar(select(func.count()).select_from(ProjectCost)) == 1
        assert db.scalar(select(func.count()).select_from(Activity).where(Activity.action == "created_from_quote")) == 1
        assert usage_quantity(db, a.tenant_id, "quotes_month") == 1
        assert usage_quantity(db, a.tenant_id, "ai_month") == 0


def test_quota_is_atomic_persistent_and_cross_tenant_draft_cannot_consume(businesses, monkeypatch):
    a, b = businesses
    monkeypatch.setenv("OPENAI_ENABLED", "true")
    monkeypatch.setenv("OPENAI_API_DISABLED", "false")
    monkeypatch.setenv("OPENAI_API_KEY", "mock-provider-only")
    calls = []
    def parse(**kwargs):
        calls.append(kwargs)
        return SimpleNamespace(choices=[SimpleNamespace(message=SimpleNamespace(parsed={"normalized_description": "Armário seguro", "confidence_score": 50}, refusal=None))], usage=SimpleNamespace(total_tokens=19))
    monkeypatch.setattr(openai, "OpenAI", lambda **_: SimpleNamespace(chat=SimpleNamespace(completions=SimpleNamespace(parse=parse))))
    with factory(a)() as db:
        increment_usage(db, a.tenant_id, "ai_month", 59)
        db.commit()
    with client_for(b) as client:
        assert client.post("/api/v1/quotes/draft", json={"customer_id": a.customer_id, "request_text": "Armário reservado de outro tenant"}).status_code == 404
    assert not calls
    with client_for(a) as client:
        def request():
            return client.post("/api/v1/quotes/draft", json={"customer_id": a.customer_id, "request_text": "Armário MDF para cozinha"})
        with ThreadPoolExecutor(max_workers=2) as pool:
            responses = list(pool.map(lambda _: request(), range(2)))
    assert sorted(response.status_code for response in responses) == [200, 402]
    assert len(calls) == 1
    with factory(a)() as db:
        assert usage_quantity(db, a.tenant_id, "ai_month") == 60
        entry = db.scalar(select(AIUsage))
        assert entry.result == "success" and entry.consumption == 19
        assert "request_text" not in AIUsage.__table__.c
    with factory(b)() as db:
        assert db.scalars(select(AIUsage)).all() == []
        assert db.scalars(select(UsageCounter)).all() == []
        # Reservation survives rollback in the caller transaction.
        extract_quote_brief_result("Armário para cozinha", db=db, tenant_id=b.tenant_id)
        db.rollback()
    with factory(b)() as db:
        assert usage_quantity(db, b.tenant_id, "ai_month") == 1


def test_material_catalog_and_intelligence_history_stay_in_tenant(businesses, monkeypatch):
    a, b = businesses
    with factory(a)() as db:
        db.add(Material(name="Insumo privado A", kind="mdf", unit="chapa", unit_cost=Decimal("180")))
        db.commit()
    with client_for(b) as client:
        assert client.get("/api/v1/materials").json() == []
        result = client.post("/api/v1/quotes/intelligence/recommend", json={"material_cost": "100"})
        assert result.status_code == 200 and result.json()["sample_size"] == 0


def test_simultaneous_acceptance_and_replayed_jobs_create_one_project(businesses):
    a = businesses[0]
    with factory(a)() as db:
        quote = Quote(customer_id=a.customer_id, description="Proposta aceita", total=130, suggested_total=130, status="sent")
        db.add(quote)
        db.commit()
        quote_id = quote.id
    with client_for(a) as client:
        def accept():
            return client.patch(f"/api/v1/quotes/{quote_id}/commercial-status", json={"status": "accepted"})
        with ThreadPoolExecutor(max_workers=2) as pool:
            results = list(pool.map(lambda _: accept(), range(2)))
        assert [result.status_code for result in results] == [200, 200]
    with factory(a)() as db:
        # A second delivery with a different transport key must still deduplicate effects.
        duplicate = job_for(db, a, event="quote.accepted", key="second-transport-delivery", entity_id=quote_id)
        process_job(db, duplicate)
        db.commit()
        assert db.scalar(select(func.count()).select_from(Project)) == 1
        assert db.scalar(select(func.count()).select_from(Activity).where(Activity.action == "accepted")) == 1
        assert db.scalar(select(func.count()).select_from(Activity).where(Activity.action == "created_from_quote")) == 1


def test_signed_subscription_events_are_idempotent_ordered_and_isolated(businesses, monkeypatch):
    import hashlib
    import hmac
    import json
    import time

    a, b = businesses
    secret = "webhook-test-only"
    monkeypatch.setenv("STRIPE_WEBHOOK_SECRET", secret)
    event = {"id": "evt_" + uuid4().hex, "type": "customer.subscription.updated", "created": 200,
             "data": {"object": {"id": "sub_" + uuid4().hex, "customer": "cus_" + uuid4().hex,
                                 "status": "active", "metadata": {"tenant_id": str(a.tenant_id), "plan_code": "professional"}}}}
    def send(client, body):
        raw = json.dumps(body).encode()
        timestamp = str(int(time.time()))
        signature = hmac.new(secret.encode(), timestamp.encode() + b"." + raw, hashlib.sha256).hexdigest()
        return client.post("/api/v1/billing/webhook", content=raw, headers={"Stripe-Signature": f"t={timestamp},v1={signature}"})
    with TestClient(app) as client:
        assert send(client, event).status_code == 200
        assert send(client, event).status_code == 200
        stale = json.loads(json.dumps(event))
        stale.update(id="evt_" + uuid4().hex, created=100)
        stale["data"]["object"]["status"] = "past_due"
        assert send(client, stale).status_code == 200
        forged = client.post("/api/v1/billing/webhook", content=json.dumps(event), headers={"Stripe-Signature": "t=1,v1=wrong"})
        assert forged.status_code == 400
    with factory(a)() as db:
        assert db.scalar(select(Subscription)).status == "active"
        assert db.scalar(select(Subscription)).provider_event_created == 200
        assert db.scalar(select(func.count()).select_from(Subscription)) == 1
        assert db.scalar(select(func.count()).select_from(Activity).where(Activity.action == "subscription_changed")) == 1
        assert db.get(Tenant, a.tenant_id).plan_code == "professional"
    with factory(b)() as db:
        assert db.scalar(select(Subscription)).status == "trialing"
        assert db.scalars(select(AutomationJob)).all() == []


def test_delayed_trial_job_does_not_expire_renewed_subscription(businesses):
    a = businesses[0]
    with factory(a)() as db:
        sub = db.scalar(select(Subscription))
        sub.trial_end = utc_now_naive() - timedelta(seconds=1)
        old = schedule_trial(db, sub)
        sub.trial_end = utc_now_naive() + timedelta(days=10)
        db.flush()
        process_job(db, old)
        db.commit()
        assert sub.status == "trialing"
        assert db.scalar(select(func.count()).select_from(AutomationJob)) == 2
        assert db.scalar(select(func.count()).select_from(Activity)) == 0


def test_onboarding_is_recoverable_without_extending_trial(businesses):
    a = businesses[0]
    with factory(a)() as db:
        original_end = db.scalar(select(Subscription)).trial_end
        job = job_for(db, a, event="tenant.created", key="onboarding", entity_id=a.tenant_id)
        process_job(db, job)
        process_job(db, job)
        db.commit()
        assert db.scalar(select(Subscription)).trial_end == original_end
        assert db.scalar(select(func.count()).select_from(Activity).where(Activity.action == "onboarding_started")) == 1
