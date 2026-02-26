"""Health check endpoints — liveness and readiness probes."""

import logging

from fastapi import APIRouter
from sqlalchemy import text

from app.config import settings
from app.database import async_session

logger = logging.getLogger(__name__)
router = APIRouter(tags=["health"])


@router.get("/health")
async def health_check():
    """Liveness probe — fast, no dependencies."""
    return {"status": "ok", "service": "raris-backend"}


@router.get("/health/ready")
async def readiness_check():
    """Readiness probe — checks DB and Redis connectivity."""
    checks = {}
    overall = True

    # Database check
    try:
        async with async_session() as db:
            await db.execute(text("SELECT 1"))
        checks["database"] = "ok"
    except Exception as e:
        checks["database"] = f"error: {type(e).__name__}"
        overall = False
        logger.warning("Readiness: database check failed: %s", e)

    # Redis check
    try:
        import redis.asyncio as aioredis

        r = aioredis.from_url(settings.redis_url)
        await r.ping()
        await r.aclose()
        checks["redis"] = "ok"
    except Exception as e:
        checks["redis"] = f"error: {type(e).__name__}"
        overall = False
        logger.warning("Readiness: redis check failed: %s", e)

    return {
        "status": "ready" if overall else "not_ready",
        "service": "raris-backend",
        "checks": checks,
    }
