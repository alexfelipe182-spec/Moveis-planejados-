"""Full tenant-scoped workflow against a disposable database."""

from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import Session
from sqlalchemy.pool import StaticPool

from app.api.deps import get_current_user, require_admin, require_cookie_csrf
from app.api.routes import api_router
from app.core.config import settings
from app.database import Base, get_db
from app.models import Organization, Plan, Subscription, User
from app.core.security import hash_password


def test_customer_quote_project_production_flow_is_tenant_scoped():
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    database = Session(engine)
    database.add_all(
        [
            Organization(id=10, name="Marcenaria A", slug="a"),
            Organization(id=20, name="Marcenaria B", slug="b"),
        ]
    )
    database.commit()
    active_user = {"value": type("UserContext", (), {"id": 1, "organization_id": 10, "is_admin": True})()}
    app = FastAPI()
    app.include_router(api_router)
    app.dependency_overrides[get_db] = lambda: database
    app.dependency_overrides[get_current_user] = lambda: active_user["value"]
    app.dependency_overrides[require_admin] = lambda: active_user["value"]
    app.dependency_overrides[require_cookie_csrf] = lambda: None

    try:
        with TestClient(app) as client:
            customer = client.post("/api/v1/customers", json={"name": "Cliente A"})
            assert customer.status_code == 201, customer.text
            customer_id = customer.json()["id"]

            quote = client.post(
                "/api/v1/quotes",
                json={
                    "customer_id": customer_id,
                    "description": "Cozinha planejada A",
                    "material_cost": "4000.00",
                    "hardware_cost": "1000.00",
                    "labor_cost": "2000.00",
                    "finishing_cost": "1000.00",
                    "profit_margin": "25.00",
                },
            )
            assert quote.status_code == 201, quote.text
            quote_id = quote.json()["id"]
            assert quote.json()["intelligence_sample_size"] == 0

            assert client.patch(f"/api/v1/quotes/{quote_id}/decision", json={"status": "approved"}).status_code == 200
            assert client.post(f"/api/v1/quotes/{quote_id}/shared").status_code == 200
            accepted = client.patch(
                f"/api/v1/quotes/{quote_id}/commercial-status",
                json={"status": "accepted"},
            )
            assert accepted.status_code == 200, accepted.text
            project_id = client.get("/api/v1/projects").json()[0]["id"]

            for status in ("measurement", "technical_design", "purchasing", "production"):
                response = client.patch(f"/api/v1/projects/{project_id}/status", json={"status": status})
                assert response.status_code == 200, response.text

            cost = client.post(
                "/api/v1/project-costs",
                json={
                    "project_id": project_id,
                    "category": "material",
                    "description": "MDF premium",
                    "quantity": "1.000",
                    "unit_cost": "9000.00",
                },
            )
            assert cost.status_code == 201, cost.text
            assert client.get(f"/api/v1/project-costs/project/{project_id}/total").json()["total_cost"] == "9000.00"
            profitability = client.get(f"/api/v1/projects/{project_id}/profitability")
            assert profitability.status_code == 200, profitability.text
            assert profitability.json()["real_cost"] == "9000.00"
            assert profitability.json()["health"] in {"healthy", "attention", "critical", "loss"}

            active_user["value"] = type("UserContext", (), {"id": 2, "organization_id": 20, "is_admin": True})()
            assert client.get("/api/v1/customers").json() == []
            assert client.get(f"/api/v1/quotes/{quote_id}").status_code == 404
            assert client.patch(f"/api/v1/projects/{project_id}/status", json={"status": "installation"}).status_code == 404
            assert client.get(f"/api/v1/projects/{project_id}/profitability").status_code == 404
    finally:
        database.close()
        engine.dispose()


def test_platform_panel_is_separate_from_marcenaria_admin_and_aggregates_only():
    engine = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)
    Base.metadata.create_all(engine)
    database = Session(engine)
    database.add_all([
        Organization(id=10, name="Marcenaria A", slug="a"),
        Organization(id=20, name="Marcenaria B", slug="b"),
    ])
    database.commit()
    active_user = {"value": type("UserContext", (), {"id": 1, "organization_id": 10, "is_admin": True, "is_platform_admin": True})()}
    app = FastAPI()
    app.include_router(api_router)
    app.dependency_overrides[get_db] = lambda: database
    app.dependency_overrides[get_current_user] = lambda: active_user["value"]
    app.dependency_overrides[require_admin] = lambda: active_user["value"]
    app.dependency_overrides[require_cookie_csrf] = lambda: None

    try:
        with TestClient(app) as client:
            overview = client.get("/api/v1/platform/overview")
            assert overview.status_code == 200
            assert overview.json() == {
                "organizations": 2,
                "users": 0,
                "subscriptions": 0,
                "subscription_statuses": {},
            }
            organizations = client.get("/api/v1/platform/organizations")
            assert organizations.status_code == 200
            assert organizations.json()[0]["name"] == "Marcenaria A"
            assert "customers" not in organizations.json()[0]

            active_user["value"] = type("UserContext", (), {"id": 1, "organization_id": 10, "is_admin": True, "is_platform_admin": False})()
            assert client.get("/api/v1/platform/overview").status_code == 403
    finally:
        database.close()
        engine.dispose()


