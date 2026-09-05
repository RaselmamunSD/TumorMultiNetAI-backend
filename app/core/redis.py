from typing import Optional
import redis.asyncio as aioredis
from app.core.config import settings

redis_client: Optional[aioredis.Redis] = None


async def get_redis_client() -> aioredis.Redis:
    """Get or initialize the global async Redis client."""
    global redis_client
    if redis_client is None:
        redis_client = aioredis.from_url(
            settings.REDIS_URL,
            encoding="utf-8",
            decode_responses=True,
            max_connections=20,
        )
    return redis_client


async def close_redis_client() -> None:
    """Close the global Redis connection pool."""
    global redis_client
    if redis_client is not None:
        await redis_client.close()
        redis_client = None


async def check_rate_limit(key: str, max_requests: int = 100, window_seconds: int = 60) -> bool:
    """Simple sliding/fixed window rate limiter via Redis."""
    try:
        r = await get_redis_client()
        current_count = await r.incr(key)
        if current_count == 1:
            await r.expire(key, window_seconds)
        return current_count <= max_requests
    except Exception:
        # Fallback gracefully if Redis is temporarily unreachable
        return True
