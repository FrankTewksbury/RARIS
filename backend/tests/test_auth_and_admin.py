"""Tests for API key auth, admin endpoints, middleware, scheduler, and health checks."""

import hashlib

import pytest

from app.auth import generate_api_key, hash_key
from app.config import Settings
from app.models.auth import ApiKey, ApiKeyScope
from app.schemas.auth import (
    ApiKeyCreatedResponse,
    ApiKeySummary,
    CreateApiKeyRequest,
    RevokeApiKeyResponse,
)

# --- API Key Generation ---


class TestApiKeyGeneration:
    def test_generate_key_format(self):
        raw_key, prefix = generate_api_key()
        assert raw_key.startswith("raris_")
        assert len(raw_key) > 20
        assert prefix == raw_key[:12]

    def test_generate_key_unique(self):
        keys = {generate_api_key()[0] for _ in range(10)}
        assert len(keys) == 10  # All unique

    def test_hash_key_deterministic(self):
        key = "raris_test_key_123"
        h1 = hash_key(key)
        h2 = hash_key(key)
        assert h1 == h2

    def test_hash_key_uses_sha256(self):
        key = "raris_test_key_123"
        expected = hashlib.sha256(key.encode()).hexdigest()
        assert hash_key(key) == expected


# --- ApiKey Model ---


class TestApiKeyModel:
    def test_model_creation(self):
        key = ApiKey(
            id="key-test-001",
            name="Test Key",
            key_hash="abc123",
            key_prefix="raris_test_",
            scope=ApiKeyScope.read,
            is_active=True,
        )
        assert key.id == "key-test-001"
        assert key.scope == ApiKeyScope.read
        assert key.is_active is True
        assert key.last_used_at is None
        assert key.expires_at is None

    def test_scope_enum(self):
        assert set(ApiKeyScope) == {"read", "write", "admin"}

    def test_scope_values(self):
        assert ApiKeyScope.read == "read"
        assert ApiKeyScope.write == "write"
        assert ApiKeyScope.admin == "admin"


# --- Auth Schemas ---


class TestCreateApiKeyRequest:
    def test_minimal_request(self):
        req = CreateApiKeyRequest(name="My Key")
        assert req.name == "My Key"
        assert req.scope == "read"
        assert req.description == ""
        assert req.expires_in_days is None

    def test_full_request(self):
        req = CreateApiKeyRequest(
            name="Admin Key",
            scope="admin",
            description="For CI/CD pipeline",
            expires_in_days=90,
        )
        assert req.scope == "admin"
        assert req.expires_in_days == 90


class TestApiKeySummary:
    def test_summary_fields(self):
        summary = ApiKeySummary(
            id="key-001",
            name="Test",
            key_prefix="raris_abc123",
            scope="read",
            is_active=True,
            description="A test key",
            created_at="2026-02-25T00:00:00Z",
            last_used_at=None,
            expires_at=None,
        )
        assert summary.is_active is True
        assert summary.last_used_at is None


class TestApiKeyCreatedResponse:
    def test_response_includes_raw_key(self):
        resp = ApiKeyCreatedResponse(
            id="key-001",
            name="New Key",
            key="raris_abc123def456",
            key_prefix="raris_abc123",
            scope="write",
            created_at="2026-02-25T00:00:00Z",
        )
        assert resp.key.startswith("raris_")
        data = resp.model_dump()
        assert "key" in data


class TestRevokeApiKeyResponse:
    def test_revoke_response(self):
        resp = RevokeApiKeyResponse(id="key-001", name="Old Key", revoked=True)
        assert resp.revoked is True


# --- Config Validation ---


class TestConfigValidation:
    def test_default_settings(self):
        s = Settings(
            database_url="postgresql+asyncpg://test:test@localhost/test",
            _env_file=None,
        )
        assert s.auth_enabled is False
        assert s.scheduler_enabled is False
        assert s.environment == "development"
        assert s.log_level == "INFO"

    def test_scheduler_settings(self):
        s = Settings(
            database_url="postgresql+asyncpg://test:test@localhost/test",
            scheduler_enabled=True,
            monitor_schedule_hour=4,
            snapshot_schedule_hour=5,
            _env_file=None,
        )
        assert s.scheduler_enabled is True
        assert s.monitor_schedule_hour == 4
        assert s.snapshot_schedule_hour == 5


