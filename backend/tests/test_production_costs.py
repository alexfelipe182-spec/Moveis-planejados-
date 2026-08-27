from fastapi.testclient import TestClient

from app.database import SessionLocal
from app.main import app
from app.models import User


def csrf_headers(client):
    token = client.cookies.get("csrf_token")
    return {"X-CSRF-Token": token} if token else {}


def admin_client() -> TestClient:
    client = TestClient(app)
    email = "production.costs.admin@example.com"
    password = "Senha-Forte-123!"
    assert client.post("/api/v1/auth/register", json={"name": "Production Costs Admin", "email": email, "password": password}).status_code == 201
    db = SessionLocal()
    try:
        user = db.query(User).filter(User.email == email).one()
        user.is_admin = True
        db.commit()
    finally:
        db.close()
    assert client.post("/api/v1/auth/login", data={"username": email, "password": password}).status_code == 200
    return client


def test_material_waste_and_project_cost_total():
    client = admin_client()
    headers = csrf_headers(client)

    customer = client.post(
        "/api/v1/customers",
        json={"name": "Cliente Custos"},
        headers=headers,
    )
    assert customer.status_code == 201

    project = client.post(
        "/api/v1/projects",
        json={"customer_id": customer.json()["id"], "name": "Cozinha Custos"},
        headers=headers,
    )
    assert project.status_code == 201

    supplier = client.post(
        "/api/v1/suppliers",
        json={"name": "Fornecedor MDF"},
        headers=headers,
    )
    assert supplier.status_code == 201

    material = client.post(
        "/api/v1/materials",
        json={
            "supplier_id": supplier.json()["id"],
            "name": "MDF Branco 18mm",
            "kind": "mdf",
            "unit": "chapa",
            "unit_cost": "200.00",
            "waste_percent": "10.00",
        },
        headers=headers,
    )
    assert material.status_code == 201

    cost = client.post(
        "/api/v1/project-costs",
        json={
            "project_id": project.json()["id"],
            "material_id": material.json()["id"],
            "category": "material",
            "description": "Chapas da cozinha",
            "quantity": "2.000",
            "unit_cost": "0.00",
        },
        headers=headers,
    )
    assert cost.status_code == 201, cost.text
    assert cost.json()["unit_cost"] == "200.00"
    assert cost.json()["total_cost"] == "440.00"

    total = client.get(f"/api/v1/project-costs/project/{project.json()['id']}/total")
    assert total.status_code == 200
    assert total.json()["total_cost"] == "440.00"
