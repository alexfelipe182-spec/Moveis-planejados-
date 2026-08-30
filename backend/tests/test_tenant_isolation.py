from fastapi.testclient import TestClient

from app.database import SessionLocal
from app.main import app
from app.models import User


def csrf_headers(client: TestClient) -> dict[str, str]:
    token = client.cookies.get("csrf_token")
    return {"X-CSRF-Token": token} if token else {}


def register_business(client: TestClient, *, business: str, email: str) -> dict:
    response = client.post(
        "/api/v1/auth/register-business",
        json={
            "business_name": business,
            "owner_name": f"Dono {business}",
            "email": email,
            "password": "Senha-Forte-123!",
            "plan_code": "professional",
        },
    )
    assert response.status_code == 201, response.text
    assert client.post(
        "/api/v1/auth/login",
        data={"username": email, "password": "Senha-Forte-123!"},
    ).status_code == 200
    return response.json()


def test_business_onboarding_creates_isolated_admin_tenant():
    with TestClient(app) as client:
        data = register_business(
            client,
            business="Marcenaria SaaS A",
            email="owner.tenant.a@example.com",
        )
        assert data["tenant"]["plan_code"] == "professional"
        assert data["owner"]["is_admin"] is True
        assert data["owner"]["tenant_id"] == data["tenant"]["id"]

        tenant = client.get("/api/v1/tenant")
        assert tenant.status_code == 200
        assert tenant.json()["id"] == data["tenant"]["id"]


def test_cross_tenant_ids_are_hidden_and_references_are_rejected():
    with TestClient(app) as tenant_a, TestClient(app) as tenant_b:
        register_business(
            tenant_a,
            business="Marcenaria Isolada A",
            email="isolated.a@example.com",
        )
        customer = tenant_a.post(
            "/api/v1/customers",
            json={"name": "Cliente Privado A", "email": "cliente.a@example.com"},
            headers=csrf_headers(tenant_a),
        )
        assert customer.status_code == 201, customer.text
        customer_id = customer.json()["id"]

        register_business(
            tenant_b,
            business="Marcenaria Isolada B",
            email="isolated.b@example.com",
        )
        assert tenant_b.get(f"/api/v1/customers/{customer_id}").status_code == 404
        visible = tenant_b.get("/api/v1/customers")
        assert visible.status_code == 200
        assert all(item["id"] != customer_id for item in visible.json())

        quote = tenant_b.post(
            "/api/v1/quotes",
            json={
                "customer_id": customer_id,
                "description": "Tentativa de referência cruzada",
                "material_cost": "100.00",
                "hardware_cost": "20.00",
                "labor_cost": "50.00",
                "finishing_cost": "10.00",
                "profit_margin": "30.00",
            },
            headers=csrf_headers(tenant_b),
        )
        assert quote.status_code == 404


def test_tenant_admin_cannot_manage_user_from_another_business():
    with TestClient(app) as tenant_a, TestClient(app) as tenant_b:
        data_a = register_business(
            tenant_a,
            business="Equipe Tenant A",
            email="team.a.owner@example.com",
        )
        owner_a_id = data_a["owner"]["id"]

        register_business(
            tenant_b,
            business="Equipe Tenant B",
            email="team.b.owner@example.com",
        )
        response = tenant_b.patch(
            f"/api/v1/admin/users/{owner_a_id}",
            json={"is_active": False},
            headers=csrf_headers(tenant_b),
        )
        assert response.status_code == 404


def test_superadmin_can_see_tenant_catalog_but_normal_admin_cannot():
    with TestClient(app) as client:
        data = register_business(
            client,
            business="Superadmin Bootstrap Test",
            email="superadmin.test@example.com",
        )
        assert client.get("/api/v1/superadmin/tenants").status_code == 403

        db = SessionLocal()
        try:
            user = db.get(User, data["owner"]["id"])
            assert user is not None
            user.is_superadmin = True
            db.commit()
        finally:
            db.close()

        tenants = client.get("/api/v1/superadmin/tenants")
        assert tenants.status_code == 200
        assert any(item["id"] == data["tenant"]["id"] for item in tenants.json())


def test_plan_catalog_is_public():
    with TestClient(app) as client:
        response = client.get("/api/v1/plans")
        assert response.status_code == 200
        codes = {item["code"] for item in response.json()["plans"]}
        assert {"starter", "professional", "business"} <= codes
