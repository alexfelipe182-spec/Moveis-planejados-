from fastapi.testclient import TestClient

from app.database import SessionLocal
from app.main import app
from app.models import User


def csrf_headers(client):
    token = client.cookies.get("csrf_token")
    return {"X-CSRF-Token": token} if token else {}


def test_health():
    client = TestClient(app)
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json()["status"] == "ok"


def test_categories_crud():
    client = TestClient(app)
    email = "crud.admin@example.com"
    password = "Senha-Forte-123!"

    registered = client.post(
        "/api/v1/auth/register",
        json={"name": "Admin CRUD", "email": email, "password": password},
    )
    assert registered.status_code == 201

    db = SessionLocal()
    try:
        user = db.query(User).filter(User.email == email).one()
        user.is_admin = True
        db.commit()
    finally:
        db.close()

    login = client.post("/api/v1/auth/login", data={"username": email, "password": password})
    assert login.status_code == 200

    payload = {"name": "Cozinha", "description": "Móveis de cozinha"}
    created = client.post("/api/v1/categories", json=payload, headers=csrf_headers(client))
    assert created.status_code == 201
    category_id = created.json()["id"]

    listed = client.get("/api/v1/categories")
    assert listed.status_code == 200
    assert any(item["id"] == category_id for item in listed.json())

    updated = client.put(
        f"/api/v1/categories/{category_id}",
        json={"name": "Cozinha Planejada", "description": "Atualizada"},
        headers=csrf_headers(client),
    )
    assert updated.status_code == 200
    assert updated.json()["name"] == "Cozinha Planejada"

    deleted = client.delete(f"/api/v1/categories/{category_id}", headers=csrf_headers(client))
    assert deleted.status_code == 204

    missing = client.get(f"/api/v1/categories/{category_id}")
    assert missing.status_code == 404
