import asyncio

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
