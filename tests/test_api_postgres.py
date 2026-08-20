from fastapi.testclient import TestClient

from app.main import app


def test_health():
    client = TestClient(app)
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json()["status"] == "ok"


def test_categories_crud():
    client = TestClient(app)
    payload = {"name": "Cozinha", "description": "Móveis de cozinha"}

    created = client.post("/api/v1/categories", json=payload)
    assert created.status_code == 201
    category_id = created.json()["id"]

    listed = client.get("/api/v1/categories")
    assert listed.status_code == 200
    assert any(item["id"] == category_id for item in listed.json())

    updated = client.put(
        f"/api/v1/categories/{category_id}",
        json={"name": "Cozinha Planejada", "description": "Atualizada"},
    )
    assert updated.status_code == 200
    assert updated.json()["name"] == "Cozinha Planejada"

    deleted = client.delete(f"/api/v1/categories/{category_id}")
    assert deleted.status_code == 204

    missing = client.get(f"/api/v1/categories/{category_id}")
    assert missing.status_code == 404
