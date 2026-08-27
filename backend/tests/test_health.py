import logging

from starlette.testclient import TestClient

import app.main as main_module
from app.main import app


def test_health_is_alive():
    with TestClient(app) as client:
        response = client.get("/health")
    assert response.status_code == 200
    assert response.json()["status"] == "ok"
    assert response.headers["Cache-Control"] == "no-store"


def test_readiness_checks_database_and_redis():
    with TestClient(app) as client:
        response = client.get("/ready")
    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "ready"
    assert body["dependencies"] == {"postgres": "ok", "redis": "ok"}
    assert response.headers["Cache-Control"] == "no-store"


def test_readiness_returns_503_when_postgres_is_unavailable(monkeypatch):
    def fail_connect():
        raise RuntimeError("postgres unavailable")

    async def redis_ok():
        return True

    monkeypatch.setattr(main_module.engine, "connect", fail_connect)
    monkeypatch.setattr(main_module.rate_limiter.redis, "ping", redis_ok)

    with TestClient(app) as client:
        response = client.get("/ready")

    assert response.status_code == 503
    assert response.json() == {
        "status": "not_ready",
        "service": main_module.settings.app_name,
        "dependencies": {"postgres": "unhealthy", "redis": "ok"},
    }
    assert response.headers["Cache-Control"] == "no-store"


def test_readiness_returns_503_when_redis_is_unavailable(monkeypatch):
    class HealthyConnection:
        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, tb):
            return False

        def execute(self, _statement):
            return None

    async def fail_ping():
        raise RuntimeError("redis unavailable")

    monkeypatch.setattr(main_module.engine, "connect", lambda: HealthyConnection())
    monkeypatch.setattr(main_module.rate_limiter.redis, "ping", fail_ping)

    with TestClient(app) as client:
        response = client.get("/ready")

    assert response.status_code == 503
    assert response.json() == {
        "status": "not_ready",
        "service": main_module.settings.app_name,
        "dependencies": {"postgres": "ok", "redis": "unhealthy"},
    }
    assert response.headers["Cache-Control"] == "no-store"


def test_security_headers_are_present():
    with TestClient(app) as client:
        response = client.get("/health")
    assert response.headers["X-Content-Type-Options"] == "nosniff"
    assert response.headers["X-Frame-Options"] == "DENY"
    assert response.headers["Referrer-Policy"] == "strict-origin-when-cross-origin"
    assert "Permissions-Policy" in response.headers


def test_request_id_is_generated_and_returned():
    with TestClient(app) as client:
        response = client.get("/health")

    request_id = response.headers["X-Request-ID"]
    assert len(request_id) == 32
    assert request_id.isalnum()


def test_safe_request_id_is_preserved():
    with TestClient(app) as client:
        response = client.get("/health", headers={"X-Request-ID": "frontend-check_123"})

    assert response.headers["X-Request-ID"] == "frontend-check_123"


def test_unsafe_request_id_is_replaced():
    with TestClient(app) as client:
        response = client.get("/health", headers={"X-Request-ID": "unsafe request id"})

    assert response.headers["X-Request-ID"] != "unsafe request id"
    assert len(response.headers["X-Request-ID"]) == 32


def test_request_log_has_correlation_fields(caplog):
    caplog.set_level("DEBUG", logger="uvicorn.error")

    with TestClient(app) as client:
        response = client.get("/health", headers={"X-Request-ID": "observability-test"})

    assert response.status_code == 200
    assert any(
        "request_completed request_id=observability-test method=GET path=/health status=200 duration_ms=" in record.message
        for record in caplog.records
    )


def test_application_logger_emits_info_in_production_runtime():
    assert main_module.logger.name == "uvicorn.error"
    assert main_module.logger.level == logging.INFO
