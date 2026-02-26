"""Tests for vertical configuration, pipeline state, and schema validation."""

from app.models.vertical import PipelinePhase, Vertical
from app.schemas.vertical import (
    CreateVerticalRequest,
    PipelinePhaseStatus,
    ScopeConfig,
    VerticalSummary,
)


class TestPipelinePhase:
    def test_all_phases_present(self):
        expected = {
            "created", "discovering", "discovered",
            "acquiring", "acquired",
            "ingesting", "indexed", "failed",
        }
        assert set(PipelinePhase) == expected

    def test_phase_ordering(self):
        """Phases should follow a logical progression."""
        ordered = [
            PipelinePhase.created,
            PipelinePhase.discovering,
            PipelinePhase.discovered,
            PipelinePhase.acquiring,
            PipelinePhase.acquired,
            PipelinePhase.ingesting,
            PipelinePhase.indexed,
        ]
        assert len(ordered) == 7  # All non-error phases

    def test_phase_values_match_names(self):
        for phase in PipelinePhase:
            assert phase.value == phase.name


class TestScopeConfig:
    def test_empty_scope(self):
        scope = ScopeConfig()
        assert scope.jurisdictions == []
        assert scope.regulatory_bodies == []
        assert scope.lines_of_business == []
        assert scope.exclusions == []

    def test_full_scope(self):
        scope = ScopeConfig(
            jurisdictions=["federal", "state"],
            regulatory_bodies=["naic", "cms"],
            lines_of_business=["mortgage origination"],
            exclusions=["commercial real estate"],
        )
        assert len(scope.jurisdictions) == 2
        assert "naic" in scope.regulatory_bodies
        assert "commercial real estate" in scope.exclusions

    def test_scope_serialization(self):
        scope = ScopeConfig(jurisdictions=["federal"])
        data = scope.model_dump()
        assert data["jurisdictions"] == ["federal"]
        assert isinstance(data["exclusions"], list)


class TestCreateVerticalRequest:
    def test_minimal_request(self):
        req = CreateVerticalRequest(
            name="Test Vertical",
            domain_description="A test regulatory domain covering XYZ",
        )
        assert req.name == "Test Vertical"
        assert req.llm_provider == "openai"
        assert req.coverage_target == 0.85
        assert req.expected_source_count_min == 100

    def test_full_request(self):
        req = CreateVerticalRequest(
            name="Mortgage FTHB",
            domain_description="All US mortgage regulations for first-time homebuyers",
            scope=ScopeConfig(
                jurisdictions=["federal", "state"],
                lines_of_business=["mortgage origination", "mortgage servicing"],
                exclusions=["commercial real estate"],
            ),
            llm_provider="anthropic",
            expected_source_count_min=150,
            expected_source_count_max=300,
            coverage_target=0.90,
            rate_limit_ms=3000,
            max_concurrent=3,
            timeout_seconds=180,
        )
        assert req.llm_provider == "anthropic"
        assert req.coverage_target == 0.90
        assert len(req.scope.lines_of_business) == 2

    def test_coverage_target_bounds(self):
        import pytest

        with pytest.raises(Exception):
            CreateVerticalRequest(
                name="Bad",
                domain_description="A test domain covering regulations",
                coverage_target=1.5,
            )


class TestPipelinePhaseStatus:
    def test_pending_status(self):
        s = PipelinePhaseStatus(phase="discovery", status="pending")
        assert s.resource_id is None

    def test_complete_with_resource(self):
        s = PipelinePhaseStatus(
            phase="discovery", status="complete", resource_id="manifest-123"
        )
        assert s.resource_id == "manifest-123"


class TestVerticalSummary:
    def test_summary_fields(self):
        s = VerticalSummary(
            id="vert-test-123",
            name="Test",
            domain_description="Test domain",
            phase="created",
            source_count=0,
            document_count=0,
            chunk_count=0,
            coverage_score=0.0,
            created_at="2026-02-25T00:00:00Z",
            updated_at="2026-02-25T00:00:00Z",
        )
        assert s.id.startswith("vert-")
        assert s.phase == "created"


class TestVerticalModel:
    def test_model_creation(self):
        v = Vertical(
            id="vert-test",
            name="Test",
            domain_description="Test domain",
            phase=PipelinePhase.created,
        )
        assert v.phase == PipelinePhase.created
        assert v.manifest_id is None
        assert v.acquisition_id is None
        assert v.ingestion_id is None
        assert v.last_error is None

    def test_model_with_scope(self):
        v = Vertical(
            id="vert-mortgage",
            name="Mortgage FTHB",
            domain_description="Mortgage regulations",
            scope={"jurisdictions": ["federal"], "exclusions": ["commercial"]},
        )
        assert v.scope["jurisdictions"] == ["federal"]

    def test_model_phase_transitions(self):
        v = Vertical(
            id="vert-test",
            name="Test",
            domain_description="Test",
            phase=PipelinePhase.created,
        )
        assert v.phase == PipelinePhase.created

        v.phase = PipelinePhase.discovering
        assert v.phase == "discovering"

        v.phase = PipelinePhase.discovered
        v.manifest_id = "manifest-abc"
        assert v.manifest_id == "manifest-abc"
