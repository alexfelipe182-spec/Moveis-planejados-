from fastapi.testclient import TestClient

from app.main import app


def csrf_headers(client: TestClient) -> dict[str, str]:
    token = client.cookies.get("csrf_token")
    assert token
    return {"X-CSRF-Token": token}


def register_and_login_business(
    client: TestClient,
    *,
    business_name: str,
    owner_name: str,
    email: str,
) -> None:
    password = "Senha-Forte-123!"
    registered = client.post(
        "/api/v1/auth/register-business",
        json={
            "business_name": business_name,
            "owner_name": owner_name,
            "email": email,
            "password": password,
            "plan_code": "starter",
        },
    )
    assert registered.status_code == 201, registered.text

    login = client.post(
        "/api/v1/auth/login",
        data={"username": email, "password": password},
    )
    assert login.status_code == 200, login.text


def test_two_businesses_cannot_read_modify_or_link_each_others_records():
    with TestClient(app) as business_a, TestClient(app) as business_b:
        register_and_login_business(
            business_a,
            business_name="Marcenaria Isolada A",
            owner_name="Admin Isolado A",
            email="tenant-http-a@example.com",
        )
        register_and_login_business(
            business_b,
            business_name="Marcenaria Isolada B",
            owner_name="Admin Isolado B",
            email="tenant-http-b@example.com",
        )

        customer_a = business_a.post(
            "/api/v1/customers",
            json={
                "name": "Cliente Privado A",
                "email": "cliente-privado-a@example.com",
            },
            headers=csrf_headers(business_a),
        )
        assert customer_a.status_code == 201, customer_a.text
        customer_a_id = customer_a.json()["id"]

        quote_a = business_a.post(
            "/api/v1/quotes",
            json={
                "customer_id": customer_a_id,
                "description": "Orçamento privado A",
                "material_cost": "1000.00",
                "hardware_cost": "200.00",
                "labor_cost": "600.00",
                "finishing_cost": "200.00",
                "profit_margin": "30.00",
            },
            headers=csrf_headers(business_a),
        )
        assert quote_a.status_code == 201, quote_a.text
        quote_a_id = quote_a.json()["id"]

        project_a = business_a.post(
            "/api/v1/projects",
            json={
                "customer_id": customer_a_id,
                "quote_id": quote_a_id,
                "name": "Projeto privado A",
                "description": "Projeto pertencente apenas à marcenaria A",
            },
            headers=csrf_headers(business_a),
        )
        assert project_a.status_code == 201, project_a.text
        project_a_id = project_a.json()["id"]

        customer_b = business_b.post(
            "/api/v1/customers",
            json={"name": "Cliente B"},
            headers=csrf_headers(business_b),
        )
        assert customer_b.status_code == 201, customer_b.text
        customer_b_id = customer_b.json()["id"]

        customers_b = business_b.get("/api/v1/customers")
        assert customers_b.status_code == 200
        assert [row["id"] for row in customers_b.json()] == [customer_b_id]
        assert all(row["name"] != "Cliente Privado A" for row in customers_b.json())

        assert business_b.get(f"/api/v1/customers/{customer_a_id}").status_code == 404
        assert business_b.get(f"/api/v1/quotes/{quote_a_id}").status_code == 404
        assert business_b.get(f"/api/v1/projects/{project_a_id}").status_code == 404

        update_other_customer = business_b.put(
            f"/api/v1/customers/{customer_a_id}",
            json={"name": "Tentativa de invasão"},
            headers=csrf_headers(business_b),
        )
        assert update_other_customer.status_code == 404

        delete_other_customer = business_b.delete(
            f"/api/v1/customers/{customer_a_id}",
            headers=csrf_headers(business_b),
        )
        assert delete_other_customer.status_code == 404

        cross_tenant_quote = business_b.post(
            "/api/v1/quotes",
            json={
                "customer_id": customer_a_id,
                "description": "Tentativa de orçamento cruzado",
                "material_cost": "100.00",
                "profit_margin": "30.00",
            },
            headers=csrf_headers(business_b),
        )
        assert cross_tenant_quote.status_code == 409
        assert "outra marcenaria" in cross_tenant_quote.json()["detail"]

        cross_tenant_project = business_b.post(
            "/api/v1/projects",
            json={
                "customer_id": customer_a_id,
                "quote_id": quote_a_id,
                "name": "Tentativa de projeto cruzado",
            },
            headers=csrf_headers(business_b),
        )
        assert cross_tenant_project.status_code == 409
        assert "outra marcenaria" in cross_tenant_project.json()["detail"]

        own_customer_b = business_b.get(f"/api/v1/customers/{customer_b_id}")
        assert own_customer_b.status_code == 200
        assert own_customer_b.json()["name"] == "Cliente B"

        own_customer_a = business_a.get(f"/api/v1/customers/{customer_a_id}")
        assert own_customer_a.status_code == 200
        assert own_customer_a.json()["name"] == "Cliente Privado A"
