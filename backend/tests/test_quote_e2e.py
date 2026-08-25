from fastapi.testclient import TestClient

from app.database import SessionLocal
from app.main import app
from app.models import User


def csrf_headers(client):
    token = client.cookies.get("csrf_token")
    return {"X-CSRF-Token": token} if token else {}


def test_quote_creation_end_to_end_persists_analysis_and_automation():
    client = TestClient(app)
    email = "quote.e2e.admin@example.com"
    password = "Senha-Forte-123!"

    registered = client.post(
        "/api/v1/auth/register",
        json={"name": "Quote E2E Admin", "email": email, "password": password},
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

    customer = client.post(
        "/api/v1/customers",
        json={"name": "Cliente E2E", "email": "cliente.e2e@example.com"},
        headers=csrf_headers(client),
    )
    assert customer.status_code == 201
    customer_id = customer.json()["id"]

    quote = client.post(
        "/api/v1/quotes",
        json={
            "customer_id": customer_id,
            "description": "Cozinha planejada E2E",
            "measurements": "3,00m x 2,50m",
            "materials": "MDF 18mm",
            "material_cost": "800.00",
            "hardware_cost": "350.00",
            "labor_cost": "900.00",
            "finishing_cost": "450.00",
            "profit_margin": "30.00",
        },
        headers=csrf_headers(client),
    )
    assert quote.status_code == 201, quote.text
    body = quote.json()
    assert body["suggested_total"] == "3250.00"
    assert body["total"] == "3250.00"
    assert body["status"] == "analysis"
    assert body["ai_analysis"] is None
    assert body["ai_analyzed_at"] is None

    fetched = client.get(f"/api/v1/quotes/{body['id']}")
    assert fetched.status_code == 200
    assert fetched.json()["suggested_total"] == "3250.00"
