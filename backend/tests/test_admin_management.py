import pytest
from fastapi.testclient import TestClient

from app.database import SessionLocal
from app.main import app
from app.models import User


@pytest.fixture
def client():
    with TestClient(app) as test_client:
        yield test_client


def csrf_headers(client):
    token = client.cookies.get("csrf_token")
    return {"X-CSRF-Token": token} if token else {}


def promote_to_admin(email: str):
    db = SessionLocal()
    try:
        user = db.query(User).filter(User.email == email).one()
        user.is_admin = True
        db.commit()
        return user.id
    finally:
        db.close()


def move_to_organization(*, email: str, organization_id: int):
    db = SessionLocal()
    try:
        user = db.query(User).filter(User.email == email).one()
        user.organization_id = organization_id
        db.commit()
    finally:
        db.close()


def register(client, *, name: str, email: str, password: str):
    response = client.post(
        "/api/v1/auth/register",
        json={"name": name, "email": email, "password": password},
    )
    assert response.status_code == 201


def login(client, *, email: str, password: str):
    response = client.post(
        "/api/v1/auth/login",
        data={"username": email, "password": password},
    )
    assert response.status_code == 200


def test_admin_user_management_guards_and_update(client):
    password = "Senha-Forte-123!"
    admin_email = "admin.management@example.com"
    target_email = "target.management@example.com"
    duplicate_email = "duplicate.management@example.com"

    register(client, name="Admin Management", email=admin_email, password=password)
    admin_id = promote_to_admin(admin_email)
    register(client, name="Target User", email=target_email, password=password)
    register(client, name="Duplicate User", email=duplicate_email, password=password)
    with SessionLocal() as db:
        admin_org_id = db.query(User.organization_id).filter(User.email == admin_email).scalar()
    move_to_organization(email=target_email, organization_id=admin_org_id)
    move_to_organization(email=duplicate_email, organization_id=admin_org_id)
    login(client, email=admin_email, password=password)

    users = client.get("/api/v1/admin/users")
    assert users.status_code == 200
    target_id = next(user["id"] for user in users.json() if user["email"] == target_email)

    missing = client.patch(
        "/api/v1/admin/users/999999999",
        json={"name": "Missing User"},
        headers=csrf_headers(client),
    )
    assert missing.status_code == 404
    assert missing.json()["detail"] == "Usuário não encontrado"

    duplicate = client.patch(
        f"/api/v1/admin/users/{target_id}",
        json={"email": duplicate_email.upper()},
        headers=csrf_headers(client),
    )
    assert duplicate.status_code == 409
    assert duplicate.json()["detail"] == "E-mail já cadastrado"

    self_demote = client.patch(
        f"/api/v1/admin/users/{admin_id}",
        json={"is_admin": False},
        headers=csrf_headers(client),
    )
    assert self_demote.status_code == 400
    assert "própria permissão" in self_demote.json()["detail"]

    self_deactivate = client.patch(
        f"/api/v1/admin/users/{admin_id}",
        json={"is_active": False},
        headers=csrf_headers(client),
    )
    assert self_deactivate.status_code == 400
    assert "própria conta" in self_deactivate.json()["detail"]

    updated = client.patch(
        f"/api/v1/admin/users/{target_id}",
        json={"name": "Target Updated", "email": "TARGET.UPDATED@EXAMPLE.COM"},
        headers=csrf_headers(client),
    )
    assert updated.status_code == 200
    body = updated.json()
    assert body["name"] == "Target Updated"
    assert body["email"] == "target.updated@example.com"

    refreshed_users = client.get("/api/v1/admin/users")
    assert refreshed_users.status_code == 200
    refreshed = next(user for user in refreshed_users.json() if user["id"] == target_id)
    assert refreshed["name"] == "Target Updated"
    assert refreshed["email"] == "target.updated@example.com"
