from decimal import Decimal

from fastapi.testclient import TestClient

from app.database import SessionLocal
from app.main import app
from app.models import Customer, User


def csrf_headers(client):
    token = client.cookies.get("csrf_token")
    assert token
    return {"X-CSRF-Token": token}


def admin_client():
    client = TestClient(app)
    email = "quotes.integration@example.com"
    password = "Senha-Forte-123!"

    registered = client.post(
        "/api/v1/auth/register",
        json={"name": "Quotes Integration", "email": email, "password": password},
    )
    assert registered.status_code in (201, 409)

    db = SessionLocal()
    try:
        user = db.query(User).filter(User.email == email).one()
        user.is_admin = True
        customer = db.query(Customer).filter(Customer.email == "quotes.customer@example.com").first()
        if customer is None:
            customer = Customer(name="Cliente Teste", email="quotes.customer@example.com")
            db.add(customer)
            db.flush()
        customer_id = customer.id
        db.commit()
    finally:
        db.close()

    login = client.post(
        "/api/v1/auth/login",
        data={"username": email, "password": password},
    )
    assert login.status_code == 200
    return client, customer_id


def test_quote_estimate_does_not_persist():
    client, _ = admin_client()
    response = client.post(
        "/api/v1/quotes/estimate",
        json={
            "material_cost": "1000.00",
            "hardware_cost": "200.00",
            "labor_cost": "500.00",
            "finishing_cost": "100.00",
            "profit_margin": "30.00",
        },
        headers=csrf_headers(client),
    )
    assert response.status_code == 200
    body = response.json()
    assert Decimal(str(body["base_cost"])) == Decimal("1800.00")
    assert Decimal(str(body["profit_margin"])) == Decimal("30.00")
    assert Decimal(str(body["suggested_total"])) == Decimal("2340.00")
    assert body["ai_analysis"]


def test_create_quote_calculates_and_persists_analysis():
    client, customer_id = admin_client()
    payload = {
        "customer_id": customer_id,
        "description": "Cozinha planejada de integração",
        "measurements": "3,20m x 2,40m",
        "materials": "MDF 18mm",
        "total": "0",
        "material_cost": "2000.00",
        "hardware_cost": "300.00",
        "labor_cost": "700.00",
        "finishing_cost": "200.00",
        "profit_margin": "25.00",
    }
    created = client.post("/api/v1/quotes", json=payload, headers=csrf_headers(client))
    assert created.status_code == 201
    body = created.json()
    assert body["status"] == "analysis"
    assert Decimal(str(body["suggested_total"])) == Decimal("4000.00")
    assert Decimal(str(body["total"])) == Decimal("4000.00")
    assert body["ai_analysis"]
    assert body["ai_analyzed_at"]

    listed = client.get("/api/v1/quotes")
    assert listed.status_code == 200
    assert any(item["id"] == body["id"] for item in listed.json())
