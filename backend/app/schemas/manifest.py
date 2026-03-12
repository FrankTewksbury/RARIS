from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field

from app.config import settings


class GenerateManifestRequest(BaseModel):
    manifest_name: str
    llm_provider: str = settings.llm_provider
    llm_model: str | None = None
    instruction_text: str | None = None
    k_depth: int = Field(default=2, ge=1, le=4)
    geo_scope: Literal["national", "state", "municipal"] = "state"
    target_segments: list[str] = []


class GenerateManifestResponse(BaseModel):
    manifest_id: str
    status: str
    stream_url: str


class SourceResponse(BaseModel):
    id: str
    name: str
    regulatory_body: str
    type: str
    format: str
    authority: str
    jurisdiction: str
    url: str
    access_method: str
    update_frequency: str | None = None
    last_known_update: str | None = None
    estimated_size: str | None = None
    scraping_notes: str | None = None
    confidence: float
    needs_human_review: bool
    review_notes: str | None = None
    classification_tags: list[str] = []
    relationships: dict = {}
    citation: str | None = None
    depth_hint: str | None = None


class SourceCreate(BaseModel):
    name: str
    regulatory_body: str
    type: str
    format: str
    authority: str
    jurisdiction: str
    url: str
    access_method: str
    update_frequency: str | None = None
    last_known_update: str | None = None
    estimated_size: str | None = None
    scraping_notes: str | None = None
    confidence: float = Field(ge=0.0, le=1.0, default=1.0)
    needs_human_review: bool = False
    classification_tags: list[str] = []
    citation: str | None = None
    depth_hint: str | None = None


class SourceUpdate(BaseModel):
    name: str | None = None
    url: str | None = None
    type: str | None = None
    format: str | None = None
    authority: str | None = None
    access_method: str | None = None
    update_frequency: str | None = None
    estimated_size: str | None = None
    scraping_notes: str | None = None
    confidence: float | None = Field(None, ge=0.0, le=1.0)
    needs_human_review: bool | None = None
    review_notes: str | None = None
    classification_tags: list[str] | None = None


class RegulatoryBodyResponse(BaseModel):
    id: str
    name: str
    jurisdiction: str
    authority_type: str
    url: str
    governs: list[str] = []


class CoverageAssessmentResponse(BaseModel):
    total_sources: int
    by_jurisdiction: dict = {}
    by_type: dict = {}
    completeness_score: float
    known_gaps: list[dict] = []


class DomainMapResponse(BaseModel):
    regulatory_bodies: list[RegulatoryBodyResponse] = []
    jurisdiction_hierarchy: dict | list = []


class ManifestSummary(BaseModel):
    id: str
    domain: str
    status: str
    created: datetime
    sources_count: int
    programs_count: int = 0
    coverage_score: float


class ProgramResponse(BaseModel):
    id: str
    canonical_id: str
    name: str
    administering_entity: str
    geo_scope: str
    jurisdiction: str | None = None
    benefits: str | None = None
    eligibility: str | None = None
    status: str
    last_verified: datetime | None = None
    evidence_snippet: str | None = None
    source_urls: list[str] = []
    provenance_links: dict = {}
    confidence: float
    needs_human_review: bool


class GoldenProgramResponse(BaseModel):
    id: int
    domain: str | None = None
    golden_run_id: str | None = None
    merge_key: str
    canonical_id: str
    name: str
    administering_entity: str
    geo_scope: str
    jurisdiction: str | None = None
    benefits: str | None = None
    eligibility: str | None = None
    status: str
    last_verified: datetime | None = None
    evidence_snippet: str | None = None
    source_urls: list[str] = []
    provenance_links: dict = {}
    confidence: float
    needs_human_review: bool
    source_manifest_ids: list[str] = []
    found_by_count: int
    ensemble_confidence: float
    merged_at: datetime | None = None


class ManifestDetail(BaseModel):
    id: str
    domain: str
    status: str
    created: datetime
    sources_count: int
    programs_count: int = 0
    coverage_score: float
    sources: list[SourceResponse] = []
    programs: list[ProgramResponse] = []
    domain_map: DomainMapResponse = DomainMapResponse()
    coverage_assessment: CoverageAssessmentResponse | None = None
    checkpoint_data: dict | None = None
    run_params: dict | None = None


class ManifestListResponse(BaseModel):
    manifests: list[ManifestSummary]


class GoldenProgramListResponse(BaseModel):
    programs: list[GoldenProgramResponse]
    total: int


class GoldenProgramStatsResponse(BaseModel):
    total: int
    by_geo_scope: dict[str, int] = {}
    by_found_by_count: dict[str, int] = {}
    average_ensemble_confidence: float = 0.0


class LogicalRunResponse(BaseModel):
    run_id: str
    manifest_id: str
    domain: str
    status: str
    created_at: datetime
    promoted_to_golden_run_id: str | None = None
    notes: str | None = None


class LogicalRunListResponse(BaseModel):
    runs: list[LogicalRunResponse]


class GoldenRunSummaryResponse(BaseModel):
    golden_run_id: str
    domain: str
    version: int
    source_run_ids: list[str] = []
    accepted_at: datetime
    accepted_by: str
    notes: str | None = None
    strategy: str
    item_count: int
    is_current: bool = False


class GoldenRunListResponse(BaseModel):
    runs: list[GoldenRunSummaryResponse]


class GoldenRunDetailResponse(GoldenRunSummaryResponse):
    programs: list[GoldenProgramResponse] = []


class PromoteGoldenRunRequest(BaseModel):
    domain: str
    source_run_ids: list[str] = Field(min_length=1)
    accepted_by: str = "system"
    notes: str = ""


class PromoteGoldenRunResponse(BaseModel):
    golden_run_id: str
    domain: str
    version: int
    total_input: int
    unique_output: int
    duplicates_removed: int
    new_added: int
    updated: int
    by_geo_scope: dict[str, int] = {}


class MergeManifestsRequest(BaseModel):
    manifest_ids: list[str] = Field(min_length=1)


class MergeManifestsResponse(BaseModel):
    total_input: int
    unique_output: int
    duplicates_removed: int
    new_added: int
    updated: int
    by_geo_scope: dict[str, int] = {}


class ReviewRequest(BaseModel):
    reviewer: str
    notes: str = ""


class ReviewResponse(BaseModel):
    manifest_id: str
    status: str
    approved_at: datetime | None = None
    rejection_notes: str | None = None
