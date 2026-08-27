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
