"""Redis-based sliding window rate limiter."""

import logging
import time

import redis.asyncio as aioredis

from app.config import settings

logger = logging.getLogger(__name__)


class RateLimitResult:
    """Result of a rate limit check."""

    __slots__ = ("allowed", "limit", "remaining", "retry_after")

    def __init__(self, allowed: bool, limit: int, remaining: int, retry_after: float = 0.0):
        self.allowed = allowed
        self.limit = limit
        self.remaining = remaining
        self.retry_after = retry_after


async def check_rate_limit(identifier: str) -> RateLimitResult:
    """Check rate limit for an identifier (API key prefix or IP).

    Uses a Redis sorted set sliding window:
    - Members are timestamps of requests
    - Score is the timestamp value
    - Window is 60 seconds
    """
    limit = settings.rate_limit_rpm
    if limit <= 0:
        return RateLimitResult(allowed=True, limit=0, remaining=0)

    window = 60.0  # seconds
    now = time.time()
    window_start = now - window
    key = f"ratelimit:{identifier}"

    try:
        r = aioredis.from_url(settings.redis_url)
        try:
            pipe = r.pipeline()
            # Remove expired entries
            pipe.zremrangebyscore(key, 0, window_start)
            # Count current entries
            pipe.zcard(key)
            # Add current request
            pipe.zadd(key, {str(now): now})
            # Set expiry on key
            pipe.expire(key, int(window) + 1)
            results = await pipe.execute()

            current_count = results[1]  # zcard result

            if current_count >= limit:
                # Over limit — remove the entry we just added
                await r.zrem(key, str(now))
                # Find oldest entry to calculate retry_after
                oldest = await r.zrange(key, 0, 0, withscores=True)
                retry_after = 0.0
                if oldest:
                    retry_after = oldest[0][1] + window - now
                    retry_after = max(0.0, retry_after)
                return RateLimitResult(
                    allowed=False,
                    limit=limit,
                    remaining=0,
                    retry_after=retry_after,
                )

            remaining = max(0, limit - current_count - 1)
            return RateLimitResult(allowed=True, limit=limit, remaining=remaining)
        finally:
            await r.aclose()
    except Exception as exc:
        # If Redis is unavailable, allow the request (fail-open)
        logger.warning("Rate limiter Redis error (fail-open): %s", exc)
        return RateLimitResult(allowed=True, limit=limit, remaining=limit)
