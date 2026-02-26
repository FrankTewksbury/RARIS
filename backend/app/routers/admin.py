"""Admin endpoints — API key management, system info, scheduler control."""

import logging
from datetime import UTC, datetime, timedelta

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth import generate_api_key, hash_key, require_admin
from app.config import settings
from app.database import get_db
from app.models.auth import ApiKey, ApiKeyScope
from app.schemas.auth import (
    ApiKeyCreatedResponse,
    ApiKeySummary,
    CreateApiKeyRequest,
    RevokeApiKeyResponse,
)

logger = logging.getLogger(__name__)
router = APIRouter(tags=["admin"])


# --- API Key Management ---


@router.post("/api/admin/keys", status_code=201, response_model=ApiKeyCreatedResponse)
async def create_api_key(
    request: CreateApiKeyRequest,
    db: AsyncSession = Depends(get_db),
    _admin: None = Depends(require_admin),
):
    """Create a new API key (admin only)."""
    raw_key, prefix = generate_api_key()
    key_id = f"key-{datetime.now(UTC).strftime('%Y%m%d%H%M%S%f')}"

    expires_at = None
    if request.expires_in_days:
        expires_at = datetime.now(UTC) + timedelta(days=request.expires_in_days)

    key_record = ApiKey(
        id=key_id,
        name=request.name,
        key_hash=hash_key(raw_key),
        key_prefix=prefix,
        scope=ApiKeyScope(request.scope),
        description=request.description,
        expires_at=expires_at,
    )
    db.add(key_record)
    await db.commit()

    return ApiKeyCreatedResponse(
        id=key_id,
        name=request.name,
        key=raw_key,
        key_prefix=prefix,
        scope=request.scope,
        created_at=key_record.created_at or datetime.now(UTC),
    )


@router.get("/api/admin/keys", response_model=list[ApiKeySummary])
async def list_api_keys(
    db: AsyncSession = Depends(get_db),
    _admin: None = Depends(require_admin),
):
    """List all API keys (admin only)."""
    result = await db.execute(select(ApiKey).order_by(ApiKey.created_at.desc()))
    return [
        ApiKeySummary(
            id=k.id,
            name=k.name,
            key_prefix=k.key_prefix,
            scope=k.scope,
            is_active=k.is_active,
            description=k.description,
            created_at=k.created_at,
            last_used_at=k.last_used_at,
            expires_at=k.expires_at,
        )
        for k in result.scalars().all()
    ]


@router.delete("/api/admin/keys/{key_id}", response_model=RevokeApiKeyResponse)
async def revoke_api_key(
    key_id: str,
    db: AsyncSession = Depends(get_db),
    _admin: None = Depends(require_admin),
):
    """Revoke an API key (admin only)."""
    result = await db.execute(select(ApiKey).where(ApiKey.id == key_id))
    key_record = result.scalar_one_or_none()
    if not key_record:
        raise HTTPException(status_code=404, detail="API key not found")

    key_record.is_active = False
    await db.commit()

    return RevokeApiKeyResponse(id=key_id, name=key_record.name, revoked=True)


# --- System Info ---


@router.get("/api/admin/info")
async def system_info(_admin: None = Depends(require_admin)):
    """System information and configuration summary."""
    return {
        "service": "raris-backend",
        "version": "0.1.0",
        "environment": settings.environment,
        "auth_enabled": settings.auth_enabled,
        "scheduler_enabled": settings.scheduler_enabled,
        "llm_provider": settings.llm_provider,
        "database_url": _mask_url(settings.database_url),
        "redis_url": _mask_url(settings.redis_url),
    }


@router.get("/api/admin/scheduler")
async def scheduler_status(_admin: None = Depends(require_admin)):
    """Get scheduler job status."""
    from app.scheduler import scheduler

    jobs = []
    for job in scheduler.get_jobs():
        jobs.append({
            "id": job.id,
            "name": job.name,
            "next_run": str(job.next_run_time) if job.next_run_time else None,
        })

    return {
        "running": scheduler.running,
        "jobs": jobs,
    }


def _mask_url(url: str) -> str:
    """Mask password in database/redis URL."""
    if "@" in url and "://" in url:
        # postgresql+asyncpg://user:pass@host/db → postgresql+asyncpg://user:***@host/db
        scheme_end = url.index("://") + 3
        at_pos = url.index("@")
        colon_pos = url.index(":", scheme_end)
        return url[:colon_pos + 1] + "***" + url[at_pos:]
    return url
