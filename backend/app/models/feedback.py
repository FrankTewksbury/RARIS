"""Models for response feedback, re-curation queue, and change monitoring."""

import enum
from datetime import datetime

from sqlalchemy import DateTime, Float, Integer, String, Text, func
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


class FeedbackType(enum.StrEnum):
    inaccurate = "inaccurate"
    outdated = "outdated"
    incomplete = "incomplete"
    irrelevant = "irrelevant"
    correct = "correct"


class FeedbackStatus(enum.StrEnum):
    pending = "pending"
    investigating = "investigating"
    resolved = "resolved"
    dismissed = "dismissed"


class ResponseFeedback(Base):
    __tablename__ = "response_feedback"

    id: Mapped[str] = mapped_column(String(100), primary_key=True)
    query_id: Mapped[str] = mapped_column(String(100), nullable=False)
    feedback_type: Mapped[FeedbackType] = mapped_column(String(20), nullable=False)
    citation_id: Mapped[str | None] = mapped_column(String(200), nullable=True)
    description: Mapped[str] = mapped_column(Text, default="")
    submitted_by: Mapped[str] = mapped_column(String(100), default="anonymous")
    status: Mapped[FeedbackStatus] = mapped_column(
        String(20), default=FeedbackStatus.pending
    )
    resolution: Mapped[str | None] = mapped_column(Text, nullable=True)
    # Trace results (populated by tracer)
    traced_source_id: Mapped[str | None] = mapped_column(String(100), nullable=True)
    traced_manifest_id: Mapped[str | None] = mapped_column(String(100), nullable=True)
    traced_document_id: Mapped[str | None] = mapped_column(String(150), nullable=True)
    auto_action: Mapped[str | None] = mapped_column(String(50), nullable=True)

    submitted_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    resolved_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )


class CurationQueuePriority(enum.StrEnum):
    critical = "critical"
    high = "high"
    medium = "medium"
    low = "low"


class CurationQueueStatus(enum.StrEnum):
    pending = "pending"
    processing = "processing"
    resolved = "resolved"
    dismissed = "dismissed"


class CurationQueueItem(Base):
    __tablename__ = "curation_queue"

    id: Mapped[str] = mapped_column(String(100), primary_key=True)
    source_id: Mapped[str] = mapped_column(String(100), nullable=False)
    manifest_id: Mapped[str] = mapped_column(String(100), nullable=False)
    priority: Mapped[CurationQueuePriority] = mapped_column(
        String(20), default=CurationQueuePriority.medium
    )
    reason: Mapped[str] = mapped_column(Text, default="")
    trigger_type: Mapped[str] = mapped_column(String(30), default="feedback")
    # feedback | change_detected | scheduled
    feedback_id: Mapped[str | None] = mapped_column(String(100), nullable=True)
    change_event_id: Mapped[str | None] = mapped_column(String(100), nullable=True)
    status: Mapped[CurationQueueStatus] = mapped_column(
        String(20), default=CurationQueueStatus.pending
    )
    result: Mapped[str | None] = mapped_column(Text, nullable=True)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    processed_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )


class ChangeEvent(Base):
    __tablename__ = "change_events"

    id: Mapped[str] = mapped_column(String(100), primary_key=True)
    source_id: Mapped[str] = mapped_column(String(100), nullable=False)
    manifest_id: Mapped[str] = mapped_column(String(100), nullable=False)
    detection_method: Mapped[str] = mapped_column(String(30), nullable=False)
    # hash_check | rss | federal_register | manual
    change_type: Mapped[str] = mapped_column(String(30), nullable=False)
    # content_update | new_document | supersession | removal
    previous_hash: Mapped[str | None] = mapped_column(String(80), nullable=True)
    current_hash: Mapped[str | None] = mapped_column(String(80), nullable=True)
    description: Mapped[str] = mapped_column(Text, default="")
    status: Mapped[str] = mapped_column(String(20), default="detected")
    # detected | processing | resolved | dismissed
    impact_assessment: Mapped[str | None] = mapped_column(Text, nullable=True)

    detected_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    resolved_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )


class AccuracySnapshot(Base):
    __tablename__ = "accuracy_snapshots"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    snapshot_date: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    total_feedback: Mapped[int] = mapped_column(Integer, default=0)
    correct_count: Mapped[int] = mapped_column(Integer, default=0)
    inaccurate_count: Mapped[int] = mapped_column(Integer, default=0)
    outdated_count: Mapped[int] = mapped_column(Integer, default=0)
    incomplete_count: Mapped[int] = mapped_column(Integer, default=0)
    irrelevant_count: Mapped[int] = mapped_column(Integer, default=0)
    accuracy_score: Mapped[float] = mapped_column(Float, default=0.0)
    resolution_rate: Mapped[float] = mapped_column(Float, default=0.0)
    avg_confidence: Mapped[float] = mapped_column(Float, default=0.0)
    stale_sources: Mapped[int] = mapped_column(Integer, default=0)
    by_vertical: Mapped[dict | None] = mapped_column(JSONB, default=dict)
