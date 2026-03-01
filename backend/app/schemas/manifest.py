from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field

from app.config import settings


class GenerateManifestRequest(BaseModel):
    domain_description: str
    llm_provider: str = settings.llm_provider
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


class ManifestListResponse(BaseModel):
    manifests: list[ManifestSummary]


class ReviewRequest(BaseModel):
    reviewer: str
    notes: str = ""


class ReviewResponse(BaseModel):
    manifest_id: str
    status: str
    approved_at: datetime | None = None
    rejection_notes: str | None = None
