"""API integration tests — hit actual FastAPI routes via ASGI transport.

These tests verify endpoint wiring, request validation, and error handling
without requiring a live database. Endpoints that need DB data return
empty lists or 404s, which is the expected behavior.
"""

import pytest

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
