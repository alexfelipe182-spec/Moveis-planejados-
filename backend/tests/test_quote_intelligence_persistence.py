from decimal import Decimal

from fastapi.testclient import TestClient

from app.database import SessionLocal
from app.main import app
from app.models import User


def csrf_headers(client: TestClient) -> dict[str, str]:
    token = client.cookies.get("csrf_token")
    assert token
    return {"X-CSRF-Token": token}


def test_quote_creation_persists_predictive_intelligence():
    client = TestClient(app, client=("quote-intelligence-persistence", 50000))
    email = "quote.intelligence.persistence@example.com"
    password = "Senha-Forte-123!"

    registered = client.post(
        "/api/v1/auth/register",
        json={"name": "Intelligence Admin", "email": email, "password": password},
    )
    assert registered.status_code == 201

    db = SessionLocal()
    try:
        user = db.query(User).filter(User.email == email).one()
        user.is_admin = True
        db.commit()
    finally:
        db.close()

    login = client.post(
        "/api/v1/auth/login",
        data={"username": email, "password": password},
    )
    assert login.status_code == 200
    headers = csrf_headers(client)

    customer = client.post(
        "/api/v1/customers",
        json={"name": "Cliente Inteligência Persistida"},
        headers=headers,
    )
    assert customer.status_code == 201

    quote = client.post(
        "/api/v1/quotes",
        json={
            "customer_id": customer.json()["id"],
            "description": "Cozinha com recomendação automática",
            "material_cost": "5000.00",
            "hardware_cost": "1500.00",
            "labor_cost": "2000.00",
            "finishing_cost": "1500.00",
            "profit_margin": "20.00",
        },
        headers=headers,
    )
    assert quote.status_code == 201, quote.text
    data = quote.json()

    assert Decimal(data["recommended_profit_margin"]) >= Decimal("20.00")
    assert Decimal(data["recommended_total"]) >= Decimal(data["suggested_total"])
    assert 0 <= data["risk_score"] <= 100
    assert data["risk_level"] in {"low", "medium", "high"}
    assert data["intelligence_confidence"] in {"low", "medium", "high"}
    assert data["intelligence_sample_size"] >= 0
    assert data["intelligence_analyzed_at"] is not None
