import pytest
from fastapi.testclient import TestClient

from app.main import app


@pytest.fixture
def client():
    return TestClient(app)


def csrf_headers(client):
    return {"X-CSRF-Token": client.cookies.get("csrf_token")}


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

    logged_out_refresh = client.post("/api/v1/auth/refresh", headers=csrf_headers(client))
    assert logged_out_refresh.status_code in (401, 403)


def test_protected_endpoint_requires_auth(client):
    assert client.get("/api/v1/me").status_code == 401


def test_non_admin_cannot_access_admin_endpoint(client):
    email = "teste.user@example.com"
    password = "Senha-Forte-123!"
    assert client.post("/api/v1/auth/register", json={"name": "Usuário", "email": email, "password": password}).status_code == 201
    assert client.post("/api/v1/auth/login", data={"username": email, "password": password}).status_code == 200
    assert client.get("/api/v1/admin/check").status_code == 403


def test_csrf_rejects_wrong_token(client):
    email = "teste.csrf@example.com"
    password = "Senha-Forte-123!"
    assert client.post("/api/v1/auth/register", json={"name": "Teste CSRF", "email": email, "password": password}).status_code == 201
    assert client.post("/api/v1/auth/login", data={"username": email, "password": password}).status_code == 200
    assert client.post("/api/v1/auth/refresh", headers={"X-CSRF-Token": "token-incorreto"}).status_code == 403
