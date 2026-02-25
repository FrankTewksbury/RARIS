import enum
from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Integer, String, Text, func
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


class AcquisitionStatus(enum.StrEnum):
    pending = "pending"
    running = "running"
    complete = "complete"
    failed = "failed"
    cancelled = "cancelled"


class SourceAcqStatus(enum.StrEnum):
    pending = "pending"
    running = "running"
    complete = "complete"
    failed = "failed"
    retrying = "retrying"
    skipped = "skipped"


class StagedDocStatus(enum.StrEnum):
    staged = "staged"
    validation_failed = "validation_failed"
    duplicate = "duplicate"


class AcquisitionRun(Base):
    __tablename__ = "acquisition_runs"

    id: Mapped[str] = mapped_column(String(100), primary_key=True)
    manifest_id: Mapped[str] = mapped_column(String(100), nullable=False)
    status: Mapped[AcquisitionStatus] = mapped_column(
        String(20), default=AcquisitionStatus.pending
    )
    started_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    completed_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    total_sources: Mapped[int] = mapped_column(Integer, default=0)

    sources: Mapped[list["AcquisitionSource"]] = relationship(
        back_populates="acquisition_run", cascade="all, delete-orphan"
    )


class AcquisitionSource(Base):
    __tablename__ = "acquisition_sources"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    acquisition_id: Mapped[str] = mapped_column(
        ForeignKey("acquisition_runs.id"), nullable=False
    )
    source_id: Mapped[str] = mapped_column(String(100), nullable=False)
    manifest_id: Mapped[str] = mapped_column(String(100), nullable=False)
    name: Mapped[str] = mapped_column(Text, nullable=False)
    regulatory_body: Mapped[str] = mapped_column(String(100), nullable=False)
    url: Mapped[str] = mapped_column(Text, nullable=False)
    access_method: Mapped[str] = mapped_column(String(20), nullable=False)
    status: Mapped[SourceAcqStatus] = mapped_column(
        String(20), default=SourceAcqStatus.pending
    )
    retry_count: Mapped[int] = mapped_column(Integer, default=0)
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    duration_ms: Mapped[int | None] = mapped_column(Integer, nullable=True)
    staged_document_id: Mapped[str | None] = mapped_column(String(100), nullable=True)
    last_attempt_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    acquisition_run: Mapped["AcquisitionRun"] = relationship(back_populates="sources")


class StagedDocument(Base):
    __tablename__ = "staged_documents"

    id: Mapped[str] = mapped_column(String(100), primary_key=True)
    manifest_id: Mapped[str] = mapped_column(String(100), nullable=False)
    source_id: Mapped[str] = mapped_column(String(100), nullable=False)
    acquisition_method: Mapped[str] = mapped_column(String(20), nullable=False)
    acquired_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    content_hash: Mapped[str] = mapped_column(String(80), nullable=False)
    content_type: Mapped[str] = mapped_column(String(100), nullable=False)
    raw_content_path: Mapped[str] = mapped_column(Text, nullable=False)
    byte_size: Mapped[int] = mapped_column(Integer, default=0)
    status: Mapped[StagedDocStatus] = mapped_column(
        String(30), default=StagedDocStatus.staged
    )
    provenance: Mapped[dict | None] = mapped_column(JSONB, default=dict)
