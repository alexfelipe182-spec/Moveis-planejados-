import json
import logging
import smtplib
import ssl
from types import SimpleNamespace
from unittest.mock import MagicMock

import httpx
import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from pydantic import SecretStr, ValidationError

from app.api import auth
from app.core.config import Settings
from app.database import get_db
from app.services import email_delivery

TEST_KEY = "re_test_key_not_a_real_credential"
TEST_TOKEN = "test-password-reset-token-never-log-this-value"
RECIPIENT = "recipient@example.com"
GENERIC_MESSAGE = "Se o e-mail estiver cadastrado, as instruções de recuperação serão enviadas."


def email_settings(**overrides):
    values = {
        "environment": "test",
        "email_provider": "smtp",
        "email_from": None,
        "resend_api_key": None,
        "smtp_host": None,
        "smtp_user": None,
        "smtp_password": None,
        "smtp_from": None,
        "frontend_url": "https://admin.example.com",
    }
    values.update(overrides)
    return Settings(_env_file=None, **values)


def resend_settings(**overrides):
    values = {
        "email_provider": "resend",
        "email_from": "access@example.com",
        "resend_api_key": TEST_KEY,
    }
    values.update(overrides)
    return email_settings(**values)


@pytest.fixture(autouse=True)
def prevent_external_delivery(monkeypatch):
    def unexpected_network(*args, **kwargs):
        pytest.fail("Tests must never send a real email")

    monkeypatch.setattr(email_delivery.httpx, "HTTPTransport", unexpected_network)
    monkeypatch.setattr(email_delivery.smtplib, "SMTP", unexpected_network)
    monkeypatch.setattr(email_delivery.smtplib, "SMTP_SSL", unexpected_network)


def mock_resend(monkeypatch, handler):
    requests = []
    options = []

    def handle(request):
        requests.append(request)
        return handler(request)

    def transport(**kwargs):
        options.append(kwargs)
        return httpx.MockTransport(handle)

    monkeypatch.setattr(email_delivery.httpx, "HTTPTransport", transport)
    return requests, options


def send(config):
    return email_delivery.send_email(
        recipient=RECIPIENT,
        subject="Recuperação de acesso",
        text_body=f"https://admin.example.com/#reset_token={TEST_TOKEN}",
        config=config,
    )


def assert_private_values_absent(text):
    for private_value in (RECIPIENT, TEST_TOKEN, TEST_KEY, "smtp-test-password"):
        assert private_value not in text


def test_default_smtp_does_not_require_new_credentials():
    config = email_settings()
    assert config.email_provider == "smtp"
    assert config.resend_api_key is None
    assert config.email_from is None
    assert config.email_timeout_seconds == 10


def test_optional_blank_email_environment_values_are_allowed():
    config = email_settings(email_from="  ", resend_api_key="", email_provider=" SMTP ")
    assert config.email_from is None
    assert config.resend_api_key is None
    assert config.email_provider == "smtp"


def test_resend_key_is_secret_and_validation_errors_do_not_echo_inputs():
    config = resend_settings()
    assert isinstance(config.resend_api_key, SecretStr)
    assert TEST_KEY not in repr(config)
    with pytest.raises(ValidationError) as error:
        resend_settings(email_from=None)
    assert TEST_KEY not in str(error.value)


@pytest.mark.parametrize(
    "overrides",
    [
        {"resend_api_key": None},
        {"resend_api_key": "  "},
        {"resend_api_key": "re_invalid key"},
        {"resend_api_key": "re_invalid\x00key"},
        {"resend_api_key": "re_não_ascii"},
        {"email_from": None},
        {"email_from": "not-an-email"},
        {"email_from": "a@example.com,b@example.com"},
        {"email_provider": "unknown-provider"},
        {"email_timeout_seconds": 0},
        {"email_timeout_seconds": -1},
        {"email_timeout_seconds": 31},
        {"email_timeout_seconds": float("inf")},
        {"email_timeout_seconds": float("nan")},
    ],
)
def test_invalid_email_configuration_is_rejected(overrides):
    with pytest.raises(ValidationError):
        resend_settings(**overrides)


@pytest.mark.parametrize("provider", ["smtp", "disabled"])
def test_missing_or_disabled_email_is_reported_without_network(provider, caplog):
    with caplog.at_level(logging.WARNING, logger="uvicorn.error"):
        assert send(email_settings(email_provider=provider)) is False
    assert "email_delivery_skipped" in caplog.text
    assert f"provider={provider}" in caplog.text
    assert_private_values_absent(caplog.text)


