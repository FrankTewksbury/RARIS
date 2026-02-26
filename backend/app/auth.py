"""API key authentication dependency."""

import hashlib
import logging
import secrets
from datetime import UTC, datetime

from fastapi import Depends, HTTPException, Security
from fastapi.security import APIKeyHeader
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.database import get_db
from app.models.auth import ApiKey, ApiKeyScope

logger = logging.getLogger(__name__)

_api_key_header = APIKeyHeader(name="X-API-Key", auto_error=False)


def hash_key(raw_key: str) -> str:
    """Hash an API key for storage."""
    return hashlib.sha256(raw_key.encode()).hexdigest()


def generate_api_key() -> tuple[str, str]:
    """Generate a new API key. Returns (raw_key, prefix)."""
    raw_key = f"raris_{secrets.token_urlsafe(32)}"
    prefix = raw_key[:12]
    return raw_key, prefix


async def _get_api_key(
    api_key: str | None = Security(_api_key_header),
    db: AsyncSession = Depends(get_db),
) -> ApiKey | None:
    """Validate API key and return the key record."""
    if not settings.auth_enabled:
        return None  # Auth disabled — allow all

    if not api_key:
        raise HTTPException(status_code=401, detail="Missing API key")

    key_hash = hash_key(api_key)
    result = await db.execute(
        select(ApiKey).where(ApiKey.key_hash == key_hash, ApiKey.is_active.is_(True))
    )
    key_record = result.scalar_one_or_none()

    if not key_record:
        raise HTTPException(status_code=401, detail="Invalid API key")

    # Check expiration
    if key_record.expires_at and key_record.expires_at < datetime.now(UTC):
        raise HTTPException(status_code=401, detail="API key expired")

    # Update last_used_at
    await db.execute(
        update(ApiKey).where(ApiKey.id == key_record.id).values(
            last_used_at=datetime.now(UTC)
        )
    )
    await db.commit()

    return key_record


async def require_read(key: ApiKey | None = Depends(_get_api_key)) -> ApiKey | None:
    """Require at least read scope."""
    return key


async def require_write(key: ApiKey | None = Depends(_get_api_key)) -> ApiKey | None:
    """Require at least write scope."""
    if key is None and not settings.auth_enabled:
        return None
    if key and key.scope not in (ApiKeyScope.write, ApiKeyScope.admin):
        raise HTTPException(status_code=403, detail="Insufficient permissions: write required")
    return key


async def require_admin(key: ApiKey | None = Depends(_get_api_key)) -> ApiKey | None:
    """Require admin scope."""
    if key is None and not settings.auth_enabled:
        return None
    if key and key.scope != ApiKeyScope.admin:
        raise HTTPException(status_code=403, detail="Insufficient permissions: admin required")
    return key
