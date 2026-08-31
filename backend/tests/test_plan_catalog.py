from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session
from sqlalchemy.pool import StaticPool

from app.api.auth import router as auth_router
from app.api.billing import router as billing_router
from app.database import Base, get_db
from app.models import Organization, Plan, Subscription, User


def commercial_plans():
    return [
        Plan(
            code="starter",
            name="Essencial",
            monthly_price_cents=4900,
            max_users=3,
            features={"customers": True, "quotes": True, "projects": True, "production": True, "costs": True},
        ),
        Plan(
            code="pro",
            name="Profissional",
            monthly_price_cents=9900,
            max_users=10,
            features={"intelligence": True, "automation": True, "profitability": True},
        ),
        Plan(
            code="scale",
            name="Empresarial",
            monthly_price_cents=24900,
            max_users=50,
            features={"advanced_reports": True, "priority_support": True, "assisted_onboarding": True},
        ),
    ]


def test_public_catalog_and_selected_trial_are_consistent():
    engine = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)
    Base.metadata.create_all(engine)
    database = Session(engine)
    database.add_all(commercial_plans())
    database.commit()
    app = FastAPI()
    app.include_router(auth_router, prefix="/api/v1")
    app.include_router(billing_router, prefix="/api/v1")
    app.dependency_overrides[get_db] = lambda: database

    try:
        with TestClient(app) as client:
            catalog = client.get("/api/v1/plans")
            assert catalog.status_code == 200
            assert [(plan["code"], plan["monthly_price_cents"]) for plan in catalog.json()] == [
                ("starter", 4900),
                ("pro", 9900),
                ("scale", 24900),
            ]

            registration = client.post(
                "/api/v1/auth/register",
                json={
                    "organization_name": "Marcenaria Plano Pro",
                    "name": "Responsável",
                    "email": "plano-pro@example.com",
                    "password": "Senha-Segura-123!",
                    "plan_code": "pro",
                },
            )
            assert registration.status_code == 201, registration.text
            user = database.scalar(select(User).where(User.email == "plano-pro@example.com"))
            subscription = database.scalar(select(Subscription).where(Subscription.organization_id == user.organization_id))
            assert subscription.plan.code == "pro"
            assert subscription.status == "trial"
            assert subscription.trial_end is not None

            unavailable = client.post(
                "/api/v1/auth/register",
                json={
                    "organization_name": "Marcenaria Inválida",
                    "name": "Responsável",
                    "email": "plano-invalido@example.com",
                    "password": "Senha-Segura-123!",
                    "plan_code": "inexistente",
                },
            )
            assert unavailable.status_code == 400
            assert database.scalar(select(Organization).where(Organization.slug == "marcenaria-invalida")) is None
    finally:
        database.close()
        engine.dispose()
