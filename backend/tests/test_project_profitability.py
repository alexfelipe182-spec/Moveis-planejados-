from fastapi.testclient import TestClient

from app.database import SessionLocal
from app.main import app
from app.models import User


def csrf_headers(client):
    token = client.cookies.get("csrf_token")
    return {"X-CSRF-Token": token} if token else {}


def admin_client() -> TestClient:
    client = TestClient(app)
    email = "profitability.admin@example.com"
    password = "Senha-Forte-123!"
    assert client.post(
        "/api/v1/auth/register",
        json={"name": "Profitability Admin", "email": email, "password": password},
    ).status_code == 201
    db = SessionLocal()
    try:
        user = db.query(User).filter(User.email == email).one()
        user.is_admin = True
        db.commit()
    finally:
        db.close()
    assert client.post(
        "/api/v1/auth/login", data={"username": email, "password": password}
    ).status_code == 200
    return client


def test_project_profitability_compares_sale_expected_and_real_cost():
    client = admin_client()
    headers = csrf_headers(client)

    customer = client.post("/api/v1/customers", json={"name": "Cliente Margem"}, headers=headers)
    assert customer.status_code == 201

    quote = client.post(
        "/api/v1/quotes",
        json={
            "customer_id": customer.json()["id"],
            "description": "Cozinha margem real",
            "material_cost": "4000.00",
            "hardware_cost": "1000.00",
            "labor_cost": "2000.00",
            "finishing_cost": "1000.00",
            "profit_margin": "25.00",
        },
        headers=headers,
    )
    assert quote.status_code == 201, quote.text
    quote_id = quote.json()["id"]

    accepted = client.post(f"/api/v1/quotes/{quote_id}/accept", headers=headers)
    assert accepted.status_code == 200, accepted.text

    project = client.post(f"/api/v1/quotes/{quote_id}/project", headers=headers)
    assert project.status_code in {200, 201}, project.text
    project_id = project.json()["id"]

    cost = client.post(
        "/api/v1/project-costs",
        json={
            "project_id": project_id,
            "category": "material",
            "description": "Custo real consolidado",
            "quantity": "1.000",
            "unit_cost": "9000.00",
        },
        headers=headers,
    )
    assert cost.status_code == 201, cost.text

    report = client.get(f"/api/v1/projects/{project_id}/profitability")
    assert report.status_code == 200, report.text
    data = report.json()
    assert data["sold_total"] == "10000.00"
    assert data["expected_cost"] == "8000.00"
    assert data["real_cost"] == "9000.00"
    assert data["real_profit"] == "1000.00"
    assert data["real_margin_percent"] == "10.00"
    assert data["cost_variance"] == "1000.00"
    assert data["cost_variance_percent"] == "12.50"
    assert data["health"] == "attention"
