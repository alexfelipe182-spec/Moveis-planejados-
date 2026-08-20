from uuid import uuid4

from fastapi.testclient import TestClient

from app.main import app


def test_health():
    response = TestClient(app).get("/health")

    assert response.status_code == 200
    assert response.json()["status"] == "ok"


def test_categories_crud_requires_authentication():
    client = TestClient(app)
    category_name = f"Cozinha {uuid4()}"
    payload = {"name": category_name, "description": "Móveis de cozinha"}

    assert client.post("/api/v1/categories", json=payload).status_code == 401

    email = f"crud.{uuid4()}@example.com"
    password = "Senha-Forte-123!"
    assert client.post(
        "/api/v1/auth/register",
        json={"name": "Teste CRUD", "email": email, "password": password},
    ).status_code == 201
    login = client.post("/api/v1/auth/login", data={"username": email, "password": password})
    assert login.status_code == 200
    headers = {"Authorization": f"Bearer {login.json()['access_token']}"}

    created = client.post("/api/v1/categories", json=payload, headers=headers)
    assert created.status_code == 201
    category_id = created.json()["id"]

    listed = client.get("/api/v1/categories", headers=headers)
    assert listed.status_code == 200
    assert any(item["id"] == category_id for item in listed.json())

    updated = client.put(
        f"/api/v1/categories/{category_id}",
        json={"name": f"{category_name} Planejada", "description": "Atualizada"},
        headers=headers,
    )
    assert updated.status_code == 200
    assert updated.json()["name"] == f"{category_name} Planejada"

    deleted = client.delete(f"/api/v1/categories/{category_id}", headers=headers)
    assert deleted.status_code == 204

    assert client.get(f"/api/v1/categories/{category_id}", headers=headers).status_code == 404
