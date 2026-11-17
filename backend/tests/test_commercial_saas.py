from sample_data import unique_email

import hashlib
import hmac
import json
import os
import time
from datetime import datetime, timedelta
from unittest.mock import patch
from uuid import uuid4

import httpx
from fastapi.testclient import TestClient

from app.database import SessionLocal
from app.main import app
from app.models import Subscription, Tenant, User

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
        register_and_login(client, unique_email("commercial.saas@example.com"))

        plans = client.get("/api/v1/plans")
        assert plans.status_code == 200
        assert {item["code"] for item in plans.json()} == {"starter", "professional", "business"}

        status = client.get("/api/v1/billing/subscription")
        assert status.status_code == 200, status.text
        payload = status.json()
        assert payload["plan_code"] == "starter"
        assert payload["access_allowed"] is True
        assert payload["subscription"]["status"] == "trialing"
        assert payload["subscription"]["provider"] == "manual"
        assert payload["subscription"]["trial_end"] is not None
        assert payload["trial_days_remaining"] == 30
        assert payload["can_cancel_trial"] is True
        assert payload["usage"]["limits"]["users"] == 3

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


def test_expired_trial_blocks_platform_but_keeps_account_and_billing_accessible():
    email = unique_email("trial.expired@example.com")
    with TestClient(app) as client:
        register_and_login(client, email)
        with SessionLocal() as db:
            user = db.query(User).filter(User.email == email).one()
            subscription = db.query(Subscription).filter(Subscription.tenant_id == user.tenant_id).one()
            subscription.trial_end = datetime.now() - timedelta(minutes=1)
            db.commit()

        me = client.get("/api/v1/me")
        assert me.status_code == 200, me.text

        billing = client.get("/api/v1/billing/subscription")
        assert billing.status_code == 200, billing.text
        assert billing.json()["access_allowed"] is False
        assert billing.json()["subscription"]["status"] == "trial_expired"
        assert billing.json()["trial_days_remaining"] == 0

        blocked = client.get("/api/v1/admin/dashboard")
        assert blocked.status_code == 402, blocked.text
        assert blocked.json()["detail"]["code"] == "trial_expired"

        stripe_response = type(
            "StripeResponse",
            (),
            {
                "raise_for_status": lambda self: None,
                "json": lambda self: {
                    "id": "cs_after_trial",
                    "url": "https://checkout.stripe.com/c/pay/cs_after_trial",
                },
            },
        )()
        with (
            patch.dict(
                os.environ,
                {
                    "STRIPE_SECRET_KEY": "sk_test_mock_only_not_real",
                    "STRIPE_PRICE_STARTER": "price_starter_test",
                },
            ),
            patch("app.api.commercial.httpx.post", return_value=stripe_response) as stripe_post,
        ):
            checkout = client.post(
                "/api/v1/billing/checkout",
                json={"plan_code": "starter"},
                headers=csrf_headers(client),
            )

        assert checkout.status_code == 200, checkout.text
        checkout_form = stripe_post.call_args.kwargs["data"]
        assert "subscription_data[trial_end]" not in checkout_form
        assert "subscription_data[trial_period_days]" not in checkout_form


def test_checkout_requires_billing_configuration():
    with TestClient(app) as client:
        register_and_login(client, unique_email("billing.not.configured@example.com"))
        with patch.dict(os.environ, {}, clear=False):
            os.environ.pop("STRIPE_PRICE_STARTER", None)
            response = client.post(
                "/api/v1/billing/checkout",
                json={"plan_code": "starter"},
                headers=csrf_headers(client),
            )
        assert response.status_code == 503


def test_owner_can_desist_from_manual_trial_without_deleting_account():
    with TestClient(app) as client:
        register_and_login(client, "trial.desist.manual@example.com")
        missing_confirmation = client.post(
            "/api/v1/billing/cancel-trial", json={"confirmation": ""}, headers=csrf_headers(client)
        )
        assert missing_confirmation.status_code == 422

        canceled = client.post(
            "/api/v1/billing/cancel-trial", json={"confirmation": "DESISTIR"}, headers=csrf_headers(client)
        )
        assert canceled.status_code == 200, canceled.text
        assert canceled.json() == {"status": "canceled", "access_allowed": False}
        assert client.get("/api/v1/billing/subscription").json()["subscription"]["status"] == "canceled"
        assert client.get("/api/v1/billing/subscription").json()["can_cancel_trial"] is False
        assert client.get("/api/v1/me").status_code == 200
        assert client.get("/api/v1/admin/dashboard").status_code == 402
        assert client.post(
            "/api/v1/billing/cancel-trial", json={"confirmation": "DESISTIR"}, headers=csrf_headers(client)
        ).status_code == 409


