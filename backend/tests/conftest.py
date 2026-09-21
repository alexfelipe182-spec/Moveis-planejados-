import os
import smtplib
from urllib.parse import urlparse

import httpx
import pytest
import redis

# Fail before importing the application or touching Redis/database state.
if os.environ.get("ENVIRONMENT") != "test":
    raise pytest.UsageError("Use ENVIRONMENT=test and scripts/validate_isolated.py")
for variable, hosts in (("DATABASE_URL", {"127.0.0.1", "localhost", "postgres"}),
                        ("REDIS_URL", {"127.0.0.1", "localhost", "redis"})):
    if urlparse(os.environ.get(variable, "")).hostname not in hosts:
        raise pytest.UsageError(f"{variable} must explicitly target an isolated local test service")

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
