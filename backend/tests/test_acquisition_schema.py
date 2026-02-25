from app.schemas.acquisition import (
    AcquisitionSourceStatus,
    RetryResponse,
    StartAcquisitionRequest,
)


def test_start_acquisition_request():
    req = StartAcquisitionRequest(manifest_id="raris-manifest-insurance-001")
    assert req.manifest_id == "raris-manifest-insurance-001"


def test_acquisition_source_status():
    src = AcquisitionSourceStatus(
        source_id="src-001",
        name="Test Source",
        regulatory_body="naic",
        access_method="scrape",
        status="complete",
        duration_ms=5200,
        staged_document_id="stg-src-001",
        error=None,
        retry_count=0,
    )
    assert src.status == "complete"
    assert src.duration_ms == 5200


def test_retry_response():
    resp = RetryResponse(
        source_id="src-015",
        status="retrying",
        retry_count=2,
        message="Source re-queued for acquisition",
    )
    assert resp.retry_count == 2
