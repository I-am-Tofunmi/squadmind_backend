"""
SquadMind – Redis Client
Async Redis connection pool + helper wrappers for caching and pub/sub.
"""

from __future__ import annotations

import json
from typing import Any, Optional, Union

import redis.asyncio as aioredis

from app.core.config import settings
from app.core.logging import get_logger

log = get_logger(__name__)

# ── Connection Pool ───────────────────────────────────────────────────────────
redis_pool: aioredis.ConnectionPool = aioredis.ConnectionPool.from_url(
    settings.REDIS_URL,
    password=settings.REDIS_PASSWORD or None,
    max_connections=50,
    decode_responses=True,
)


def get_redis_client() -> aioredis.Redis:
    """Return a Redis client backed by the shared pool."""
    return aioredis.Redis(connection_pool=redis_pool)


# ── FastAPI Dependency ────────────────────────────────────────────────────────
async def get_redis() -> aioredis.Redis:
    """
    Dependency-injectable Redis client.

    Usage in route:
        async def my_route(redis: Redis = Depends(get_redis)):
    """
    return get_redis_client()


# ── Health Check ──────────────────────────────────────────────────────────────
async def check_redis_connection() -> bool:
    """Ping Redis. Used in /health endpoint."""
    try:
        client = get_redis_client()
        await client.ping()
        return True
    except Exception as e:
        log.error("redis_health_check_failed", error=str(e))
        return False


# ── Cache Helpers ─────────────────────────────────────────────────────────────
class CacheManager:
    """
    Thin wrapper around Redis for JSON-based caching.
    Designed for dashboard and analytics data that doesn't need to be
    real-time accurate to the millisecond.
    """

    PREFIX = "squadmind:"

    def __init__(self) -> None:
        self.client = get_redis_client()

    def _key(self, key: str) -> str:
        return f"{self.PREFIX}{key}"

    async def get(self, key: str) -> Optional[Any]:
        """Retrieve and JSON-deserialize a cached value."""
        try:
            raw = await self.client.get(self._key(key))
            return json.loads(raw) if raw else None
        except Exception as e:
            log.warning("cache_get_error", key=key, error=str(e))
            return None

    async def set(
        self,
        key: str,
        value: Any,
        ttl_seconds: int = 300,   # default 5 minutes
    ) -> bool:
        """JSON-serialize and cache a value with a TTL."""
        try:
            serialized = json.dumps(value, default=str)
            await self.client.setex(self._key(key), ttl_seconds, serialized)
            return True
        except Exception as e:
            log.warning("cache_set_error", key=key, error=str(e))
            return False

    async def delete(self, key: str) -> bool:
        """Invalidate a cached key."""
        try:
            await self.client.delete(self._key(key))
            return True
        except Exception as e:
            log.warning("cache_delete_error", key=key, error=str(e))
            return False

    async def delete_pattern(self, pattern: str) -> int:
        """Delete all keys matching a glob pattern. Returns count deleted."""
        try:
            keys = await self.client.keys(self._key(pattern))
            if keys:
                return await self.client.delete(*keys)
            return 0
        except Exception as e:
            log.warning("cache_delete_pattern_error", pattern=pattern, error=str(e))
            return 0

    async def exists(self, key: str) -> bool:
        """Check if a key exists in the cache."""
        try:
            return bool(await self.client.exists(self._key(key)))
        except Exception:
            return False


# ── Singleton ─────────────────────────────────────────────────────────────────
cache = CacheManager()


# ── Rate Limiter ──────────────────────────────────────────────────────────────
async def check_rate_limit(identifier: str, max_calls: int, window_seconds: int) -> bool:
    """
    Sliding-window rate limiter.

    Returns True if the request is allowed, False if rate-limited.
    identifier: typically f"{user_id}:{endpoint}"
    """
    client = get_redis_client()
    key = f"{CacheManager.PREFIX}rate:{identifier}"
    try:
        pipe = client.pipeline()
        pipe.incr(key)
        pipe.expire(key, window_seconds)
        results = await pipe.execute()
        current_count = results[0]
        return current_count <= max_calls
    except Exception as e:
        log.warning("rate_limit_check_error", identifier=identifier, error=str(e))
        return True   # fail open — don't block on Redis errors
