import hashlib
import hmac
import json
import os
import time
from unittest.mock import patch

from fastapi.testclient import TestClient

from app.main import app

PASSWORD = "Senha-Forte-123!"


def csrf_headers(client: TestClient) -> dict[str, str]:
    token = client.cookies.get("csrf_token")
    return {"X-CSRF-Token": token} if token else {}


def register_and_login(client: TestClient, email: str, plan_code: str = "starter") -> None:
    registered = client.post(
        "/api/v1/auth/register-business",
        json={
            "business_name": "Marcenaria Comercial SaaS",
            "owner_name": "Dono Comercial",
            "email": email,
            "password": PASSWORD,
            "plan_code": plan_code,
        },
    )
    assert registered.status_code == 201, registered.text
    logged = client.post("/api/v1/auth/login", data={"username": email, "password": PASSWORD})
    assert logged.status_code == 200, logged.text


def test_plan_catalog_subscription_usage_and_guided_onboarding():
    with TestClient(app) as client:
        register_and_login(client, "commercial.saas@example.com")

        plans = client.get("/api/v1/plans")
        assert plans.status_code == 200
        assert {item["code"] for item in plans.json()} == {"starter", "professional", "business"}

        status = client.get("/api/v1/billing/subscription")
        assert status.status_code == 200, status.text
        assert status.json()["plan_code"] == "starter"
        assert status.json()["usage"]["limits"]["users"] == 3

        onboarding = client.get("/api/v1/onboarding")
        assert onboarding.status_code == 200
        assert onboarding.json()["completed"] is False

        updated = client.patch(
            "/api/v1/onboarding",
            json={
                "phone": "11999999999",
                "city": "Praia Grande",
                "state": "SP",
                "default_profit_margin": "35.00",
                "step": 4,
                "complete": True,
            },
            headers=csrf_headers(client),
        )
        assert updated.status_code == 200, updated.text
        assert updated.json()["completed"] is True
        assert updated.json()["business"]["city"] == "Praia Grande"
        assert updated.json()["business"]["default_profit_margin"] == 35.0


def test_checkout_requires_billing_configuration():
    with TestClient(app) as client:
        register_and_login(client, "billing.not.configured@example.com")
        with patch.dict(os.environ, {}, clear=False):
            os.environ.pop("STRIPE_PRICE_STARTER", None)
            response = client.post(
                "/api/v1/billing/checkout",
                json={"plan_code": "starter"},
                headers=csrf_headers(client),
            )
        assert response.status_code == 503


def test_signed_subscription_webhook_updates_tenant_plan():
    secret = "whsec_test_commercial_saas"
    event = {
        "type": "customer.subscription.updated",
        "data": {
            "object": {
                "id": "sub_test_commercial",
                "customer": "cus_test_commercial",
                "status": "active",
                "current_period_end": int(time.time()) + 3600,
                "cancel_at_period_end": False,
                "metadata": {},
            }
        },
    }

    with TestClient(app) as client:
        registered = client.post(
            "/api/v1/auth/register-business",
            json={
                "business_name": "Marcenaria Webhook SaaS",
                "owner_name": "Dono Webhook",
                "email": "webhook.saas@example.com",
                "password": PASSWORD,
                "plan_code": "starter",
            },
        )
        assert registered.status_code == 201
        tenant_id = registered.json()["tenant"]["id"]
        event["data"]["object"]["metadata"] = {"tenant_id": str(tenant_id), "plan_code": "professional"}
        raw = json.dumps(event, separators=(",", ":")).encode()
        timestamp = str(int(time.time()))
        signature = hmac.new(secret.encode(), timestamp.encode() + b"." + raw, hashlib.sha256).hexdigest()

        with patch.dict(os.environ, {"STRIPE_WEBHOOK_SECRET": secret}):
            webhook = client.post(
                "/api/v1/billing/webhook",
                content=raw,
                headers={"Stripe-Signature": f"t={timestamp},v1={signature}", "Content-Type": "application/json"},
            )
        assert webhook.status_code == 200, webhook.text

        login = client.post(
            "/api/v1/auth/login",
            data={"username": "webhook.saas@example.com", "password": PASSWORD},
        )
        assert login.status_code == 200
        tenant = client.get("/api/v1/tenant")
        assert tenant.status_code == 200
        assert tenant.json()["plan_code"] == "professional"
