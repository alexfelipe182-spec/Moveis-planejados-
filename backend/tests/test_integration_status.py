import os
from unittest.mock import patch

from fastapi.testclient import TestClient

from app.core.config import settings
from app.main import app


PASSWORD = "Senha-Forte-123!"
PLACEHOLDER = "test-only-placeholder"


def register_admin(client: TestClient, email: str) -> None:
    registered = client.post(
        "/api/v1/auth/register-business",
        json={
            "business_name": "Marcenaria Diagnóstico",
            "owner_name": "Admin Diagnóstico",
            "email": email,
            "password": PASSWORD,
            "plan_code": "starter",
        },
    )
    assert registered.status_code == 201, registered.text
    login = client.post(
        "/api/v1/auth/login",
        data={"username": email, "password": PASSWORD},
    )
    assert login.status_code == 200, login.text


def test_integration_status_requires_admin_authentication():
    with TestClient(app) as client:
        response = client.get("/api/v1/admin/integrations")

    assert response.status_code == 401


def test_integration_status_reports_readiness_without_exposing_values(monkeypatch):
    monkeypatch.setattr(settings, "smtp_host", "smtp.example.com")
    monkeypatch.setattr(settings, "smtp_user", "mailer@example.com")
    monkeypatch.setattr(settings, "smtp_password", PLACEHOLDER)
    monkeypatch.setattr(settings, "smtp_from", "Multi-Marcenarias <mailer@example.com>")
    monkeypatch.setattr(settings, "smtp_starttls", True)
    monkeypatch.setattr(settings, "smtp_use_ssl", False)

    env = {
        "OPENAI_API_KEY": PLACEHOLDER,
        "OPENAI_MODEL": "test-model",
        "STRIPE_SECRET_KEY": PLACEHOLDER,
        "STRIPE_WEBHOOK_SECRET": PLACEHOLDER,
        "STRIPE_PRICE_STARTER": "test-price-starter",
        "STRIPE_PRICE_PROFESSIONAL": "test-price-professional",
        "STRIPE_PRICE_BUSINESS": "test-price-business",
    }
    with patch.dict(os.environ, env, clear=False):
        with TestClient(app) as client:
            register_admin(client, "integration.status@example.com")
            response = client.get("/api/v1/admin/integrations")

    assert response.status_code == 200, response.text
    payload = response.json()
    assert payload["openai"] == {"configured": True, "model": "test-model"}
    assert payload["email"]["configured"] is True
    assert payload["email"]["transport"] == "starttls"
    assert payload["stripe"]["checkout_ready"] is True
    assert payload["stripe"]["fully_configured"] is True
    assert all(payload["stripe"]["prices_configured"].values())
    assert PLACEHOLDER not in response.text


def test_integration_status_marks_optional_services_as_pending(monkeypatch):
    monkeypatch.setattr(settings, "smtp_host", None)
    monkeypatch.setattr(settings, "smtp_user", None)
    monkeypatch.setattr(settings, "smtp_password", None)
    monkeypatch.setattr(settings, "smtp_from", None)

    empty_env = {
        "OPENAI_API_KEY": "",
        "STRIPE_SECRET_KEY": "",
        "STRIPE_WEBHOOK_SECRET": "",
        "STRIPE_PRICE_STARTER": "",
        "STRIPE_PRICE_PROFESSIONAL": "",
        "STRIPE_PRICE_BUSINESS": "",
    }
    with patch.dict(os.environ, empty_env, clear=False):
        with TestClient(app) as client:
            register_admin(client, "integration.pending@example.com")
            response = client.get("/api/v1/admin/integrations")

    assert response.status_code == 200
    payload = response.json()
    assert payload["openai"]["configured"] is False
    assert payload["email"]["configured"] is False
    assert payload["stripe"]["checkout_ready"] is False
    assert payload["stripe"]["fully_configured"] is False