def test_sandbox_billing_is_tenant_scoped_and_webhook_is_idempotent(monkeypatch):
    engine = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)
    Base.metadata.create_all(engine)
    database = Session(engine)
    database.add(Organization(id=10, name="Marcenaria A", slug="a"))
    database.add_all([
        Plan(id=1, code="starter", name="Starter", monthly_price_cents=0, max_users=3, features={"quotes": True}),
        Plan(id=2, code="pro", name="Pro", monthly_price_cents=9900, max_users=10, features={"quotes": True, "intelligence": True}),
    ])
    database.add(Subscription(organization_id=10, plan_id=1, status="trial", provider="sandbox"))
    database.commit()
    active_user = type("UserContext", (), {"id": 1, "organization_id": 10, "is_admin": True, "is_platform_admin": False})()
    app = FastAPI()
    app.include_router(api_router)
    app.dependency_overrides[get_current_user] = lambda: active_user
    app.dependency_overrides[require_admin] = lambda: active_user
    app.dependency_overrides[get_db] = lambda: database
    app.dependency_overrides[require_cookie_csrf] = lambda: None

    monkeypatch.setattr(settings, "billing_provider", "sandbox")
    try:
        with TestClient(app) as client:
            assert client.get("/api/v1/plans").json()[0]["code"] == "starter"
            current = client.get("/api/v1/billing/subscription")
            assert current.status_code == 200
            assert current.json()["plan_code"] == "starter"
            assert current.json()["access_allowed"] is True
            checkout = client.post("/api/v1/billing/checkout", json={"plan_code": "pro"})
            assert checkout.status_code == 200
            assert checkout.json()["mode"] == "test"

            payload = {
                "id": "evt_001",
                "type": "subscription.updated",
                "data": {"organization_id": 10, "plan_code": "pro", "status": "active", "subscription_id": "sub_001"},
            }
            first = client.post("/api/v1/billing/webhooks/sandbox", json=payload)
            second = client.post("/api/v1/billing/webhooks/sandbox", json=payload)
            assert first.json() == {"accepted": True, "duplicate": False, "status": "processed"}
            assert second.json() == {"accepted": True, "duplicate": True, "status": "processed"}
            altered = {
                **payload,
                "data": {**payload["data"], "status": "past_due"},
            }
            replay_conflict = client.post("/api/v1/billing/webhooks/sandbox", json=altered)
            assert replay_conflict.status_code == 400
            assert "Webhook inválido" in replay_conflict.json()["detail"]
            database.expire_all()
            subscription = database.query(Subscription).filter(Subscription.organization_id == 10).one()
            assert subscription.status == "active"
            assert subscription.plan.code == "pro"
    finally:
        database.close()
        engine.dispose()


def test_onboarding_status_is_dynamic_and_member_limit_is_enforced():
    engine = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)
    Base.metadata.create_all(engine)
    database = Session(engine)
    owner = User(
        id=1,
        organization_id=10,
        name="Owner",
        email="owner@example.com",
        password_hash=hash_password("Senha-Segura-123!"),
        is_admin=True,
    )
    database.add(Organization(id=10, name="Marcenaria A", slug="a"))
    database.commit()
    database.add_all([
        owner,
        Plan(id=1, code="starter", name="Starter", monthly_price_cents=0, max_users=1, features={}),
    ])
    database.commit()
    database.add(Subscription(organization_id=10, plan_id=1, status="trial", provider="internal"))
    database.commit()
    active_user = type("UserContext", (), {"id": 1, "organization_id": 10, "is_admin": True, "is_platform_admin": False})()
    app = FastAPI()
    app.include_router(api_router)
    app.dependency_overrides[get_current_user] = lambda: active_user
    app.dependency_overrides[require_admin] = lambda: active_user
    app.dependency_overrides[get_db] = lambda: database
    app.dependency_overrides[require_cookie_csrf] = lambda: None
    try:
        with TestClient(app) as client:
            onboarding = client.get("/api/v1/onboarding/status")
            assert onboarding.status_code == 200
            assert onboarding.json()["next_step"] == "first_customer"
            blocked = client.post(
                "/api/v1/onboarding/members",
                json={"name": "Segundo", "email": "second@example.com", "password": "Senha-Segura-123!"},
            )
            assert blocked.status_code == 409
            assert "Limite" in blocked.json()["detail"]

            subscription = database.query(Subscription).filter(Subscription.organization_id == 10).one()
            subscription.status = "past_due"
            database.commit()
            inactive = client.get("/api/v1/onboarding/status")
            subscription_item = next(item for item in inactive.json()["checklist"] if item["key"] == "subscription")
            assert inactive.json()["subscription"]["access_allowed"] is False
            assert subscription_item["complete"] is False
            assert inactive.json()["next_step"] == "subscription"
            payment_blocked = client.post(
                "/api/v1/onboarding/members",
                json={"name": "Segundo", "email": "another@example.com", "password": "Senha-Segura-123!"},
            )
            assert payment_blocked.status_code == 402
    finally:
        database.close()
        engine.dispose()
