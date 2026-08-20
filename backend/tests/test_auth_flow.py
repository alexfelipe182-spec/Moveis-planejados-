import pytest
from starlette.testclient import TestClient

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
    finally:
        db.close()


def test_auth_flow(client):
    email = "teste.auth@example.com"
    password = "Senha-Forte-123!"

    register = client.post("/api/v1/auth/register", json={"name": "Teste Auth", "email": email, "password": password})
    assert register.status_code == 201

    login = client.post("/api/v1/auth/login", data={"username": email, "password": password})
    assert login.status_code == 200
    assert login.json()["token_type"] == "bearer"
    assert "access_token" in client.cookies
    assert "refresh_token" in client.cookies
    assert "csrf_token" in client.cookies

    me = client.get("/api/v1/me")
    assert me.status_code == 200
    assert me.json()["email"] == email

    missing_csrf = client.post("/api/v1/auth/refresh")
    assert missing_csrf.status_code == 403

    old_refresh = client.cookies.get("refresh_token")
    refresh = client.post("/api/v1/auth/refresh", headers=csrf_headers(client))
    assert refresh.status_code == 200
    new_refresh = client.cookies.get("refresh_token")
    assert new_refresh != old_refresh

    client.cookies.set("refresh_token", old_refresh, domain="testserver.local", path="/api/v1/auth")
    rotated_old = client.post("/api/v1/auth/refresh", headers=csrf_headers(client))
    assert rotated_old.status_code == 401

    client.cookies.set("refresh_token", new_refresh, domain="testserver.local", path="/api/v1/auth")
    logout = client.post("/api/v1/auth/logout", headers=csrf_headers(client))
    assert logout.status_code == 204
    assert "refresh_token" not in client.cookies
    assert "csrf_token" not in client.cookies
    logged_out_refresh = client.post("/api/v1/auth/refresh")
    assert logged_out_refresh.status_code == 403


def test_protected_endpoint_requires_auth(client):
    assert client.get("/api/v1/me").status_code == 401


def test_non_admin_cannot_access_admin_endpoint(client):
    email = "teste.user@example.com"
    password = "Senha-Forte-123!"
    assert client.post("/api/v1/auth/register", json={"name": "Usuário", "email": email, "password": password}).status_code == 201
    assert client.post("/api/v1/auth/login", data={"username": email, "password": password}).status_code == 200
    assert client.get("/api/v1/admin/check").status_code == 403
    assert client.get("/api/v1/admin/dashboard").status_code == 403


def test_csrf_rejects_wrong_token(client):
    email = "teste.csrf@example.com"
    password = "Senha-Forte-123!"
    assert client.post("/api/v1/auth/register", json={"name": "Teste CSRF", "email": email, "password": password}).status_code == 201
    assert client.post("/api/v1/auth/login", data={"username": email, "password": password}).status_code == 200
    assert client.post("/api/v1/auth/refresh", headers={"X-CSRF-Token": "token-incorreto"}).status_code == 403


def test_non_admin_cannot_mutate_crud(client):
    email = "teste.crud.csrf@example.com"
    password = "Senha-Forte-123!"
    assert client.post("/api/v1/auth/register", json={"name": "Teste CRUD", "email": email, "password": password}).status_code == 201
    assert client.post("/api/v1/auth/login", data={"username": email, "password": password}).status_code == 200

    payload = {"name": "Dormitórios", "description": "Móveis para dormitórios"}
    assert client.post("/api/v1/categories", json=payload, headers=csrf_headers(client)).status_code == 403


def test_admin_dashboard_and_user_management(client):
    email = "teste.admin@example.com"
    password = "Senha-Forte-123!"
    assert client.post("/api/v1/auth/register", json={"name": "Administrador", "email": email, "password": password}).status_code == 201
    promote_to_admin(email)
    assert client.post("/api/v1/auth/login", data={"username": email, "password": password}).status_code == 200

    dashboard = client.get("/api/v1/admin/dashboard")
    assert dashboard.status_code == 200
    assert "counts" in dashboard.json()

    users = client.get("/api/v1/admin/users")
    assert users.status_code == 200
    assert any(user["email"] == email for user in users.json())
