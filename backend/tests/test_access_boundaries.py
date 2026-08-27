from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

import app.main as main_module
from app.core.resilience import RateLimitDecision
from app.core.security import create_access_token
from app.database import Base, get_db
from app.models import User


INTERNAL_READS = [
    "/api/v1/customers", "/api/v1/customers/1", "/api/v1/customers/1/history",
    "/api/v1/quotes", "/api/v1/quotes/1", "/api/v1/quotes/1/items",
    "/api/v1/projects", "/api/v1/projects/1",
    "/api/v1/products", "/api/v1/products/1",
    "/api/v1/categories", "/api/v1/categories/1",
    "/api/v1/activities", "/api/v1/admin/dashboard", "/api/v1/admin/users",
]


@pytest.fixture
def access_client(monkeypatch):
    monkeypatch.setattr(main_module.settings, "secret_key", "access-boundary-test-key-not-for-production-123")
    monkeypatch.setattr(main_module.settings, "environment", "test")
    database = create_engine(
        "sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool
    )
    Base.metadata.create_all(database)
    sessions = sessionmaker(database, expire_on_commit=False)
    with sessions() as db:
        db.add_all([
            User(id=1, name="Equipe teste", email="staff@example.com", password_hash="unused", is_admin=True),
            User(id=2, name="Visitante teste", email="visitor@example.com", password_hash="unused", is_admin=False),
            User(id=3, name="Inativo teste", email="inactive@example.com", password_hash="unused", is_active=False),
        ])
        db.commit()

    def isolated_db():
        with sessions() as db:
            yield db

    original_overrides = main_module.app.dependency_overrides.copy()
    main_module.app.dependency_overrides[get_db] = isolated_db
    monkeypatch.setattr(main_module.rate_limiter, "allow", AsyncMock(return_value=RateLimitDecision(True, 0)))
    monkeypatch.setattr(main_module.rate_limiter, "redis", SimpleNamespace(aclose=AsyncMock()))
    try:
        with TestClient(main_module.app) as client:
            yield client
    finally:
        main_module.app.dependency_overrides.clear()
        main_module.app.dependency_overrides.update(original_overrides)
        database.dispose()


@pytest.mark.parametrize("path", INTERNAL_READS)
def test_anonymous_cannot_read_internal_records(access_client, path):
    assert access_client.get(path).status_code == 401


@pytest.mark.parametrize("path", INTERNAL_READS)
def test_registered_non_admin_cannot_read_internal_records(access_client, path):
    token = create_access_token("2")
    response = access_client.get(path, headers={"Authorization": f"Bearer {token}"})
    assert response.status_code == 403


@pytest.mark.parametrize("path", INTERNAL_READS)
def test_disabled_user_cannot_read_internal_records(access_client, path):
    token = create_access_token("3")
    assert access_client.get(path, headers={"Authorization": f"Bearer {token}"}).status_code == 401


@pytest.mark.parametrize("path", ["/api/v1/customers", "/api/v1/quotes", "/api/v1/projects"])
def test_authorized_staff_keep_read_access(access_client, path):
    token = create_access_token("1")
    response = access_client.get(path, headers={"Authorization": f"Bearer {token}"})
    assert response.status_code == 200
    assert response.json() == []


def test_public_registration_never_grants_internal_access(access_client):
    payload = {"name": "Novo visitante", "email": "public@example.com", "password": "Only-for-test-123!", "is_admin": True}
    registered = access_client.post("/api/v1/auth/register", json=payload)
    assert registered.status_code == 201
    assert registered.json()["is_admin"] is False
    login = access_client.post("/api/v1/auth/login", data={"username": payload["email"], "password": payload["password"]})
    assert login.status_code == 200
    assert access_client.get("/api/v1/me").status_code == 200
    for path in INTERNAL_READS:
        assert access_client.get(path).status_code == 403


def test_release_workflow_and_approved_quote_integrity(access_client, monkeypatch):
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    access_client.headers["Authorization"] = f"Bearer {create_access_token('1')}"
    customer = access_client.post("/api/v1/customers", json={"name": "Cliente de homologação"})
    assert customer.status_code == 201
    customer_id = customer.json()["id"]
    quote = access_client.post("/api/v1/quotes", json={
        "customer_id": customer_id, "description": "Cozinha de homologação",
        "material_cost": "100", "hardware_cost": "20", "labor_cost": "50",
        "finishing_cost": "30", "profit_margin": "30",
    })
    assert quote.status_code == 201
    quote_id = quote.json()["id"]
    assert quote.json()["status"] == "analysis"
    assert quote.json()["total"] == "260.00"
    item = access_client.post(f"/api/v1/quotes/{quote_id}/items", json={
        "name": "Armário de teste", "quantity": "2", "unit_price": "130.00",
    })
    assert item.status_code == 201
    item_id = item.json()["id"]
    approved = access_client.patch(f"/api/v1/quotes/{quote_id}/decision", json={"status": "approved"})
    assert approved.status_code == 200
    assert approved.json()["status"] == "approved"
    assert access_client.put(f"/api/v1/quotes/{quote_id}/items/{item_id}", json={"quantity": "99"}).status_code == 409
    assert access_client.delete(f"/api/v1/quotes/{quote_id}/items/{item_id}").status_code == 409
    assert access_client.post(f"/api/v1/quotes/{quote_id}/items", json={"name": "Novo item", "unit_price": "1"}).status_code == 409
    assert access_client.get(f"/api/v1/quotes/{quote_id}").json()["total"] == "260.00"
    sent = access_client.post(f"/api/v1/quotes/{quote_id}/shared")
    assert sent.status_code == 200
    accepted = access_client.patch(f"/api/v1/quotes/{quote_id}/commercial-status", json={"status": "accepted"})
    assert accepted.status_code == 200
    projects = access_client.get("/api/v1/projects").json()
    project = next(row for row in projects if row["quote_id"] == quote_id)
    for stage in ("measurement", "technical_design", "purchasing", "production", "installation", "delivered", "completed"):
        finished = access_client.patch(f"/api/v1/projects/{project['id']}/status", json={"status": stage})
        assert finished.status_code == 200
    assert finished.json()["status"] == "completed"
    activities = access_client.get("/api/v1/activities").json()
    assert {"created", "approved", "shared", "accepted", "status_changed"} <= {entry["action"] for entry in activities}
