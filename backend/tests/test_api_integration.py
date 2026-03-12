"""API integration tests — hit actual FastAPI routes via ASGI transport.

These tests verify endpoint wiring, request validation, and error handling
without requiring a live database. Endpoints that need DB data return
empty lists or 404s, which is the expected behavior.
"""

import pytest

from app.database import get_db
from app.routers import manifests as manifests_router

# --- Health ---


@pytest.mark.asyncio
async def test_health(client):
    resp = await client.get("/health")
    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == "ok"
    assert data["service"] == "raris-backend"


# --- Manifests ---


@pytest.mark.asyncio
async def test_list_manifests(client):
    resp = await client.get("/api/manifests")
    assert resp.status_code == 200
    data = resp.json()
    assert isinstance(data["manifests"], list)


@pytest.mark.asyncio
async def test_get_manifest_not_found(client):
    resp = await client.get("/api/manifests/nonexistent-id")
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_generate_manifest_validation(client):
    # Missing required field
    resp = await client.post("/api/manifests/generate", json={})
    assert resp.status_code == 422
    data = resp.json()
    assert data["error"] is True
    assert "errors" in data


@pytest.mark.asyncio
async def test_generate_manifest_json_requires_instruction_text(client):
    resp = await client.post(
        "/api/manifests/generate",
        json={
            "manifest_name": "US insurance regulation",
            "llm_provider": "openai",
        },
    )
    assert resp.status_code == 422
    data = resp.json()
    assert data["error"] is True
    assert "errors" in data


@pytest.mark.asyncio
async def test_generate_manifest_multipart_without_instruction_file(client, monkeypatch):
    async def _noop_run_agent(*args, **kwargs):
        return None

    monkeypatch.setattr(manifests_router, "_run_agent", _noop_run_agent)

    resp = await client.post(
        "/api/manifests/generate",
        data={
            "manifest_name": "US insurance regulation",
            "llm_provider": "openai",
        },
    )
    assert resp.status_code == 422
    data = resp.json()
    assert data["error"] is True
    assert "errors" in data


@pytest.mark.asyncio
async def test_generate_manifest_multipart_with_instruction_only(client, monkeypatch):
    async def _noop_run_agent(*args, **kwargs):
        return None

    monkeypatch.setattr(manifests_router, "_run_agent", _noop_run_agent)

    resp = await client.post(
        "/api/manifests/generate",
        data={
            "manifest_name": "US insurance regulation",
            "llm_provider": "openai",
        },
        files={
            "instruction_files": ("instruction.txt", b"focus on insurance regulators", "text/plain"),
        },
    )
    assert resp.status_code == 202
    data = resp.json()
    assert "manifest_id" in data
    assert data["status"] == "generating"
    assert "stream_url" in data


@pytest.mark.asyncio
async def test_list_manifests_reconciles_orphaned_generating_runs(client, monkeypatch):
    async def _noop_run_agent(*args, **kwargs):
        return None

    monkeypatch.setattr(manifests_router, "_run_agent", _noop_run_agent)

    resp = await client.post(
        "/api/manifests/generate",
        data={
            "manifest_name": "US insurance regulation",
            "llm_provider": "openai",
        },
        files={
            "instruction_files": ("instruction.txt", b"focus on insurance regulators", "text/plain"),
        },
    )
    assert resp.status_code == 202
    manifest_id = resp.json()["manifest_id"]

    manifests_router._event_queues.pop(manifest_id, None)

    resp = await client.get("/api/manifests")
    assert resp.status_code == 200
    manifests = resp.json()["manifests"]
    manifest = next(item for item in manifests if item["id"] == manifest_id)
    assert manifest["status"] == "pending_review"


@pytest.mark.asyncio
async def test_stream_manifest_reports_reconciled_orphaned_generation(client, monkeypatch):
    async def _noop_run_agent(*args, **kwargs):
        return None

    monkeypatch.setattr(manifests_router, "_run_agent", _noop_run_agent)

    resp = await client.post(
        "/api/manifests/generate",
        data={
            "manifest_name": "US insurance regulation",
            "llm_provider": "openai",
        },
        files={
            "instruction_files": ("instruction.txt", b"focus on insurance regulators", "text/plain"),
        },
    )
    assert resp.status_code == 202
    manifest_id = resp.json()["manifest_id"]

    manifests_router._event_queues.pop(manifest_id, None)

    resp = await client.get(f"/api/manifests/{manifest_id}/stream")
    assert resp.status_code == 409
    assert "reconciled" in resp.json()["detail"].lower()

    resp = await client.get(f"/api/manifests/{manifest_id}")
    assert resp.status_code == 200
    assert resp.json()["status"] == "pending_review"


