import pytest
from fastapi.testclient import TestClient

from app.database import SessionLocal
from app.main import app
from app.models import User


@pytest.fixture
def client():
    with TestClient(app) as test_client:
        yield test_client


def csrf_headers(client: TestClient) -> dict[str, str]:
    token = client.cookies.get("csrf_token")
    return {"X-CSRF-Token": token} if token else {}


def register_and_promote(client: TestClient, *, name: str, email: str, password: str) -> int:
    response = client.post(
        "/api/v1/auth/register",
        json={"name": name, "email": email, "password": password},
    )
    assert response.status_code == 201

    db = SessionLocal()
    try:
        user = db.query(User).filter(User.email == email).one()
        assert user.tenant_id is not None
        tenant_id = user.tenant_id
        user.is_admin = True
        db.commit()
        return tenant_id
    finally:
        db.close()


def login(client: TestClient, email: str, password: str) -> None:
    client.cookies.clear()
    response = client.post(
        "/api/v1/auth/login",
        data={"username": email, "password": password},
    )
    assert response.status_code == 200


def test_customers_are_isolated_between_tenants(client: TestClient):
    password = "Senha-Forte-123!"
    email_a = "tenant.a@example.com"
    email_b = "tenant.b@example.com"

    tenant_a = register_and_promote(
        client,
        name="Marcenaria A",
        email=email_a,
        password=password,
    )
    tenant_b = register_and_promote(
        client,
        name="Marcenaria B",
        email=email_b,
        password=password,
    )
    assert tenant_a != tenant_b

    login(client, email_a, password)
    created_a = client.post(
        "/api/v1/customers",
        json={"name": "Cliente exclusivo A", "email": "cliente.a@example.com"},
        headers=csrf_headers(client),
    )
    assert created_a.status_code == 201
    customer_a_id = created_a.json()["id"]

    list_a = client.get("/api/v1/customers")
    assert list_a.status_code == 200
    assert [item["name"] for item in list_a.json()] == ["Cliente exclusivo A"]

    login(client, email_b, password)
    list_b_before = client.get("/api/v1/customers")
    assert list_b_before.status_code == 200
    assert list_b_before.json() == []

    assert client.get(f"/api/v1/customers/{customer_a_id}").status_code == 404
    assert (
        client.put(
            f"/api/v1/customers/{customer_a_id}",
            json={"name": "Tentativa B"},
            headers=csrf_headers(client),
        ).status_code
        == 404
    )
    assert (
        client.delete(
            f"/api/v1/customers/{customer_a_id}",
            headers=csrf_headers(client),
        ).status_code
        == 404
    )

    # IDs de outro tenant também não podem ser usados como referências em
    # novos registros. Isso bloqueia ataques que tentem adivinhar customer_id.
    cross_tenant_quote = client.post(
        "/api/v1/quotes",
        json={
            "customer_id": customer_a_id,
            "description": "Tentativa de referenciar cliente da Marcenaria A",
            "material_cost": "100.00",
            "hardware_cost": "0.00",
            "labor_cost": "100.00",
            "finishing_cost": "0.00",
            "profit_margin": "30.00",
        },
        headers=csrf_headers(client),
    )
    assert cross_tenant_quote.status_code == 409

    created_b = client.post(
        "/api/v1/customers",
        json={"name": "Cliente exclusivo B", "email": "cliente.b@example.com"},
        headers=csrf_headers(client),
    )
    assert created_b.status_code == 201
    customer_b_id = created_b.json()["id"]

    quote_b = client.post(
        "/api/v1/quotes",
        json={
            "customer_id": customer_b_id,
            "description": "Orçamento exclusivo B",
            "material_cost": "500.00",
            "hardware_cost": "100.00",
            "labor_cost": "300.00",
            "finishing_cost": "100.00",
            "profit_margin": "30.00",
        },
        headers=csrf_headers(client),
    )
    assert quote_b.status_code == 201
    quote_b_id = quote_b.json()["id"]

    list_b_after = client.get("/api/v1/customers")
    assert list_b_after.status_code == 200
    assert [item["name"] for item in list_b_after.json()] == ["Cliente exclusivo B"]

    login(client, email_a, password)
    list_a_after = client.get("/api/v1/customers")
    assert list_a_after.status_code == 200
    assert [item["name"] for item in list_a_after.json()] == ["Cliente exclusivo A"]
    assert client.get(f"/api/v1/quotes/{quote_b_id}").status_code == 404