def test_missing_resend_configuration_is_safe_even_if_runtime_settings_change(monkeypatch, caplog):
    config = resend_settings()
    monkeypatch.setattr(config, "resend_api_key", None)
    assert send(config) is False
    assert "provider=resend reason=missing_configuration" in caplog.text


def test_resend_uses_https_expected_payload_timeouts_and_no_retries(monkeypatch, caplog):
    requests, options = mock_resend(
        monkeypatch, lambda request: httpx.Response(200, json={"id": "accepted-message-id"})
    )
    with caplog.at_level(logging.INFO, logger="uvicorn.error"):
        assert send(resend_settings(email_timeout_seconds=4)) is True
    assert options == [{"retries": 0, "trust_env": False}]
    assert len(requests) == 1
    request = requests[0]
    assert request.method == "POST"
    assert str(request.url) == "https://api.resend.com/emails"
    assert request.headers["Authorization"] == f"Bearer {TEST_KEY}"
    assert request.headers["Content-Type"] == "application/json"
    assert request.extensions["timeout"] == {
        "connect": 4,
        "read": 4,
        "write": 4,
        "pool": 4,
    }
    assert json.loads(request.content) == {
        "from": "access@example.com",
        "to": [RECIPIENT],
        "subject": "Recuperação de acesso",
        "text": f"https://admin.example.com/#reset_token={TEST_TOKEN}",
    }
    assert "email_delivery_accepted provider=resend" in caplog.text
    assert_private_values_absent(caplog.text)


@pytest.mark.parametrize("status_code", [301, 307, 400, 401, 403, 429, 500, 503])
def test_provider_errors_and_redirects_are_not_retried_or_exposed(monkeypatch, caplog, status_code):
    requests, _ = mock_resend(
        monkeypatch,
        lambda request: httpx.Response(
            status_code,
            json={"message": f"PRIVATE {RECIPIENT} {TEST_TOKEN} {TEST_KEY}"},
            headers={"Location": "https://unexpected.example.com/emails"},
        ),
    )
    assert send(resend_settings()) is False
    assert len(requests) == 1
    assert f"reason=provider_rejected status_code={status_code}" in caplog.text
    assert_private_values_absent(caplog.text)


@pytest.mark.parametrize(
    "error_type",
    [httpx.ConnectTimeout, httpx.ReadTimeout, httpx.WriteTimeout, httpx.ConnectError, OSError],
)
def test_transport_failures_are_safe_and_not_retried(monkeypatch, caplog, error_type):
    def handler(request):
        raise error_type(f"PRIVATE {RECIPIENT} {TEST_TOKEN} {TEST_KEY}")

    requests, _ = mock_resend(monkeypatch, handler)
    assert send(resend_settings()) is False
    assert len(requests) == 1
    assert f"reason=transport_error error_type={error_type.__name__}" in caplog.text
    assert_private_values_absent(caplog.text)


@pytest.mark.parametrize("body", ["not-json", "{}", "[]", '{"id": ""}', '{"id": 1}'])
def test_success_without_provider_message_id_is_not_claimed_as_accepted(monkeypatch, caplog, body):
    mock_resend(monkeypatch, lambda request: httpx.Response(200, text=body))
    assert send(resend_settings()) is False
    assert "reason=invalid_response" in caplog.text


@pytest.mark.parametrize("use_ssl", [False, True])
def test_smtp_remains_supported_with_verified_tls(monkeypatch, use_ssl, caplog):
    smtp = MagicMock()
    smtp.__enter__.return_value = smtp
    constructor = MagicMock(return_value=smtp)
    monkeypatch.setattr(email_delivery.smtplib, "SMTP_SSL" if use_ssl else "SMTP", constructor)
    config = email_settings(
        smtp_host="smtp.example.com",
        smtp_port=465 if use_ssl else 587,
        smtp_user="smtp-test-user",
        smtp_password="smtp-test-password",
        smtp_from="access@example.com",
        smtp_use_ssl=use_ssl,
        smtp_starttls=not use_ssl,
        smtp_timeout_seconds=7,
    )
    with caplog.at_level(logging.INFO, logger="uvicorn.error"):
        assert send(config) is True
    assert constructor.call_args.args == ("smtp.example.com", 465 if use_ssl else 587)
    assert constructor.call_args.kwargs["timeout"] == 7
    if use_ssl:
        context = constructor.call_args.kwargs["context"]
        smtp.starttls.assert_not_called()
    else:
        context = smtp.starttls.call_args.kwargs["context"]
    assert context.verify_mode == ssl.CERT_REQUIRED
    assert context.check_hostname is True
    smtp.login.assert_called_once_with("smtp-test-user", "smtp-test-password")
    message = smtp.send_message.call_args.args[0]
    assert message["From"] == "access@example.com"
    assert message["To"] == RECIPIENT
    assert f"/#reset_token={TEST_TOKEN}" in message.get_content()
    assert "email_delivery_accepted provider=smtp" in caplog.text
    assert_private_values_absent(caplog.text)


