"""Pydantic schemas for API key management."""

from datetime import datetime

from pydantic import BaseModel


class CreateApiKeyRequest(BaseModel):
    name: str
    scope: str = "read"  # read | write | admin
    description: str = ""
    expires_in_days: int | None = None


class ApiKeyCreatedResponse(BaseModel):
    id: str
    name: str
    key: str  # Only returned on creation
    key_prefix: str
    scope: str
    created_at: datetime


class ApiKeySummary(BaseModel):
    id: str
    name: str
    key_prefix: str
    scope: str
    is_active: bool
    description: str
    created_at: datetime
    last_used_at: datetime | None
    expires_at: datetime | None


class RevokeApiKeyResponse(BaseModel):
    id: str
    name: str
    revoked: bool
