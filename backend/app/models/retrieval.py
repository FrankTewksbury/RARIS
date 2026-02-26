"""Models for query and analysis persistence."""

import enum
from datetime import datetime

from sqlalchemy import DateTime, Float, Integer, String, Text, func
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


class QueryStatus(enum.StrEnum):
    pending = "pending"
    processing = "processing"
    complete = "complete"
    failed = "failed"


class QueryRecord(Base):
    __tablename__ = "query_records"

    id: Mapped[str] = mapped_column(String(100), primary_key=True)
    query: Mapped[str] = mapped_column(Text, nullable=False)
    depth: Mapped[int] = mapped_column(Integer, default=2)
    filters: Mapped[dict | None] = mapped_column(JSONB, default=dict)
    status: Mapped[QueryStatus] = mapped_column(
        String(20), default=QueryStatus.pending
    )
    response_text: Mapped[str] = mapped_column(Text, default="")
    citations: Mapped[list | None] = mapped_column(JSONB, default=list)
    sources_count: Mapped[int] = mapped_column(Integer, default=0)
    token_count: Mapped[int] = mapped_column(Integer, default=0)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    completed_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )


class AnalysisRecord(Base):
    __tablename__ = "analysis_records"

    id: Mapped[str] = mapped_column(String(100), primary_key=True)
    analysis_type: Mapped[str] = mapped_column(String(30), nullable=False)
    primary_text_preview: Mapped[str] = mapped_column(Text, default="")
    filters: Mapped[dict | None] = mapped_column(JSONB, default=dict)
    depth: Mapped[int] = mapped_column(Integer, default=3)
    status: Mapped[QueryStatus] = mapped_column(
        String(20), default=QueryStatus.pending
    )
    findings: Mapped[list | None] = mapped_column(JSONB, default=list)
    summary: Mapped[str] = mapped_column(Text, default="")
    coverage_score: Mapped[float | None] = mapped_column(Float, nullable=True)
    citations: Mapped[list | None] = mapped_column(JSONB, default=list)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    completed_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
