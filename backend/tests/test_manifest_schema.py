import pytest
from pydantic import ValidationError

from app.config import settings
from app.schemas.manifest import (
    GenerateManifestRequest,
    ProgramResponse,
    SourceCreate,
    SourceUpdate,
)


def test_generate_manifest_request_valid():
    req = GenerateManifestRequest(
        domain_description="US Insurance regulation",
        llm_provider="openai",
    )
    assert req.domain_description == "US Insurance regulation"


def test_generate_manifest_request_default_provider():
    req = GenerateManifestRequest(domain_description="test")
    assert req.llm_provider == settings.llm_provider
    assert req.k_depth == 2
    assert req.geo_scope == "state"
    assert req.target_segments == []


def test_generate_manifest_request_depth_bounds():
    with pytest.raises(ValidationError):
        GenerateManifestRequest(domain_description="test", k_depth=5)


def test_source_create_valid():
    src = SourceCreate(
        name="Test Source",
        regulatory_body="naic",
        type="guidance",
        format="pdf",
        authority="advisory",
        jurisdiction="federal",
        url="https://example.gov/doc.pdf",
        access_method="download",
        confidence=0.9,
    )
    assert src.name == "Test Source"
    assert src.needs_human_review is False


def test_source_create_confidence_bounds():
    with pytest.raises(ValidationError):
        SourceCreate(
            name="Bad",
            regulatory_body="x",
            type="guidance",
            format="pdf",
            authority="advisory",
            jurisdiction="federal",
            url="https://example.gov",
            access_method="download",
            confidence=1.5,
        )


def test_source_update_partial():
    update = SourceUpdate(name="Updated Name", needs_human_review=False)
    dumped = update.model_dump(exclude_unset=True)
    assert "name" in dumped
    assert "url" not in dumped


def test_program_response_defaults():
    program = ProgramResponse(
        id="prog-001",
        canonical_id="ca-haf-first-time-homebuyer",
        name="California Housing Assistance Fund",
        administering_entity="California Housing Finance Agency",
        geo_scope="state",
        status="verification_pending",
        confidence=0.6,
        needs_human_review=True,
    )
    assert program.source_urls == []
    assert program.provenance_links == {}
