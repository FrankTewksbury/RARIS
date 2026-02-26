"""Tests for export API endpoints."""

import pytest


@pytest.mark.asyncio
async def test_export_manifest_not_found(client):
    resp = await client.get("/api/export/manifest/nonexistent")
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_export_queries_empty(client):
    resp = await client.get("/api/export/queries")
    assert resp.status_code == 200
    assert resp.headers["content-type"].startswith("text/csv")
    # Should have header row even when empty
    content = resp.text
    assert "id,query,depth,status" in content


@pytest.mark.asyncio
async def test_export_queries_content_disposition(client):
    resp = await client.get("/api/export/queries")
    assert "content-disposition" in resp.headers
    assert "query-history.csv" in resp.headers["content-disposition"]


@pytest.mark.asyncio
async def test_export_manifest_with_data(client):
    """Create a manifest then export it."""
    # Create via the generate endpoint (simplified — just create directly)
    from app.models.manifest import Manifest, ManifestStatus

    # Use the test conftest DB — insert directly
    from tests.conftest import TestSession

    async with TestSession() as db:
        manifest = Manifest(
            id="test-export-001",
            domain="Insurance",
            status=ManifestStatus.approved,
        )
        db.add(manifest)
        await db.commit()

    resp = await client.get("/api/export/manifest/test-export-001")
    assert resp.status_code == 200
    data = resp.json()
    assert data["id"] == "test-export-001"
    assert data["domain"] == "Insurance"
    assert "sources" in data
    assert "regulatory_bodies" in data
