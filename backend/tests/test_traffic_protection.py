import pytest
from starlette.requests import Request
from starlette.testclient import TestClient

import app.main as main_module
from app.core.resilience import RateLimitDecision


def request_with(headers=None, client=("192.0.2.10", 12345)):
    return Request({
        "type": "http", "method": "GET", "path": "/", "client": client,
        "headers": [(key.lower().encode(), value.encode()) for key, value in (headers or {}).items()],
    })


@pytest.mark.parametrize("header", [None, "", "not-an-ip", "203.0.113.1, 203.0.113.2"])
def test_invalid_or_missing_edge_ip_uses_connection(monkeypatch, header):
    monkeypatch.setenv("RENDER", "true")
    monkeypatch.setenv("RENDER_SERVICE_TYPE", "web")
    headers = {"X-Forwarded-For": "198.51.100.1"}
    if header is not None:
        headers["CF-Connecting-IP"] = header
    assert main_module._client_rate_limit_key(request_with(headers)) == "192.0.2.10"


def test_ipv6_edge_address_is_normalized(monkeypatch):
    monkeypatch.setenv("RENDER", "true")
    monkeypatch.setenv("RENDER_SERVICE_TYPE", "web")
    request = request_with({"CF-Connecting-IP": "2001:0db8:0000:0000:0000:0000:0000:0001"})
    assert main_module._client_rate_limit_key(request) == "2001:db8::1"


def test_private_render_service_does_not_trust_edge_header(monkeypatch):
    monkeypatch.setenv("RENDER", "true")
    monkeypatch.setenv("RENDER_SERVICE_TYPE", "pserv")
    request = request_with({"CF-Connecting-IP": "203.0.113.9"})
    assert main_module._client_rate_limit_key(request) == "192.0.2.10"


def test_request_without_connection_uses_unknown(monkeypatch):
    monkeypatch.delenv("RENDER", raising=False)
    assert main_module._client_rate_limit_key(request_with(client=None)) == "unknown"


def test_rate_limit_response_is_readable_by_allowed_browser(monkeypatch):
    async def deny(_key):
        return RateLimitDecision(allowed=False, retry_after=15)

    monkeypatch.setattr(main_module.rate_limiter, "allow", deny)
    origin = main_module.settings.cors_origins[0]
    with TestClient(main_module.app) as client:
        response = client.get("/", headers={"Origin": origin, "X-Request-ID": "rate-test"})

    assert response.status_code == 429
    assert response.headers["Access-Control-Allow-Origin"] == origin
    assert response.headers["Access-Control-Allow-Credentials"] == "true"
    assert response.headers["Retry-After"] == "15"
    assert response.headers["X-RateLimit-Limit"] == str(main_module.rate_limiter.limit)
    assert "retry-after" in response.headers["Access-Control-Expose-Headers"].lower()
    assert response.headers["X-Content-Type-Options"] == "nosniff"
    assert response.headers["X-Request-ID"] == "rate-test"
    assert response.json()["detail"] == "Muitas requisições. Tente novamente em instantes."


def test_health_and_preflight_do_not_consume_rate_limit(monkeypatch):
    keys = []

    async def unexpected_call(_key):
        keys.append(_key)
        return RateLimitDecision(allowed=False, retry_after=15)

    monkeypatch.setattr(main_module.rate_limiter, "allow", unexpected_call)
    with TestClient(main_module.app) as client:
        health = client.get("/health")
        preflight = client.options("/api/v1/customers", headers={
            "Origin": main_module.settings.cors_origins[0],
            "Access-Control-Request-Method": "POST",
            "Access-Control-Request-Headers": "X-CSRF-Token",
        })
    assert health.status_code == 200
    assert preflight.status_code == 200
    assert keys == []