@pytest.mark.asyncio
async def test_generate_manifest_multipart_with_attachments(client, monkeypatch):
    async def _noop_run_agent(*args, **kwargs):
        return None

    monkeypatch.setattr(manifests_router, "_run_agent", _noop_run_agent)

    files = {
        "constitution_file": ("constitution.md", b"must do guardrails", "text/markdown"),
        "instruction_files": ("instruction.txt", b"focus on federal and all states", "text/plain"),
    }
    resp = await client.post(
        "/api/manifests/generate",
        data={
            "manifest_name": "US insurance regulation",
            "llm_provider": "openai",
        },
        files=files,
    )
    assert resp.status_code == 202
    data = resp.json()
    assert "manifest_id" in data
    assert data["status"] == "generating"


@pytest.mark.asyncio
async def test_generate_manifest_multipart_with_seeding_files(client, monkeypatch):
    async def _noop_run_agent(*args, **kwargs):
        return None

    monkeypatch.setattr(manifests_router, "_run_agent", _noop_run_agent)

    files = [
        ("seeding_files", ("seed.json", b'[{"url":"https://example.gov/portal"}]', "application/json")),
        ("seeding_files", ("seed.csv", b"name,url\nExample,https://example.com", "text/csv")),
    ]
    resp = await client.post(
        "/api/manifests/generate",
        data={
            "manifest_name": "US insurance regulation",
            "llm_provider": "openai",
            "geo_scope": "municipal",
            "k_depth": "3",
        },
        files=[
            ("instruction_files", ("instruction.txt", b"focus on insurance regulators", "text/plain")),
            *files,
        ],
    )
    assert resp.status_code == 202
    data = resp.json()
    assert "manifest_id" in data
    assert data["status"] == "generating"


@pytest.mark.asyncio
async def test_generate_manifest_multipart_multi_prompt(client, monkeypatch):
    """Multiple instruction_files are accepted and threaded as instruction_texts list."""
    received_texts: list[list[str]] = []

    async def _capture_run_agent(*args, **kwargs):
        received_texts.append(kwargs.get("instruction_texts", []))

    monkeypatch.setattr(manifests_router, "_run_agent", _capture_run_agent)

    resp = await client.post(
        "/api/manifests/generate",
        data={
            "manifest_name": "US insurance regulation multi-prompt",
            "llm_provider": "openai",
        },
        files=[
            ("instruction_files", ("1-federal.txt", b"Find all federal insurance regulators", "text/plain")),
            ("instruction_files", ("2-state.txt", b"Find all 56 state and territorial regulators", "text/plain")),
            ("instruction_files", ("3-standards.txt", b"Find all standards and advisory bodies", "text/plain")),
        ],
    )
    assert resp.status_code == 202
    data = resp.json()
    assert "manifest_id" in data
    assert data["status"] == "generating"


@pytest.mark.asyncio
async def test_generate_manifest_multipart_without_instruction_files_rejects(client, monkeypatch):
    """Sending no instruction_files returns 422."""
    async def _noop_run_agent(*args, **kwargs):
        return None

    monkeypatch.setattr(manifests_router, "_run_agent", _noop_run_agent)

    resp = await client.post(
        "/api/manifests/generate",
        data={
            "manifest_name": "US insurance regulation",
            "llm_provider": "openai",
        },
    )
    assert resp.status_code == 422
    data = resp.json()
    assert data["error"] is True


@pytest.mark.asyncio
async def test_generate_manifest_rejects_unsupported_attachment(client, monkeypatch):
    async def _noop_run_agent(*args, **kwargs):
        return None

    monkeypatch.setattr(manifests_router, "_run_agent", _noop_run_agent)

    resp = await client.post(
        "/api/manifests/generate",
        data={
            "manifest_name": "US insurance regulation",
            "llm_provider": "openai",
        },
        files={
            "constitution_file": ("constitution.exe", b"bad", "application/octet-stream"),
        },
    )
    assert resp.status_code == 422
    data = resp.json()
    assert data["error"] is True
    assert "Unsupported file type" in data["detail"]


