"""Resilience primitives shared by the API and background workers."""

from __future__ import annotations

import asyncio
import time
from collections import defaultdict
from dataclasses import dataclass

from redis.asyncio import Redis


@dataclass(frozen=True)
class RateLimitDecision:
    allowed: bool
    retry_after: int


class DistributedRateLimiter:
    """Redis-backed fixed-window limiter with a safe in-process fallback.

    Redis is preferred so multiple API replicas share the same limit. The local
    fallback prevents a Redis outage from taking the API down, while remaining
    bounded by periodic cleanup.
    """

    def __init__(self, redis_url: str, limit: int = 120, window_seconds: int = 60) -> None:
        self.limit = limit
        self.window_seconds = window_seconds
        self.redis: Redis = Redis.from_url(redis_url, decode_responses=True)
        self._local: dict[str, tuple[int, float]] = {}
        self._lock = asyncio.Lock()

    async def allow(self, key: str) -> RateLimitDecision:
        now = int(time.time())
        bucket = now // self.window_seconds
        redis_key = f"rate:{bucket}:{key}"
        try:
            count = await self.redis.incr(redis_key)
            if count == 1:
                await self.redis.expire(redis_key, self.window_seconds + 1)
            if count > self.limit:
                return RateLimitDecision(False, self.window_seconds - (now % self.window_seconds))
            return RateLimitDecision(True, 0)
        except Exception:
            return await self._allow_local(key, now)

    async def _allow_local(self, key: str, now: int) -> RateLimitDecision:
        async with self._lock:
            count, started = self._local.get(key, (0, float(now)))
            if now - started >= self.window_seconds:
                count, started = 0, float(now)
            count += 1
            self._local[key] = (count, started)
            if len(self._local) > 10_000:
                cutoff = now - self.window_seconds
                self._local = {k: v for k, v in self._local.items() if v[1] >= cutoff}
            if count > self.limit:
                return RateLimitDecision(False, max(1, self.window_seconds - int(now - started)))
            return RateLimitDecision(True, 0)

    async def close(self) -> None:
        await self.redis.aclose()
