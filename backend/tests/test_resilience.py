import asyncio
from unittest.mock import AsyncMock

import pytest
from redis.exceptions import ConnectionError as RedisConnectionError

from app.core.resilience import DistributedRateLimiter


def test_local_rate_limiter_blocks_after_limit():
    limiter = DistributedRateLimiter("redis://127.0.0.1:6399/15", limit=2, window_seconds=60)

    async def run():
        first = await limiter._allow_local("test-client", 100)
        second = await limiter._allow_local("test-client", 100)
        third = await limiter._allow_local("test-client", 100)
        await limiter.close()
        return first, second, third

    first, second, third = asyncio.run(run())
    assert first.allowed
    assert second.allowed
    assert not third.allowed
    assert third.retry_after > 0


def test_local_rate_limiter_resets_window():
    limiter = DistributedRateLimiter("redis://127.0.0.1:6399/15", limit=1, window_seconds=60)

    async def run():
        blocked = await limiter._allow_local("test-client", 100)
        reset = await limiter._allow_local("test-client", 160)
        await limiter.close()
        return blocked, reset

    blocked, reset = asyncio.run(run())
    assert blocked.allowed
    assert reset.allowed


def test_redis_client_has_explicit_timeouts_and_no_command_retries():
    limiter = DistributedRateLimiter("redis://127.0.0.1:6399/15", redis_timeout_seconds=0.25)
    connection = limiter.redis.connection_pool.make_connection()
    assert connection.socket_connect_timeout == 0.25
    assert connection.socket_timeout == 0.25
    assert connection.retry.get_retries() == 0
    asyncio.run(limiter.close())


def test_redis_rate_limit_and_expiry_are_preserved(monkeypatch):
    limiter = DistributedRateLimiter("redis://127.0.0.1:6399/15", limit=2)
    incr = AsyncMock(side_effect=[1, 2, 3])
    expire = AsyncMock(return_value=True)
    monkeypatch.setattr(limiter.redis, "incr", incr)
    monkeypatch.setattr(limiter.redis, "expire", expire)
    monkeypatch.setattr("app.core.resilience.time.time", lambda: 100)

    async def run():
        try:
            return [await limiter.allow("client") for _ in range(3)]
        finally:
            await limiter.close()

    decisions = asyncio.run(run())
    assert [decision.allowed for decision in decisions] == [True, True, False]
    assert decisions[-1].retry_after == 20
    expire.assert_awaited_once_with("rate:1:client", 61)
    assert not limiter._local


def test_redis_connection_failure_keeps_local_protection(monkeypatch):
    limiter = DistributedRateLimiter("redis://127.0.0.1:6399/15", limit=1)
    incr = AsyncMock(side_effect=RedisConnectionError("unavailable"))
    monkeypatch.setattr(limiter.redis, "incr", incr)

    async def run():
        try:
            return await limiter.allow("client"), await limiter.allow("client")
        finally:
            await limiter.close()

    first, second = asyncio.run(run())
    assert first.allowed
    assert not second.allowed
    assert incr.await_count == 2


@pytest.mark.parametrize("stalled_command", ["incr", "expire"])
def test_stalled_redis_commands_time_out_and_keep_local_protection(monkeypatch, stalled_command):
    limiter = DistributedRateLimiter(
        "redis://127.0.0.1:6399/15", limit=1, redis_timeout_seconds=0.01
    )
    cancelled = []

    async def stalled(*_args):
        try:
            await asyncio.Event().wait()
        finally:
            cancelled.append(True)

    monkeypatch.setattr(limiter.redis, "incr", AsyncMock(return_value=1))
    monkeypatch.setattr(limiter.redis, "expire", AsyncMock(return_value=True))
    monkeypatch.setattr(limiter.redis, stalled_command, stalled)

    async def run():
        try:
            async with asyncio.timeout(1):
                return await limiter.allow("client"), await limiter.allow("client")
        finally:
            await limiter.close()

    first, second = asyncio.run(run())
    assert first.allowed
    assert not second.allowed
    assert len(cancelled) == 2


def test_request_cancellation_is_not_converted_to_local_allow(monkeypatch):
    limiter = DistributedRateLimiter("redis://127.0.0.1:6399/15")
    monkeypatch.setattr(limiter.redis, "incr", AsyncMock(side_effect=asyncio.CancelledError))

    async def run():
        try:
            with pytest.raises(asyncio.CancelledError):
                await limiter.allow("client")
        finally:
            await limiter.close()

    asyncio.run(run())
    assert not limiter._local


def test_stalled_redis_health_check_times_out(monkeypatch):
    limiter = DistributedRateLimiter("redis://127.0.0.1:6399/15", redis_timeout_seconds=0.01)

    async def stalled():
        await asyncio.Event().wait()

    monkeypatch.setattr(limiter.redis, "ping", stalled)

    async def run():
        try:
            async with asyncio.timeout(1):
                with pytest.raises(TimeoutError):
                    await limiter.ping()
        finally:
            await limiter.close()

    asyncio.run(run())