# --- Admin API Integration Tests ---


@pytest.mark.asyncio
async def test_system_info(client):
    resp = await client.get("/api/admin/info")
    assert resp.status_code == 200
    data = resp.json()
    assert data["service"] == "raris-backend"
    assert data["version"] == "0.1.0"
    assert "auth_enabled" in data
    assert "scheduler_enabled" in data
    assert "llm_provider" in data


@pytest.mark.asyncio
async def test_scheduler_status(client):
    resp = await client.get("/api/admin/scheduler")
    assert resp.status_code == 200
    data = resp.json()
    assert "running" in data
    assert "jobs" in data
    assert isinstance(data["jobs"], list)


@pytest.mark.asyncio
async def test_create_api_key(client):
    resp = await client.post(
        "/api/admin/keys",
        json={"name": "Test Key", "scope": "read"},
    )
    assert resp.status_code == 201
    data = resp.json()
    assert data["name"] == "Test Key"
    assert data["scope"] == "read"
    assert data["key"].startswith("raris_")
    assert data["key_prefix"] == data["key"][:12]


@pytest.mark.asyncio
async def test_list_api_keys(client):
    # Create one first
    await client.post(
        "/api/admin/keys",
        json={"name": "List Test", "scope": "write"},
    )
    resp = await client.get("/api/admin/keys")
    assert resp.status_code == 200
    data = resp.json()
    assert isinstance(data, list)
    assert len(data) >= 1
    assert data[0]["name"] == "List Test"


@pytest.mark.asyncio
async def test_revoke_api_key(client):
    # Create then revoke
    create_resp = await client.post(
        "/api/admin/keys",
        json={"name": "Revoke Test", "scope": "read"},
    )
    key_id = create_resp.json()["id"]

    resp = await client.delete(f"/api/admin/keys/{key_id}")
    assert resp.status_code == 200
    data = resp.json()
    assert data["revoked"] is True


@pytest.mark.asyncio
async def test_revoke_nonexistent_key(client):
    resp = await client.delete("/api/admin/keys/nonexistent-key")
    assert resp.status_code == 404


# --- Health Checks ---


@pytest.mark.asyncio
async def test_liveness(client):
    resp = await client.get("/health")
    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == "ok"


@pytest.mark.asyncio
async def test_readiness_structure(client):
    resp = await client.get("/health/ready")
    data = resp.json()
    assert "status" in data
    assert "checks" in data
    assert "database" in data["checks"]
    assert "redis" in data["checks"]


# --- Middleware ---


@pytest.mark.asyncio
async def test_correlation_id_generated(client):
    resp = await client.get("/health")
    assert "x-correlation-id" in resp.headers
    assert len(resp.headers["x-correlation-id"]) > 0


@pytest.mark.asyncio
async def test_correlation_id_passthrough(client):
    custom_id = "test-correlation-123"
    resp = await client.get("/health", headers={"X-Correlation-ID": custom_id})
    assert resp.headers["x-correlation-id"] == custom_id


@pytest.mark.asyncio
async def test_response_time_header(client):
    resp = await client.get("/health")
    assert "x-response-time-ms" in resp.headers
    time_ms = float(resp.headers["x-response-time-ms"])
    assert time_ms >= 0


# --- URL Masking ---


class TestUrlMasking:
    def test_mask_database_url(self):
        from app.routers.admin import _mask_url

        url = "postgresql+asyncpg://raris:secret123@localhost:5432/raris"
        masked = _mask_url(url)
        assert "secret123" not in masked
        assert "***" in masked
        assert "raris" in masked  # User preserved
        assert "localhost:5432" in masked  # Host preserved

    def test_mask_redis_url(self):
        from app.routers.admin import _mask_url

        url = "redis://default:mypassword@redis:6379/0"
        masked = _mask_url(url)
        assert "mypassword" not in masked
        assert "***" in masked

    def test_mask_url_no_password(self):
        from app.routers.admin import _mask_url

        url = "redis://localhost:6379/0"
        masked = _mask_url(url)
        assert masked == url  # No change
