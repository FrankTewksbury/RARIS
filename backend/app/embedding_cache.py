"""Redis-based embedding cache to avoid repeat OpenAI API calls."""

import hashlib
import json
import logging

import redis.asyncio as aioredis

from app.config import settings

logger = logging.getLogger(__name__)

_CACHE_TTL = 86400  # 24 hours


def _cache_key(text: str) -> str:
    """Generate a cache key from query text."""
    h = hashlib.sha256(text.encode()).hexdigest()[:16]
    return f"embed:{settings.embedding_model}:{h}"


async def get_cached_embedding(text: str) -> list[float] | None:
    """Look up a cached embedding for the given text."""
    try:
        r = aioredis.from_url(settings.redis_url)
        try:
            data = await r.get(_cache_key(text))
            if data:
                return json.loads(data)
            return None
        finally:
            await r.aclose()
    except Exception:
        logger.debug("Embedding cache read failed (miss)")
        return None


async def set_cached_embedding(text: str, embedding: list[float]) -> None:
    """Store an embedding in the cache."""
    try:
        r = aioredis.from_url(settings.redis_url)
        try:
            await r.setex(_cache_key(text), _CACHE_TTL, json.dumps(embedding))
        finally:
            await r.aclose()
    except Exception:
        logger.debug("Embedding cache write failed")
