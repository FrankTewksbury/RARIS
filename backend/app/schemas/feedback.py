"""Pydantic schemas for feedback, re-curation queue, change monitoring, accuracy."""

from datetime import datetime

from pydantic import BaseModel, Field

# --- Feedback ---

class SubmitFeedbackRequest(BaseModel):
    query_id: str
    feedback_type: str = Field(
        description="inaccurate | outdated | incomplete | irrelevant | correct"
    )
    citation_id: str | None = None
    description: str = ""
    submitted_by: str = "anonymous"


class FeedbackDetail(BaseModel):
    id: str
    query_id: str
    feedback_type: str
    citation_id: str | None
    description: str
    submitted_by: str
    status: str
    resolution: str | None
    traced_source_id: str | None
    traced_manifest_id: str | None
    traced_document_id: str | None
    auto_action: str | None
    submitted_at: datetime
    resolved_at: datetime | None


class ResolveFeedbackRequest(BaseModel):
    resolution: str
    status: str = "resolved"  # resolved | dismissed


# --- Curation Queue ---

class CurationQueueItemSchema(BaseModel):
    id: str
    source_id: str
    manifest_id: str
    priority: str
    reason: str
    trigger_type: str
    feedback_id: str | None
    change_event_id: str | None
    status: str
    result: str | None
    created_at: datetime
    processed_at: datetime | None


# --- Change Events ---

class ChangeEventSchema(BaseModel):
    id: str
    source_id: str
    manifest_id: str
    detection_method: str
    change_type: str
    previous_hash: str | None
    current_hash: str | None
    description: str
    status: str
    impact_assessment: str | None
    detected_at: datetime
    resolved_at: datetime | None


class TriggerMonitorResponse(BaseModel):
    sources_checked: int
    changes_detected: int
    message: str


# --- Accuracy Dashboard ---

class AccuracyMetrics(BaseModel):
    total_feedback: int
    correct_count: int
    inaccurate_count: int
    outdated_count: int
    incomplete_count: int
    irrelevant_count: int
    accuracy_score: float
    resolution_rate: float
    avg_source_confidence: float
    stale_sources: int
    pending_queue_items: int
    unresolved_changes: int


class AccuracyTrendPoint(BaseModel):
    date: str
    accuracy_score: float
    total_feedback: int
    resolution_rate: float


class AccuracyDashboardData(BaseModel):
    current: AccuracyMetrics
    trends: list[AccuracyTrendPoint]
    by_feedback_type: dict[str, int]
    by_vertical: dict[str, float]