def test_smtp_error_is_safe_and_does_not_raise(monkeypatch, caplog):
    smtp = MagicMock()
    smtp.__enter__.return_value = smtp
    smtp.send_message.side_effect = smtplib.SMTPException(f"PRIVATE {RECIPIENT} smtp-test-password")
    monkeypatch.setattr(email_delivery.smtplib, "SMTP", MagicMock(return_value=smtp))
    config = email_settings(
        smtp_host="smtp.example.com",
        smtp_user="smtp-test-user",
        smtp_password="smtp-test-password",
        smtp_from="access@example.com",
    )
    assert send(config) is False
    assert "provider=smtp reason=transport_error error_type=SMTPException" in caplog.text
    assert_private_values_absent(caplog.text)


@pytest.mark.parametrize("outcome", ["accepted", "rejected", "timeout", "missing", "disabled", "unknown_user"])
def test_production_reset_response_remains_generic_without_debug_token(monkeypatch, caplog, outcome):
    provider = "smtp" if outcome == "missing" else "disabled" if outcome == "disabled" else "resend"
    config = email_settings(
        environment="production",
        secret_key="a" * 48,
        database_url="postgresql+psycopg://user:pass@db.example.com/database",
        cors_origins=["https://admin.example.com"],
        email_provider=provider,
        email_from="access@example.com" if provider == "resend" else None,
        resend_api_key=TEST_KEY if provider == "resend" else None,
    )
    monkeypatch.setattr(auth, "settings", config)
    monkeypatch.setattr(auth.secrets, "token_urlsafe", lambda length: TEST_TOKEN)
    db = MagicMock()
    db.scalar.return_value = None if outcome == "unknown_user" else SimpleNamespace(
        id=7, name="Pessoa Teste", email=RECIPIENT
    )
    test_app = FastAPI()
    test_app.include_router(auth.router, prefix="/api/v1")
    test_app.dependency_overrides[get_db] = lambda: db

    def handler(request):
        if outcome == "timeout":
            raise httpx.ReadTimeout(f"PRIVATE {RECIPIENT} {TEST_TOKEN} {TEST_KEY}")
        if outcome == "rejected":
            return httpx.Response(403, json={"message": f"PRIVATE {RECIPIENT} {TEST_TOKEN}"})
        return httpx.Response(200, json={"id": "accepted-message-id"})

    requests, _ = mock_resend(monkeypatch, handler)
    with TestClient(test_app) as client:
        response = client.post("/api/v1/auth/password-reset/request", json={"email": RECIPIENT})
    assert response.status_code == 200
    assert response.json() == {"message": GENERIC_MESSAGE}
    assert_private_values_absent(response.text)
    assert_private_values_absent(caplog.text)
    if outcome in {"missing", "disabled", "unknown_user"}:
        assert not requests
    else:
        assert len(requests) == 1
        assert f"https://admin.example.com/#reset_token={TEST_TOKEN}" in json.loads(requests[0].content)["text"]
    if outcome == "unknown_user":
        db.commit.assert_not_called()


def test_development_keeps_existing_debug_fallback_without_logging_token(monkeypatch, caplog):
    monkeypatch.setattr(auth, "settings", email_settings())
    monkeypatch.setattr(auth.secrets, "token_urlsafe", lambda length: TEST_TOKEN)
    db = MagicMock()
    db.scalar.return_value = SimpleNamespace(id=7, name="Pessoa Teste", email=RECIPIENT)
    response = auth.request_password_reset(auth.PasswordResetRequest(email=RECIPIENT), db)
    assert response.debug_token == TEST_TOKEN
    assert response.message == GENERIC_MESSAGE
    assert_private_values_absent(caplog.text)
