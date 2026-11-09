from urllib.parse import parse_qs, urlparse
from uuid import uuid4

from fastapi.testclient import TestClient

from app.main import app


PASSWORD = "Senha-Forte-123!"


def staff_csrf(client: TestClient) -> dict[str, str]:
    token = client.cookies.get("csrf_token")
    return {"X-CSRF-Token": token} if token else {}


def customer_csrf(client: TestClient) -> dict[str, str]:
    token = client.cookies.get("customer_csrf_token")
    return {"X-CSRF-Token": token} if token else {}


def test_customer_portal_invitation_activation_quote_decision_project_and_messages():
    suffix = uuid4().hex
    owner_email = f"portal.owner.{suffix}@example.com"
    customer_email = f"portal.customer.{suffix}@example.com"

    with TestClient(app) as client:
        registered = client.post(
            "/api/v1/auth/register-business",
            json={
                "business_name": f"Marcenaria Portal {suffix[:8]}",
                "owner_name": "Dono Portal",
                "email": owner_email,
                "password": PASSWORD,
                "plan_code": "professional",
            },
        )
        assert registered.status_code == 201, registered.text
        tenant_slug = registered.json()["tenant"]["slug"]
        assert client.post(
            "/api/v1/auth/login", data={"username": owner_email, "password": PASSWORD}
        ).status_code == 200

        customer = client.post(
            "/api/v1/customers",
            json={"name": "Cliente Portal", "email": customer_email, "phone": "+5513999999999"},
            headers=staff_csrf(client),
        )
        assert customer.status_code == 201, customer.text
        customer_id = customer.json()["id"]

        quote = client.post(
            "/api/v1/quotes",
            json={
                "customer_id": customer_id,
                "description": "Cozinha do portal",
                "material_cost": "1000.00",
                "hardware_cost": "200.00",
                "labor_cost": "500.00",
                "finishing_cost": "100.00",
                "profit_margin": "30.00",
            },
            headers=staff_csrf(client),
        )
        assert quote.status_code == 201, quote.text
        quote_id = quote.json()["id"]
        assert client.patch(
            f"/api/v1/quotes/{quote_id}/decision",
            json={"status": "approved"},
            headers=staff_csrf(client),
        ).status_code == 200
        assert client.post(
            f"/api/v1/quotes/{quote_id}/shared", headers=staff_csrf(client)
        ).status_code == 200

        invite = client.post(
            f"/api/v1/customer-portal/admin/customers/{customer_id}/invite",
            headers=staff_csrf(client),
        )
        assert invite.status_code == 200, invite.text
        invitation_url = invite.json()["invitation_url"]
        invitation_token = parse_qs(urlparse(invitation_url).query)["customer_portal_token"][0]

        activation = client.post(
            "/api/v1/customer-portal/activate",
            json={"token": invitation_token, "password": PASSWORD},
        )
        assert activation.status_code == 200, activation.text
        assert activation.json()["tenant"]["slug"] == tenant_slug
        assert client.cookies.get("customer_access_token")
        assert client.cookies.get("customer_csrf_token")

        me = client.get("/api/v1/customer-portal/me")
        assert me.status_code == 200, me.text
        assert me.json()["customer"]["id"] == customer_id

        visible_quotes = client.get("/api/v1/customer-portal/quotes")
        assert visible_quotes.status_code == 200
        assert [item["id"] for item in visible_quotes.json()] == [quote_id]
        assert "material_cost" not in visible_quotes.json()[0]

        missing_csrf = client.patch(
            f"/api/v1/customer-portal/quotes/{quote_id}/decision",
            json={"status": "accepted"},
        )
        assert missing_csrf.status_code == 403

        accepted = client.patch(
            f"/api/v1/customer-portal/quotes/{quote_id}/decision",
            json={"status": "accepted"},
            headers=customer_csrf(client),
        )
        assert accepted.status_code == 200, accepted.text
        assert accepted.json()["status"] == "accepted"

        projects = client.get("/api/v1/customer-portal/projects")
        assert projects.status_code == 200, projects.text
        assert len(projects.json()) == 1
        assert projects.json()[0]["quote_id"] == quote_id

        message = client.post(
            "/api/v1/customer-portal/messages",
            json={"body": "Gostaria de confirmar a data da medição.", "project_id": projects.json()[0]["id"]},
            headers=customer_csrf(client),
        )
        assert message.status_code == 201, message.text
        assert message.json()["author_type"] == "customer"

        reply = client.post(
            f"/api/v1/customer-portal/admin/customers/{customer_id}/messages",
            json={"body": "Entraremos em contato para agendar."},
            headers=staff_csrf(client),
        )
        assert reply.status_code == 201, reply.text
        messages = client.get("/api/v1/customer-portal/messages")
        assert [item["author_type"] for item in messages.json()] == ["customer", "staff"]

        logout = client.post(
            "/api/v1/customer-portal/logout", headers=customer_csrf(client)
        )
        assert logout.status_code == 204
        assert client.get("/api/v1/customer-portal/me").status_code == 401

        relogin = client.post(
            "/api/v1/customer-portal/login",
            json={"business_slug": tenant_slug, "email": customer_email, "password": PASSWORD},
        )
        assert relogin.status_code == 200, relogin.text
        assert relogin.json()["customer"]["id"] == customer_id
