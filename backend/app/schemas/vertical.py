"""Pydantic schemas for vertical onboarding and pipeline management."""

from datetime import datetime

from pydantic import BaseModel, Field


class ScopeConfig(BaseModel):
    jurisdictions: list[str] = Field(default_factory=list)
    regulatory_bodies: list[str] = Field(default_factory=list)
    lines_of_business: list[str] = Field(default_factory=list)
    exclusions: list[str] = Field(default_factory=list)


class CreateVerticalRequest(BaseModel):
    name: str = Field(min_length=1, max_length=255)
    domain_description: str = Field(min_length=10)
    scope: ScopeConfig = Field(default_factory=ScopeConfig)
    llm_provider: str = "openai"
    expected_source_count_min: int = Field(default=100, ge=10)
    expected_source_count_max: int = Field(default=300, ge=10)
    coverage_target: float = Field(default=0.85, ge=0.0, le=1.0)
    rate_limit_ms: int = Field(default=2000, ge=100)
    max_concurrent: int = Field(default=5, ge=1, le=20)
    timeout_seconds: int = Field(default=120, ge=10)


class VerticalSummary(BaseModel):
    id: str
    name: str
    domain_description: str
    phase: str
    source_count: int
    document_count: int
    chunk_count: int
    coverage_score: float
    created_at: datetime
    updated_at: datetime


class PipelinePhaseStatus(BaseModel):
    phase: str
    status: str  # pending | running | complete | failed
    resource_id: str | None = None


class VerticalDetail(BaseModel):
    id: str
    name: str
    domain_description: str
    scope: ScopeConfig
    llm_provider: str
    expected_source_count_min: int
    expected_source_count_max: int
    coverage_target: float
    rate_limit_ms: int
    max_concurrent: int
    timeout_seconds: int
    phase: str
    manifest_id: str | None
    acquisition_id: str | None
    ingestion_id: str | None
    source_count: int
    document_count: int
    chunk_count: int
    coverage_score: float
    last_error: str | None
    created_at: datetime
    updated_at: datetime
    pipeline_status: list[PipelinePhaseStatus] = []


class VerticalPipelineStatus(BaseModel):
    vertical_id: str
    phase: str
    phases: list[PipelinePhaseStatus]
    source_count: int
    document_count: int
    chunk_count: int
    coverage_score: float


class TriggerResponse(BaseModel):
    vertical_id: str
    phase: str
    resource_id: str
    message: str
