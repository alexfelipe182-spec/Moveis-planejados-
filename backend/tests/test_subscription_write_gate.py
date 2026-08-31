from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import Session
from sqlalchemy.pool import StaticPool

from app.api.deps import get_current_user, require_admin, require_cookie_csrf
from app.api.routes import api_router
from app.database import Base, get_db
from app.models import Organization, Plan, Subscription


def test_inactive_subscription_is_read_only_until_access_is_restored():
    engine = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)
    Base.metadata.create_all(engine)
    database = Session(engine)
    database.add(Organization(id=10, name="Marcenaria A", slug="a"))
    database.add(Plan(id=1, code="starter", name="Starter", monthly_price_cents=4900, max_users=3, features={}))
    database.commit()
    database.add(Subscription(organization_id=10, plan_id=1, status="past_due", provider="sandbox"))
    database.commit()
    active_user = type(
        "UserContext",
        (),
        {"id": 1, "organization_id": 10, "is_admin": True, "is_platform_admin": False},
    )()
    app = FastAPI()
    app.include_router(api_router)
    app.dependency_overrides[get_current_user] = lambda: active_user
    app.dependency_overrides[require_admin] = lambda: active_user
    app.dependency_overrides[get_db] = lambda: database
    app.dependency_overrides[require_cookie_csrf] = lambda: None

    try:
        with TestClient(app) as client:
            assert client.get("/api/v1/customers").status_code == 200
            blocked = client.post("/api/v1/customers", json={"name": "Cliente bloqueado"})
            assert blocked.status_code == 402
            assert "assinatura" in blocked.json()["detail"].lower()

            subscription = database.query(Subscription).filter(Subscription.organization_id == 10).one()
            subscription.status = "active"
            database.commit()
            created = client.post("/api/v1/customers", json={"name": "Cliente autorizado"})
            assert created.status_code == 201
            assert created.json()["name"] == "Cliente autorizado"
    finally:
        database.close()
        engine.dispose()