def test_stripe_trial_is_canceled_at_provider_before_access_is_closed():
    email = "trial.desist.stripe@example.com"
    with TestClient(app) as client:
        register_and_login(client, email)
        with SessionLocal() as db:
            user = db.query(User).filter(User.email == email).one()
            subscription = db.query(Subscription).filter(Subscription.tenant_id == user.tenant_id).one()
            subscription.provider = "stripe"
            subscription.provider_customer_id = "cus_desist_test"
            subscription.provider_subscription_id = "sub_desist_test"
            db.commit()

        stripe_response = type("StripeResponse", (), {
            "raise_for_status": lambda self: None,
            "json": lambda self: {"id": "sub_desist_test", "status": "canceled"},
        })()
        with (
            patch.dict(os.environ, {"STRIPE_SECRET_KEY": "sk_test_mock_only_not_real"}),
            patch("app.api.commercial.httpx.delete", return_value=stripe_response) as stripe_delete,
        ):
            canceled = client.post(
                "/api/v1/billing/cancel-trial", json={"confirmation": "DESISTIR"}, headers=csrf_headers(client)
            )
        assert canceled.status_code == 200, canceled.text
        assert stripe_delete.call_args.args[0].endswith("/sub_desist_test")
        assert stripe_delete.call_args.kwargs["data"] == {"invoice_now": "false", "prorate": "false"}
        assert client.get("/api/v1/billing/subscription").json()["subscription"]["status"] == "canceled"


def test_stripe_error_keeps_trial_active_and_does_not_claim_cancellation():
    email = "trial.desist.stripe.error@example.com"
    with TestClient(app) as client:
        register_and_login(client, email)
        with SessionLocal() as db:
            user = db.query(User).filter(User.email == email).one()
            subscription = db.query(Subscription).filter(Subscription.tenant_id == user.tenant_id).one()
            subscription.provider = "stripe"
            subscription.provider_customer_id = "cus_desist_error"
            subscription.provider_subscription_id = "sub_desist_error"
            db.commit()

        with (
            patch.dict(os.environ, {"STRIPE_SECRET_KEY": "sk_test_mock_only_not_real"}),
            patch("app.api.commercial.httpx.delete", side_effect=httpx.ConnectError("offline")),
        ):
            response = client.post(
                "/api/v1/billing/cancel-trial", json={"confirmation": "DESISTIR"}, headers=csrf_headers(client)
            )
        assert response.status_code == 502
        billing = client.get("/api/v1/billing/subscription").json()
        assert billing["subscription"]["status"] == "trialing"
        assert billing["can_cancel_trial"] is True


def test_checkout_creates_stripe_session_without_exposing_secret_and_preserves_trial():
    with TestClient(app) as client:
        register_and_login(client, unique_email("billing.checkout@example.com"))
        stripe_response = type(
            "StripeResponse",
            (),
            {
                "raise_for_status": lambda self: None,
                "json": lambda self: {
                    "id": "cs_live_checkout",
                    "url": "https://checkout.stripe.com/c/pay/cs_live_checkout",
                },
            },
        )()
        with (
            patch.dict(
                os.environ,
                {
                    "STRIPE_SECRET_KEY": "sk_test_mock_only_not_real",
                    "STRIPE_PRICE_PROFESSIONAL": "price_professional_test",
                },
            ),
            patch("app.api.commercial.httpx.post", return_value=stripe_response) as stripe_post,
        ):
            response = client.post(
                "/api/v1/billing/checkout",
                json={"plan_code": "professional"},
                headers=csrf_headers(client),
            )

        assert response.status_code == 200, response.text
        assert response.json() == {
            "checkout_url": "https://checkout.stripe.com/c/pay/cs_live_checkout",
            "session_id": "cs_live_checkout",
        }
        call = stripe_post.call_args
        assert call.args[0] == "https://api.stripe.com/v1/checkout/sessions"
        assert call.kwargs["data"]["line_items[0][price]"] == "price_professional_test"
        assert call.kwargs["data"]["subscription_data[metadata][plan_code]"] == "professional"
        assert "subscription_data[trial_end]" in call.kwargs["data"]
        assert call.kwargs["headers"] == {"Authorization": "Bearer sk_test_mock_only_not_real"}
        assert "sk_live" not in response.text