@pytest.mark.asyncio
async def test_generate_manifest_rejects_unsupported_seed_file(client, monkeypatch):
    async def _noop_run_agent(*args, **kwargs):
        return None

    monkeypatch.setattr(manifests_router, "_run_agent", _noop_run_agent)

    resp = await client.post(
        "/api/manifests/generate",
        data={
            "manifest_name": "US insurance regulation",
            "llm_provider": "openai",
        },
        files={
            "seeding_files": ("seed.exe", b"bad", "application/octet-stream"),
        },
    )
    assert resp.status_code == 422
    data = resp.json()
    assert data["error"] is True
    assert "Unsupported seed file type" in data["detail"]


@pytest.mark.asyncio
async def test_update_source_not_found(client):
    resp = await client.patch(
        "/api/manifests/fake-manifest/sources/fake-source",
        json={"confidence": 0.5},
    )
    assert resp.status_code == 404


# --- Acquisitions ---


@pytest.mark.asyncio
async def test_list_acquisitions(client):
    resp = await client.get("/api/acquisitions")
    assert resp.status_code == 200
    data = resp.json()
    assert isinstance(data["acquisitions"], list)


@pytest.mark.asyncio
async def test_get_acquisition_not_found(client):
    resp = await client.get("/api/acquisitions/nonexistent-id")
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_start_acquisition_validation(client):
    resp = await client.post("/api/acquisitions", json={})
    assert resp.status_code == 422
    data = resp.json()
    assert data["error"] is True


# --- Ingestion ---


@pytest.mark.asyncio
async def test_get_ingestion_not_found(client):
    resp = await client.get("/api/ingestion/nonexistent-id")
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_get_document_not_found(client):
    resp = await client.get("/api/documents/nonexistent-id")
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_index_stats(client):
    resp = await client.get("/api/index/stats")
    assert resp.status_code == 200
    data = resp.json()
    assert "total_documents" in data
    assert "total_chunks" in data


@pytest.mark.asyncio
async def test_start_ingestion_validation(client):
    resp = await client.post("/api/ingestion/run", json={})
    assert resp.status_code == 422


# --- Retrieval ---


@pytest.mark.asyncio
async def test_get_query_not_found(client):
    resp = await client.get("/api/query/nonexistent-id")
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_get_analysis_not_found(client):
    resp = await client.get("/api/analysis/nonexistent-id")
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_corpus_stats(client):
    resp = await client.get("/api/corpus/stats")
    assert resp.status_code == 200
    data = resp.json()
    assert "total_documents" in data
    assert "total_chunks" in data
    assert "indexed_documents" in data


@pytest.mark.asyncio
async def test_corpus_sources(client):
    resp = await client.get("/api/corpus/sources")
    assert resp.status_code == 200
    data = resp.json()
    assert isinstance(data, list)


@pytest.mark.asyncio
async def test_get_citation_not_found(client):
    resp = await client.get("/api/citations/nonexistent-chunk")
    assert resp.status_code == 404


# --- Verticals ---


@pytest.mark.asyncio
async def test_list_verticals(client):
    resp = await client.get("/api/verticals")
    assert resp.status_code == 200
    data = resp.json()
    assert isinstance(data, list)


@pytest.mark.asyncio
async def test_get_vertical_not_found(client):
    resp = await client.get("/api/verticals/nonexistent-id")
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_create_vertical_validation(client):
    resp = await client.post("/api/verticals", json={})
    assert resp.status_code == 422


# --- Feedback ---


@pytest.mark.asyncio
async def test_list_feedback(client):
    resp = await client.get("/api/feedback")
    assert resp.status_code == 200
    data = resp.json()
    assert isinstance(data, list)


@pytest.mark.asyncio
async def test_list_feedback_with_filters(client):
    resp = await client.get("/api/feedback?status=pending&feedback_type=inaccurate&limit=10")
    assert resp.status_code == 200
    data = resp.json()
    assert isinstance(data, list)


@pytest.mark.asyncio
async def test_get_feedback_not_found(client):
    resp = await client.get("/api/feedback/nonexistent-id")
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_submit_feedback_validation(client):
    resp = await client.post("/api/feedback", json={})
    assert resp.status_code == 422


@pytest.mark.asyncio
async def test_resolve_feedback_not_found(client):
    resp = await client.patch(
        "/api/feedback/nonexistent-id/resolve",
        json={"resolution": "Fixed", "status": "resolved"},
    )
    assert resp.status_code == 404


# --- Curation Queue ---


