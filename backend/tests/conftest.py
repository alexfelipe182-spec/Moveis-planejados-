import os

import pytest
import redis

from app.main import rate_limiter


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
