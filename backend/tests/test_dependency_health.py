import asyncio
import runpy
import threading
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

import httpx
import pytest
import sqlalchemy

import app.database as database_module
import app.main as main_module


@pytest.fixture(autouse=True)
def isolated_dependencies(monkeypatch):
    # No live sockets or pools shared with integration tests on other event loops.
    monkeypatch.setattr(
        main_module.rate_limiter, "redis", SimpleNamespace(ping=AsyncMock(return_value=True))
    )
    connection = MagicMock()
    connection.__enter__.return_value = connection
    monkeypatch.setattr(main_module.engine, "connect", lambda: connection)
    return connection


def test_database_engine_receives_configured_connect_timeout(monkeypatch):
    create_engine = MagicMock()
    monkeypatch.setattr(sqlalchemy, "create_engine", create_engine)
    monkeypatch.setattr(database_module.settings, "database_connect_timeout_seconds", 8)

    # Execute the wiring in isolation without replacing the application's engine.
    runpy.run_path(database_module.__file__)

    assert create_engine.call_args.kwargs["connect_args"] == {"connect_timeout": 8}


def test_readiness_returns_503_when_redis_ping_stalls(monkeypatch):
    async def stalled():
        await asyncio.Event().wait()

    monkeypatch.setattr(main_module.rate_limiter.redis, "ping", stalled)
    monkeypatch.setattr(main_module.rate_limiter, "redis_timeout_seconds", 0.01)

    async def run():
        async with httpx.AsyncClient(
            transport=httpx.ASGITransport(app=main_module.app), base_url="http://test"
        ) as client:
            async with asyncio.timeout(1):
                return await client.get("/ready")

    response = asyncio.run(run())
    assert response.status_code == 503
    assert response.json()["dependencies"] == {"postgres": "ok", "redis": "unhealthy"}
    assert response.headers["Cache-Control"] == "no-store"


def test_readiness_does_not_treat_a_false_redis_ping_as_healthy(monkeypatch):
    monkeypatch.setattr(main_module.rate_limiter.redis, "ping", AsyncMock(return_value=False))

    async def run():
        async with httpx.AsyncClient(
            transport=httpx.ASGITransport(app=main_module.app), base_url="http://test"
        ) as client:
            return await client.get("/ready")

    response = asyncio.run(run())
    assert response.status_code == 503
    assert response.json()["dependencies"] == {"postgres": "ok", "redis": "unhealthy"}


def test_slow_database_probe_does_not_block_other_requests(isolated_dependencies):
    release_query = threading.Event()

    async def run():
        loop = asyncio.get_running_loop()
        query_started = asyncio.Event()

        def blocked_query(_statement):
            loop.call_soon_threadsafe(query_started.set)
            release_query.wait(timeout=2)

        isolated_dependencies.execute.side_effect = blocked_query
        async with httpx.AsyncClient(
            transport=httpx.ASGITransport(app=main_module.app), base_url="http://test"
        ) as client:
            readiness = asyncio.create_task(client.get("/ready"))
            try:
                await asyncio.wait_for(query_started.wait(), timeout=1)
                health = await asyncio.wait_for(client.get("/health"), timeout=1)
                assert health.status_code == 200
                assert not readiness.done(), "The database probe blocked the event loop"
            finally:
                release_query.set()
                response = await readiness
            assert response.status_code == 200
            assert response.json()["dependencies"] == {"postgres": "ok", "redis": "ok"}

    asyncio.run(run())