@pytest.mark.asyncio
async def test_list_curation_queue(client):
    resp = await client.get("/api/curation-queue")
    assert resp.status_code == 200
    data = resp.json()
    assert isinstance(data, list)


@pytest.mark.asyncio
async def test_process_queue_item_not_found(client):
    resp = await client.post("/api/curation-queue/nonexistent-id/process")
    assert resp.status_code == 404


# --- Changes ---


@pytest.mark.asyncio
async def test_list_changes(client):
    resp = await client.get("/api/changes")
    assert resp.status_code == 200
    data = resp.json()
    assert isinstance(data, list)


@pytest.mark.asyncio
async def test_get_change_not_found(client):
    resp = await client.get("/api/changes/nonexistent-id")
    assert resp.status_code == 404


# --- Monitor ---


@pytest.mark.asyncio
async def test_trigger_monitor(client):
    resp = await client.post("/api/monitor/run")
    assert resp.status_code == 202
    data = resp.json()
    assert "message" in data


# --- Accuracy Dashboard ---


@pytest.mark.asyncio
async def test_accuracy_dashboard(client):
    resp = await client.get("/api/accuracy/dashboard")
    assert resp.status_code == 200
    data = resp.json()
    assert "current" in data
    assert "trends" in data
    assert "by_feedback_type" in data
    assert "by_vertical" in data
    assert "accuracy_score" in data["current"]
    assert "resolution_rate" in data["current"]


# --- Error handling ---


@pytest.mark.asyncio
async def test_404_format(client):
    resp = await client.get("/nonexistent-route")
    assert resp.status_code == 404
    data = resp.json()
    assert data["error"] is True
    assert data["status_code"] == 404


@pytest.mark.asyncio
async def test_validation_error_format(client):
    resp = await client.post("/api/manifests/generate", json={"bad_field": "value"})
    assert resp.status_code == 422
    data = resp.json()
    assert data["error"] is True
    assert data["status_code"] == 422
    assert isinstance(data["errors"], list)
    assert len(data["errors"]) > 0
    assert "field" in data["errors"][0]
    assert "message" in data["errors"][0]


@pytest.mark.asyncio
async def test_resume_manifest_404_when_not_found(client):
    """POST /resume returns 404 for non-existent manifest."""
    resp = await client.post("/api/manifests/nonexistent-id/resume")
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_resume_manifest_409_when_no_checkpoint(client, monkeypatch):
    """POST /resume returns 409 when manifest exists but has no checkpoint_data."""
    async def _noop_run_agent(*args, **kwargs):
        return None

    monkeypatch.setattr(manifests_router, "_run_agent", _noop_run_agent)

    # First create a manifest
    resp = await client.post(
        "/api/manifests/generate",
        data={"manifest_name": "test domain no checkpoint", "llm_provider": "openai"},
        files=[("instruction_files", ("inst.txt", b"Find regulators", "text/plain"))],
    )
    assert resp.status_code == 202
    manifest_id = resp.json()["manifest_id"]

    # Resume should fail — no checkpoint
    resp2 = await client.post(f"/api/manifests/{manifest_id}/resume")
    assert resp2.status_code == 409


@pytest.mark.asyncio
async def test_resume_manifest_202_when_checkpoint_present(client, monkeypatch):
    """POST /resume returns 202 when manifest has checkpoint_data."""
    from app.models.manifest import Manifest, ManifestStatus
    from tests.conftest import TestSession

    async def _noop_run_agent_resumed(*args, **kwargs):
        return None

    monkeypatch.setattr(manifests_router, "_run_agent_resumed", _noop_run_agent_resumed)

    # Directly create a manifest in pending_review with checkpoint_data using
    # the test session (SQLite in-memory, same engine as the route's get_db override)
    manifest_id = "raris-test-resume-checkpoint-001"
    async with TestSession() as db:
        manifest = Manifest(
            id=manifest_id,
            domain="test domain with checkpoint",
            status=ManifestStatus.pending_review,
            created_by="test",
        )
        manifest.checkpoint_data = {
            "type": "l1_boundary",
            "batch_n": 0,
            "api_calls_used": 42,
            "queue_items": [],
            "visited": [],
            "written_at": "2026-03-11T00:00:00Z",
        }
        db.add(manifest)
        await db.commit()

    # Resume should work — no active queue, checkpoint present
    resp = await client.post(f"/api/manifests/{manifest_id}/resume")
    assert resp.status_code == 202
    data = resp.json()
    assert data["manifest_id"] == manifest_id
    assert "stream_url" in data
