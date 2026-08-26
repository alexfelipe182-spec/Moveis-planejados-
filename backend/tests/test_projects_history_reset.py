from starlette.testclient import TestClient

from app.database import SessionLocal
from app.main import app
from app.models import User


def csrf_headers(client):
    token = client.cookies.get("csrf_token")
    return {"X-CSRF-Token": token} if token else {}


def admin_client(email: str) -> TestClient:
    client = TestClient(app)
    password = "Senha-Forte-123!"
    response = client.post("/api/v1/auth/register", json={"name": "Admin Features", "email": email, "password": password})
    assert response.status_code == 201
    db = SessionLocal()
    try:
        user = db.query(User).filter(User.email == email).one()
        user.is_admin = True
        db.commit()
    finally:
        db.close()
    assert client.post("/api/v1/auth/login", data={"username": email, "password": password}).status_code == 200
    return client


def test_project_quote_and_activity_history():
    client = admin_client("admin.features@example.com")
    headers = csrf_headers(client)
    customer = client.post("/api/v1/customers", json={"name": "Cliente Projeto", "email": "cliente.projeto@example.com", "phone": "13999990000"}, headers=headers)
    assert customer.status_code == 201
    customer_id = customer.json()["id"]

    project = client.post("/api/v1/projects", json={
        "customer_id": customer_id,
        "name": "Cozinha Ideal",
        "description": "Projeto completo de cozinha",
        "measurements": "3,20m x 0,65m",
        "materials": "MDF amadeirado + ferragens",
        "status": "planning",
        "photos": ["https://example.com/cozinha.jpg"],
    }, headers=headers)
    assert project.status_code == 201
    assert project.json()["photos"] == ["https://example.com/cozinha.jpg"]

    quote = client.post("/api/v1/quotes", json={
        "customer_id": customer_id,
        "description": "Orçamento da cozinha",
        "measurements": "3,20m x 0,65m",
        "materials": "MDF amadeirado",
        "total": "8500.00",
        "status": "analysis",
    }, headers=headers)
    assert quote.status_code == 201
    assert quote.json()["status"] == "analysis"

    history = client.get(f"/api/v1/customers/{customer_id}/history")
    assert history.status_code == 200
    assert any(item["entity"] == "customer" for item in history.json())

    activities = client.get("/api/v1/activities")
    assert activities.status_code == 200
    assert any(item["entity"] == "project" for item in activities.json())
    assert any(item["entity"] == "quote" for item in activities.json())


def test_password_reset_token_expires_and_can_be_used_once():
    client = TestClient(app)
    email = "password.reset@example.com"
    old_password = "Senha-Antiga-123!"
    new_password = "Senha-Nova-123!"
    assert client.post("/api/v1/auth/register", json={"name": "Reset Test", "email": email, "password": old_password}).status_code == 201

    old_login = client.post("/api/v1/auth/login", data={"username": email, "password": old_password})
    assert old_login.status_code == 200
    old_csrf = csrf_headers(client)

    request = client.post("/api/v1/auth/password-reset/request", json={"email": email})
    assert request.status_code == 200
    token = request.json()["debug_token"]
    assert token

    confirm = client.post("/api/v1/auth/password-reset/confirm", json={"token": token, "new_password": new_password})
    assert confirm.status_code == 200
    reused = client.post("/api/v1/auth/password-reset/confirm", json={"token": token, "new_password": old_password})
    assert reused.status_code == 400

    revoked_session = client.post("/api/v1/auth/refresh", headers=old_csrf)
    assert revoked_session.status_code == 401

    login = client.post("/api/v1/auth/login", data={"username": email, "password": new_password})
    assert login.status_code == 200
