import enum
from datetime import datetime

from pgvector.sqlalchemy import Vector
from sqlalchemy import DateTime, Float, ForeignKey, Integer, String, Text, func
from sqlalchemy.dialects.postgresql import JSONB, TSVECTOR
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.config import settings
from app.database import Base


class CurationStatus(enum.StrEnum):
    raw = "raw"
    enriched = "enriched"
    validated = "validated"
    approved = "approved"
    indexed = "indexed"
    rejected = "rejected"


class IngestionRunStatus(enum.StrEnum):
    pending = "pending"
    running = "running"
    complete = "complete"
    failed = "failed"


class IngestionRun(Base):
    __tablename__ = "ingestion_runs"

    id: Mapped[str] = mapped_column(String(100), primary_key=True)
    acquisition_id: Mapped[str] = mapped_column(String(100), nullable=False)
    manifest_id: Mapped[str] = mapped_column(String(100), nullable=False)
    status: Mapped[IngestionRunStatus] = mapped_column(
        String(20), default=IngestionRunStatus.pending
    )
    started_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    completed_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    total_documents: Mapped[int] = mapped_column(Integer, default=0)
    processed: Mapped[int] = mapped_column(Integer, default=0)
    failed: Mapped[int] = mapped_column(Integer, default=0)

    documents: Mapped[list["InternalDocument"]] = relationship(
        back_populates="ingestion_run", cascade="all, delete-orphan"
    )


class InternalDocument(Base):
    __tablename__ = "internal_documents"

    id: Mapped[str] = mapped_column(String(150), primary_key=True)
    ingestion_run_id: Mapped[str] = mapped_column(ForeignKey("ingestion_runs.id"), nullable=False)
    manifest_id: Mapped[str] = mapped_column(String(100), nullable=False)
    source_id: Mapped[str] = mapped_column(String(100), nullable=False)
    staged_document_id: Mapped[str] = mapped_column(String(100), nullable=False)

    # Extracted content
    title: Mapped[str] = mapped_column(Text, default="")
    full_text: Mapped[str] = mapped_column(Text, default="")

    # Metadata (JSONB for flexible querying)
    jurisdiction: Mapped[str] = mapped_column(String(50), default="")
    regulatory_body: Mapped[str] = mapped_column(String(100), default="")
    effective_date: Mapped[str | None] = mapped_column(String(50), nullable=True)
    authority_level: Mapped[str] = mapped_column(String(30), default="informational")
    document_type: Mapped[str] = mapped_column(String(30), default="guidance")
    applicability_scope: Mapped[list | None] = mapped_column(JSONB, default=list)
    classification_tags: Mapped[list | None] = mapped_column(JSONB, default=list)
    cross_references: Mapped[list | None] = mapped_column(JSONB, default=list)
    supersedes: Mapped[list | None] = mapped_column(JSONB, default=list)
    superseded_by: Mapped[list | None] = mapped_column(JSONB, default=list)

    # Curation state
    status: Mapped[CurationStatus] = mapped_column(
        String(20), default=CurationStatus.raw
    )
    quality_score: Mapped[float] = mapped_column(Float, default=0.0)
    quality_gates: Mapped[dict | None] = mapped_column(JSONB, default=dict)
    curation_notes: Mapped[list | None] = mapped_column(JSONB, default=list)
    curated_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    content_hash: Mapped[str] = mapped_column(String(80), default="")

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )

    # Relationships
    ingestion_run: Mapped["IngestionRun"] = relationship(back_populates="documents")
    sections: Mapped[list["DocumentSection"]] = relationship(
        back_populates="document", cascade="all, delete-orphan"
    )
    tables: Mapped[list["DocumentTable"]] = relationship(
        back_populates="document", cascade="all, delete-orphan"
    )
    chunks: Mapped[list["Chunk"]] = relationship(
        back_populates="document", cascade="all, delete-orphan"
    )


class DocumentSection(Base):
    __tablename__ = "document_sections"

    id: Mapped[str] = mapped_column(String(150), primary_key=True)
    document_id: Mapped[str] = mapped_column(ForeignKey("internal_documents.id"), nullable=False)
    parent_id: Mapped[str | None] = mapped_column(String(150), nullable=True)
    heading: Mapped[str] = mapped_column(Text, default="")
    level: Mapped[int] = mapped_column(Integer, default=1)
    text: Mapped[str] = mapped_column(Text, default="")
    position: Mapped[int] = mapped_column(Integer, default=0)

    document: Mapped["InternalDocument"] = relationship(back_populates="sections")


class DocumentTable(Base):
    __tablename__ = "document_tables"

    id: Mapped[str] = mapped_column(String(150), primary_key=True)
    document_id: Mapped[str] = mapped_column(ForeignKey("internal_documents.id"), nullable=False)
    section_id: Mapped[str | None] = mapped_column(String(150), nullable=True)
    caption: Mapped[str | None] = mapped_column(Text, nullable=True)
    headers: Mapped[list | None] = mapped_column(JSONB, default=list)
    rows: Mapped[list | None] = mapped_column(JSONB, default=list)

    document: Mapped["InternalDocument"] = relationship(back_populates="tables")


class Chunk(Base):
    __tablename__ = "chunks"

    id: Mapped[str] = mapped_column(String(200), primary_key=True)
    document_id: Mapped[str] = mapped_column(ForeignKey("internal_documents.id"), nullable=False)
    section_id: Mapped[str] = mapped_column(String(150), default="")
    section_path: Mapped[str] = mapped_column(Text, default="")
    text: Mapped[str] = mapped_column(Text, nullable=False)
    token_count: Mapped[int] = mapped_column(Integer, default=0)
    position: Mapped[int] = mapped_column(Integer, default=0)
    cross_references: Mapped[list | None] = mapped_column(JSONB, default=list)

    # Dense vector embedding (pgvector)
    embedding: Mapped[list | None] = mapped_column(
        Vector(settings.embedding_dimensions), nullable=True
    )

    # Sparse lexical search (tsvector)
    search_vector: Mapped[str | None] = mapped_column(TSVECTOR, nullable=True)

    # Metadata for filtered retrieval (denormalized from document)
    chunk_metadata: Mapped[dict | None] = mapped_column(JSONB, default=dict)

    document: Mapped["InternalDocument"] = relationship(back_populates="chunks")
