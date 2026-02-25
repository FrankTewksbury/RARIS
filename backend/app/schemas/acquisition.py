from datetime import datetime

from pydantic import BaseModel


class StartAcquisitionRequest(BaseModel):
    manifest_id: str


class StartAcquisitionResponse(BaseModel):
    acquisition_id: str
    manifest_id: str
    status: str
    total_sources: int
    stream_url: str


class AcquisitionRunDetail(BaseModel):
    acquisition_id: str
    manifest_id: str
    status: str
    started_at: datetime
    elapsed_seconds: float
    total_sources: int
    completed: int
    failed: int
    pending: int
    retrying: int


class AcquisitionRunSummary(BaseModel):
    acquisition_id: str
    manifest_id: str
    status: str
    started_at: datetime
    total_sources: int
    completed: int
    failed: int


class AcquisitionSourceStatus(BaseModel):
    source_id: str
    name: str
    regulatory_body: str
    access_method: str
    status: str
    duration_ms: int | None = None
    staged_document_id: str | None = None
    error: str | None = None
    retry_count: int = 0


class RetryResponse(BaseModel):
    source_id: str
    status: str
    retry_count: int
    message: str


class AcquisitionListResponse(BaseModel):
    acquisitions: list[AcquisitionRunSummary]


class AcquisitionSourcesResponse(BaseModel):
    sources: list[AcquisitionSourceStatus]
