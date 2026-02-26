"""Models for vertical configuration and pipeline state."""

import enum
from datetime import datetime

from sqlalchemy import DateTime, Float, Integer, String, Text, func
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


class PipelinePhase(enum.StrEnum):
    created = "created"
    discovering = "discovering"
    discovered = "discovered"
    acquiring = "acquiring"
    acquired = "acquired"
    ingesting = "ingesting"
    indexed = "indexed"
    failed = "failed"


class Vertical(Base):
    __tablename__ = "verticals"

    id: Mapped[str] = mapped_column(String(100), primary_key=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    domain_description: Mapped[str] = mapped_column(Text, nullable=False)

    # Scope configuration
    scope: Mapped[dict] = mapped_column(JSONB, default=dict)
    # {jurisdictions, regulatory_bodies, lines_of_business, exclusions}

    # Discovery config
    llm_provider: Mapped[str] = mapped_column(String(50), default="openai")
    expected_source_count_min: Mapped[int] = mapped_column(Integer, default=100)
    expected_source_count_max: Mapped[int] = mapped_column(Integer, default=300)
    coverage_target: Mapped[float] = mapped_column(Float, default=0.85)

    # Acquisition config
    rate_limit_ms: Mapped[int] = mapped_column(Integer, default=2000)
    max_concurrent: Mapped[int] = mapped_column(Integer, default=5)
    timeout_seconds: Mapped[int] = mapped_column(Integer, default=120)

    # Pipeline state
    phase: Mapped[PipelinePhase] = mapped_column(
        String(30), default=PipelinePhase.created
    )
    manifest_id: Mapped[str | None] = mapped_column(String(100), nullable=True)
    acquisition_id: Mapped[str | None] = mapped_column(String(100), nullable=True)
    ingestion_id: Mapped[str | None] = mapped_column(String(100), nullable=True)

    # Metrics
    source_count: Mapped[int] = mapped_column(Integer, default=0)
    document_count: Mapped[int] = mapped_column(Integer, default=0)
    chunk_count: Mapped[int] = mapped_column(Integer, default=0)
    coverage_score: Mapped[float] = mapped_column(Float, default=0.0)

    # Error tracking
    last_error: Mapped[str | None] = mapped_column(Text, nullable=True)

    # Timestamps
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )
