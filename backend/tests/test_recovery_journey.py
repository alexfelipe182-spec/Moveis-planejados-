"""The owner's requested registration-to-persistence acceptance journey."""

from uuid import uuid4

from fastapi.testclient import TestClient

from app.main import app


def test_new_business_trial_customer_product_quote_and_relogin():
    email = f"recovery.{uuid4().hex}@example.com"
    password = "Recovery-Test-Only-2026!"
    with TestClient(app) as client:
        registered = client.post("/api/v1/auth/register-business", json={
            "business_name": "Marcenaria teste de recuperacao",
            "owner_name": "Responsavel teste", "email": email,
            "password": password, "plan_code": "professional",
        })
        assert registered.status_code == 201, registered.text
        assert registered.json()["owner"]["is_admin"] is True

        def login():
            response = client.post("/api/v1/auth/login", data={"username": email, "password": password})
            assert response.status_code == 200, response.text

        def create(path, payload):
            response = client.post("/api/v1" + path, json=payload,
                                   headers={"X-CSRF-Token": client.cookies.get("csrf_token")})
            assert response.status_code == 201, response.text
            return response.json()

        login()
        subscription = client.get("/api/v1/billing/subscription")
        assert subscription.status_code == 200
        assert subscription.json()["access_allowed"] is True
        assert subscription.json()["trial_days_remaining"] == 30
        assert client.get("/api/v1/tenant").status_code == 200
        customer = create("/customers", {"name": "Cliente de teste recuperacao"})
        category = create("/categories", {"name": "Moveis planejados"})
        product = create("/products", {"category_id": category["id"], "name": "Armario teste", "price": "1200.00"})
        quote = create("/quotes", {
            "customer_id": customer["id"], "description": "Armario teste recuperacao",
            "material_cost": "500.00", "hardware_cost": "100.00",
            "labor_cost": "200.00", "finishing_cost": "0.00", "profit_margin": "30.00",
        })
        logout = client.post("/api/v1/auth/logout", headers={"X-CSRF-Token": client.cookies.get("csrf_token")})
        assert logout.status_code == 204
        assert client.get(f"/api/v1/quotes/{quote['id']}").status_code == 401
        login()
        for resource, record in (("customers", customer), ("products", product), ("quotes", quote)):
            response = client.get(f"/api/v1/{resource}/{record['id']}")
            assert response.status_code == 200, response.text
            assert response.json()["id"] == record["id"]
        assert client.get(f"/api/v1/quotes/{quote['id']}").json()["total"] == quote["total"]
