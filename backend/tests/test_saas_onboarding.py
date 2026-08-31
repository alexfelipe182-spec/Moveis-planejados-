from fastapi.testclient import TestClient

from app.database import SessionLocal
from app.main import app
from app.models import Tenant

PASSWORD = "Senha-Forte-123!"


def csrf_headers(client: TestClient) -> dict[str, str]:
    token = client.cookies.get("csrf_token")
    return {"X-CSRF-Token": token} if token else {}


def register_business(
    client: TestClient,
    *,
    business_name: str,
    owner_name: str,
    email: str,
    plan_code: str = "professional",
) -> dict:
    response = client.post(
        "/api/v1/auth/register-business",
        json={
            "business_name": business_name,
            "owner_name": owner_name,
            "email": email,
            "password": PASSWORD,
            "plan_code": plan_code,
        },
    )
    assert response.status_code == 201, response.text
    body = response.json()
    assert body["tenant"]["name"] == business_name
    assert body["tenant"]["plan_code"] == plan_code
    assert body["owner"]["email"] == email
    assert body["owner"]["is_admin"] is True
    return body


def login(client: TestClient, email: str) -> None:
    response = client.post(
        "/api/v1/auth/login",
        data={"username": email, "password": PASSWORD},
    )
    assert response.status_code == 200, response.text


def test_business_onboarding_creates_admin_and_editable_tenant_profile():
    with TestClient(app) as client:
        registered = register_business(
            client,
            business_name="Marcenaria SaaS Onboarding",
            owner_name="Dono SaaS",
            email="owner.saas.onboarding@example.com",
            plan_code="business",
        )
        login(client, "owner.saas.onboarding@example.com")

        tenant = client.get("/api/v1/tenant")
        assert tenant.status_code == 200
        assert tenant.json()["id"] == registered["tenant"]["id"]
        assert tenant.json()["plan_code"] == "business"

        updated = client.patch(
            "/api/v1/tenant",
            json={"name": "Marcenaria SaaS Atualizada"},
            headers=csrf_headers(client),
        )
        assert updated.status_code == 200, updated.text
        assert updated.json()["name"] == "Marcenaria SaaS Atualizada"
        assert updated.json()["slug"] == registered["tenant"]["slug"]


def test_two_businesses_are_isolated_across_customers_quotes_and_team():
    with TestClient(app) as client_a, TestClient(app) as client_b:
        business_a = register_business(
            client_a,
            business_name="Marcenaria SaaS Isolada A",
            owner_name="Owner A",
            email="owner.saas.a@example.com",
        )
        business_b = register_business(
            client_b,
            business_name="Marcenaria SaaS Isolada B",
            owner_name="Owner B",
            email="owner.saas.b@example.com",
        )
        assert business_a["tenant"]["id"] != business_b["tenant"]["id"]
        assert business_a["tenant"]["slug"] != business_b["tenant"]["slug"]

        login(client_a, "owner.saas.a@example.com")
        customer_a = client_a.post(
            "/api/v1/customers",
            json={"name": "Cliente exclusivo A", "email": "cliente.saas.a@example.com"},
            headers=csrf_headers(client_a),
        )
        assert customer_a.status_code == 201
        customer_a_id = customer_a.json()["id"]

        quote_a = client_a.post(
            "/api/v1/quotes",
            json={
                "customer_id": customer_a_id,
                "description": "Cozinha exclusiva A",
                "material_cost": "1000.00",
                "hardware_cost": "200.00",
                "labor_cost": "500.00",
                "finishing_cost": "100.00",
                "profit_margin": "30.00",
            },
            headers=csrf_headers(client_a),
        )
        assert quote_a.status_code == 201, quote_a.text
        quote_a_id = quote_a.json()["id"]

        login(client_b, "owner.saas.b@example.com")
        assert client_b.get("/api/v1/customers").json() == []
        assert client_b.get(f"/api/v1/customers/{customer_a_id}").status_code == 404
        assert client_b.get(f"/api/v1/quotes/{quote_a_id}").status_code == 404

        cross_quote = client_b.post(
            "/api/v1/quotes",
            json={
                "customer_id": customer_a_id,
                "description": "Tentativa de cruzar tenant",
                "material_cost": "100.00",
                "hardware_cost": "0.00",
                "labor_cost": "100.00",
                "finishing_cost": "0.00",
                "profit_margin": "30.00",
            },
            headers=csrf_headers(client_b),
        )
        assert cross_quote.status_code == 409

        team_user = client_b.post(
            "/api/v1/admin/users",
            json={
                "name": "Equipe B",
                "email": "team.saas.b@example.com",
                "password": PASSWORD,
                "is_admin": False,
            },
            headers=csrf_headers(client_b),
        )
        assert team_user.status_code == 201, team_user.text

        users_b = client_b.get("/api/v1/admin/users")
        assert users_b.status_code == 200
        emails_b = {item["email"] for item in users_b.json()}
        assert "owner.saas.b@example.com" in emails_b
        assert "team.saas.b@example.com" in emails_b
        assert "owner.saas.a@example.com" not in emails_b


def test_inactive_tenant_blocks_existing_session():
    with TestClient(app) as client:
        registered = register_business(
            client,
            business_name="Marcenaria Suspensa",
            owner_name="Owner Suspenso",
            email="owner.suspended@example.com",
        )
        login(client, "owner.suspended@example.com")
        assert client.get("/api/v1/me").status_code == 200

        db = SessionLocal()
        try:
            tenant = db.get(Tenant, registered["tenant"]["id"])
            assert tenant is not None
            tenant.is_active = False
            db.commit()
        finally:
            db.close()

        blocked = client.get("/api/v1/me")
        assert blocked.status_code == 403
        assert blocked.json()["detail"] == "Marcenaria indisponível"
