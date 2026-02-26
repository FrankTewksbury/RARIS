"""Pydantic schemas for the retrieval and agent API."""

from datetime import datetime

from pydantic import BaseModel, Field

# --- Search ---

class SearchFiltersSchema(BaseModel):
    jurisdiction: list[str] | None = None
    document_type: list[str] | None = None
    regulatory_body: list[str] | None = None
    authority_level: list[str] | None = None
    tags: list[str] | None = None


# --- Query ---

class QueryRequest(BaseModel):
    query: str
    depth: int = Field(default=2, ge=1, le=4)
    filters: SearchFiltersSchema | None = None


class CitationSchema(BaseModel):
    chunk_id: str
    chunk_text: str = ""
    section_path: str
    document_id: str = ""
    document_title: str = ""
    source_id: str
    source_url: str = ""
    regulatory_body: str = ""
    jurisdiction: str = ""
    authority_level: str = ""
    manifest_id: str = ""
    confidence: float = 0.0


class QueryResponse(BaseModel):
    query_id: str
    query: str
    depth: int
    depth_name: str
    response_text: str
    citations: list[CitationSchema]
    sources_count: int
    token_count: int


class QuerySummary(BaseModel):
    query_id: str
    query: str
    depth: int
    created_at: datetime
    response_preview: str


# --- Analysis ---

class AnalysisRequest(BaseModel):
    analysis_type: str = Field(
        description="gap | conflict | coverage | change_impact"
    )
    primary_text: str = Field(description="Document text to analyze")
    filters: SearchFiltersSchema | None = None
    depth: int = Field(default=3, ge=1, le=4)


class FindingSchema(BaseModel):
    category: str
    severity: str
    description: str
    primary_citation: dict = {}
    comparison_citation: dict | None = None
    recommendation: str = ""


class AnalysisResponse(BaseModel):
    analysis_id: str
    analysis_type: str
    findings: list[FindingSchema]
    summary: str
    coverage_score: float | None = None
    citations: list[CitationSchema]


# --- Corpus ---

class CorpusStats(BaseModel):
    total_documents: int
    indexed_documents: int
    total_chunks: int
    indexed_chunks: int
    by_jurisdiction: dict[str, int]
    by_document_type: dict[str, int]
    by_regulatory_body: dict[str, int]


class CorpusSourceSummary(BaseModel):
    source_id: str
    manifest_id: str
    name: str
    regulatory_body: str
    jurisdiction: str
    authority_level: str
    document_type: str
    document_count: int
    chunk_count: int
