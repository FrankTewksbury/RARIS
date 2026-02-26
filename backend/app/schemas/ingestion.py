from datetime import datetime

from pydantic import BaseModel


class StartIngestionRequest(BaseModel):
    acquisition_id: str


class StartIngestionResponse(BaseModel):
    ingestion_id: str
    acquisition_id: str
    manifest_id: str
    status: str
    total_documents: int
    stream_url: str


class IngestionRunDetail(BaseModel):
    ingestion_id: str
    acquisition_id: str
    manifest_id: str
    status: str
    started_at: datetime
    completed_at: datetime | None = None
    total_documents: int
    processed: int
    failed: int


class IngestionRunSummary(BaseModel):
    ingestion_id: str
    acquisition_id: str
    manifest_id: str
    status: str
    started_at: datetime
    total_documents: int
    processed: int
    failed: int


class DocumentSummary(BaseModel):
    document_id: str
    source_id: str
    title: str
    status: str
    quality_score: float
    document_type: str
    jurisdiction: str
    regulatory_body: str
    chunk_count: int = 0


class DocumentDetail(BaseModel):
    document_id: str
    source_id: str
    staged_document_id: str
    manifest_id: str
    title: str
    full_text_preview: str  # first 500 chars
    status: str
    quality_score: float
    quality_gates: dict
    curation_notes: list[str]
    effective_date: str | None = None
    jurisdiction: str
    regulatory_body: str
    authority_level: str
    document_type: str
    classification_tags: list[str]
    cross_references: list[str]
    section_count: int
    table_count: int
    chunk_count: int
    created_at: datetime
    curated_at: datetime | None = None


class SectionSummary(BaseModel):
    id: str
    heading: str
    level: int
    text_preview: str
    parent_id: str | None = None


class IndexStats(BaseModel):
    total_chunks: int
    indexed_chunks: int
    total_documents: int
    indexed_documents: int
    by_jurisdiction: dict[str, int]
    by_document_type: dict[str, int]
