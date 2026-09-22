import os
import smtplib

import httpx
import pytest
import redis

# Fail before importing the application or touching Redis/database state. Only
# the exact disposable runner and GitHub CI targets are allowed; localhost by
# itself is not proof that a database is safe to mutate.
if os.environ.get("ENVIRONMENT") != "test":
    raise pytest.UsageError("Use ENVIRONMENT=test and scripts/validate_isolated.py")
targets = (os.environ.get("DATABASE_URL", ""), os.environ.get("REDIS_URL", ""))
allowed_targets = {
    ("postgresql+psycopg://postgres:isolated-test-only@postgres:5432/mm_validation",
     "redis://redis:6379/0"),
    ("postgresql+psycopg://postgres:postgres@127.0.0.1:5432/marcenaria_db",
     "redis://127.0.0.1:6379/0"),
}
if targets not in allowed_targets:
    raise pytest.UsageError(
        "DATABASE_URL and REDIS_URL must exactly match the disposable validation runner or CI services"
    )

os.environ.setdefault("OPENAI_API_DISABLED", "true")

from app.main import rate_limiter  # noqa: E402 - validate destinations before app import


@pytest.fixture(autouse=True)
def forbid_external_transports(monkeypatch):
    def blocked(*_args, **_kwargs):
        raise AssertionError("Real email and HTTP transports are forbidden in tests; use mocks")

    monkeypatch.setattr(smtplib, "SMTP", blocked)
    monkeypatch.setattr(smtplib, "SMTP_SSL", blocked)
    monkeypatch.setattr(httpx.HTTPTransport, "handle_request", blocked)
    monkeypatch.setattr(httpx.AsyncHTTPTransport, "handle_async_request", blocked)


@pytest.fixture(autouse=True)
def forbid_real_openai(monkeypatch):
    import openai

    def blocked(**_kwargs):
        raise AssertionError("Testes devem mockar o provider; chamadas reais são proibidas")

    monkeypatch.setattr(openai, "OpenAI", blocked)


@pytest.fixture(autouse=True)
def reset_api_rate_limit_state():
    """Evita que requisições de um teste consumam a cota de outro teste.

    O comportamento do limitador continua sendo exercitado dentro de cada teste;
    apenas o estado global compartilhado pelo processo/Redis é limpo entre casos.
    """
    rate_limiter._local.clear()
    client = redis.Redis.from_url(os.environ.get("REDIS_URL", "redis://localhost:6379/0"))
    try:
        keys = list(client.scan_iter(match="rate:*", count=500))
        if keys:
            client.delete(*keys)
    except redis.RedisError:
        # Testes de fallback do rate limiter também precisam funcionar sem Redis.
        pass
    finally:
        client.close()

    yield

    rate_limiter._local.clear()