def test_active_subscription_uses_billing_portal_and_blocks_duplicate_checkout():
    email = unique_email("billing.portal@example.com")
    customer_id = f"cus_portal_test_{uuid4().hex}"
    subscription_id = f"sub_portal_test_{uuid4().hex}"
    with TestClient(app) as client:
        register_and_login(client, email)
        with SessionLocal() as db:
            user = db.query(User).filter(User.email == email).one()
            tenant = db.get(Tenant, user.tenant_id)
            subscription = db.query(Subscription).filter(Subscription.tenant_id == tenant.id).one()
            subscription.provider = "stripe"
            subscription.provider_customer_id = customer_id
            subscription.provider_subscription_id = subscription_id
            subscription.plan_code = "professional"
            subscription.status = "active"
            subscription.current_period_end = datetime.now() + timedelta(days=30)
            subscription.trial_end = None
            tenant.plan_code = "professional"
            db.commit()

        with patch.dict(
            os.environ,
            {
                "STRIPE_SECRET_KEY": "sk_test_mock_only_not_real",
                "STRIPE_PRICE_BUSINESS": "price_business_test",
            },
        ):
            duplicate = client.post(
                "/api/v1/billing/checkout",
                json={"plan_code": "business"},
                headers=csrf_headers(client),
            )
        assert duplicate.status_code == 409
        assert "portal de cobrança" in duplicate.json()["detail"]

        stripe_response = type(
            "StripeResponse",
            (),
            {
                "raise_for_status": lambda self: None,
                "json": lambda self: {"url": "https://billing.stripe.com/p/session/test"},
            },
        )()
        with (
            patch.dict(os.environ, {"STRIPE_SECRET_KEY": "sk_test_mock_only_not_real"}),
            patch("app.api.commercial.httpx.post", return_value=stripe_response) as stripe_post,
        ):
            portal = client.post("/api/v1/billing/portal", headers=csrf_headers(client))

        assert portal.status_code == 200, portal.text
        assert portal.json() == {"portal_url": "https://billing.stripe.com/p/session/test"}
        assert stripe_post.call_args.args[0] == "https://api.stripe.com/v1/billing_portal/sessions"
        assert stripe_post.call_args.kwargs["data"]["customer"] == customer_id


def test_signed_subscription_webhook_updates_tenant_plan_and_trial_deadline():
    secret = "whsec_test_commercial_saas"
    stripe_trial_end = int(time.time()) + 10 * 86400
    event = {
        "type": "customer.subscription.updated",
        "data": {
            "object": {
                "id": f"sub_test_commercial_{uuid4().hex}",
                "customer": f"cus_test_commercial_{uuid4().hex}",
                "status": "trialing",
                "current_period_end": int(time.time()) + 30 * 86400,
                "trial_end": stripe_trial_end,
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
                "email": unique_email("webhook.saas@example.com"),
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
            data={"username": unique_email("webhook.saas@example.com"), "password": PASSWORD},
        )
        assert login.status_code == 200
        tenant = client.get("/api/v1/tenant")
        assert tenant.status_code == 200
        assert tenant.json()["plan_code"] == "professional"

        billing = client.get("/api/v1/billing/subscription")
        assert billing.status_code == 200
        assert billing.json()["subscription"]["provider"] == "stripe"
        assert billing.json()["subscription"]["status"] == "trialing"
        assert billing.json()["subscription"]["trial_days_remaining"] in {9, 10}


def test_management_keeps_business_data_scoped_and_platform_data_owner_only(monkeypatch):
    owner_email = "management.platform@example.com"
    monkeypatch.setenv("PLATFORM_OWNER_EMAILS", owner_email)
    with TestClient(app) as owner:
        register_and_login(owner, owner_email)
        created = owner.post(
            "/api/v1/customers", json={"name": "Cliente privado da gestão"}, headers=csrf_headers(owner)
        )
        assert created.status_code == 201, created.text
        assert owner.get("/api/v1/admin/management").json()["customers"] == 1
        assert owner.get("/api/v1/platform/access").json()["is_platform_owner"] is True

        with TestClient(app) as business:
            register_and_login(business, "management.business@example.com")
            response = business.get("/api/v1/admin/management")
            assert response.status_code == 200, response.text
            assert response.json()["customers"] == 0
            assert business.get("/api/v1/platform/access").json()["is_platform_owner"] is False
            assert business.get("/api/v1/platform/dashboard").status_code == 403

        response = owner.get("/api/v1/platform/dashboard")
        assert response.status_code == 200, response.text
        assert response.json()["subscription_statuses"]["trialing"] >= 2
