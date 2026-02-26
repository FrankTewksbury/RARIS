"""Feedback service — CRUD for feedback, curation queue, changes, accuracy metrics."""

import logging
from datetime import UTC, datetime

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.feedback import (
    AccuracySnapshot,
    ChangeEvent,
    CurationQueueItem,
    CurationQueueStatus,
    FeedbackStatus,
    FeedbackType,
    ResponseFeedback,
)
from app.models.manifest import Source
from app.models.vertical import Vertical
from app.schemas.feedback import (
    AccuracyDashboardData,
    AccuracyMetrics,
    AccuracyTrendPoint,
    ChangeEventSchema,
    CurationQueueItemSchema,
    FeedbackDetail,
)

logger = logging.getLogger(__name__)


# --- Feedback CRUD ---


async def create_feedback(
    db: AsyncSession,
    feedback_id: str,
    query_id: str,
    feedback_type: str,
    citation_id: str | None,
    description: str,
    submitted_by: str,
) -> ResponseFeedback:
    """Create a feedback record."""
    fb = ResponseFeedback(
        id=feedback_id,
        query_id=query_id,
        feedback_type=feedback_type,
        citation_id=citation_id,
        description=description,
        submitted_by=submitted_by,
    )
    db.add(fb)
    await db.flush()
    return fb


async def get_feedback(db: AsyncSession, feedback_id: str) -> FeedbackDetail | None:
    result = await db.execute(
        select(ResponseFeedback).where(ResponseFeedback.id == feedback_id)
    )
    fb = result.scalar_one_or_none()
    if not fb:
        return None
    return _fb_to_detail(fb)


async def list_feedback(
    db: AsyncSession,
    status: str | None = None,
    feedback_type: str | None = None,
    limit: int = 50,
) -> list[FeedbackDetail]:
    query = select(ResponseFeedback).order_by(ResponseFeedback.submitted_at.desc())
    if status:
        query = query.where(ResponseFeedback.status == status)
    if feedback_type:
        query = query.where(ResponseFeedback.feedback_type == feedback_type)
    query = query.limit(limit)

    result = await db.execute(query)
    return [_fb_to_detail(fb) for fb in result.scalars().all()]


async def resolve_feedback(
    db: AsyncSession,
    feedback_id: str,
    resolution: str,
    status: str = "resolved",
) -> FeedbackDetail | None:
    result = await db.execute(
        select(ResponseFeedback).where(ResponseFeedback.id == feedback_id)
    )
    fb = result.scalar_one_or_none()
    if not fb:
        return None

    fb.status = FeedbackStatus(status)
    fb.resolution = resolution
    fb.resolved_at = datetime.now(UTC)
    await db.commit()
    return _fb_to_detail(fb)


def _fb_to_detail(fb: ResponseFeedback) -> FeedbackDetail:
    return FeedbackDetail(
        id=fb.id,
        query_id=fb.query_id,
        feedback_type=fb.feedback_type,
        citation_id=fb.citation_id,
        description=fb.description,
        submitted_by=fb.submitted_by,
        status=fb.status,
        resolution=fb.resolution,
        traced_source_id=fb.traced_source_id,
        traced_manifest_id=fb.traced_manifest_id,
        traced_document_id=fb.traced_document_id,
        auto_action=fb.auto_action,
        submitted_at=fb.submitted_at,
        resolved_at=fb.resolved_at,
    )


# --- Curation Queue ---


async def list_curation_queue(
    db: AsyncSession, status: str | None = None, limit: int = 50
) -> list[CurationQueueItemSchema]:
    query = select(CurationQueueItem).order_by(
        CurationQueueItem.priority,
        CurationQueueItem.created_at,
    )
    if status:
        query = query.where(CurationQueueItem.status == status)
    query = query.limit(limit)

    result = await db.execute(query)
    return [
        CurationQueueItemSchema(
            id=item.id,
            source_id=item.source_id,
            manifest_id=item.manifest_id,
            priority=item.priority,
            reason=item.reason,
            trigger_type=item.trigger_type,
            feedback_id=item.feedback_id,
            change_event_id=item.change_event_id,
            status=item.status,
            result=item.result,
            created_at=item.created_at,
            processed_at=item.processed_at,
        )
        for item in result.scalars().all()
    ]


async def process_queue_item(
    db: AsyncSession, item_id: str
) -> CurationQueueItemSchema | None:
    """Mark a queue item as processing (actual re-curation is triggered externally)."""
    result = await db.execute(
        select(CurationQueueItem).where(CurationQueueItem.id == item_id)
    )
    item = result.scalar_one_or_none()
    if not item:
        return None

    item.status = CurationQueueStatus.processing
    item.processed_at = datetime.now(UTC)
    await db.commit()

    return CurationQueueItemSchema(
        id=item.id,
        source_id=item.source_id,
        manifest_id=item.manifest_id,
        priority=item.priority,
        reason=item.reason,
        trigger_type=item.trigger_type,
        feedback_id=item.feedback_id,
        change_event_id=item.change_event_id,
        status=item.status,
        result=item.result,
        created_at=item.created_at,
        processed_at=item.processed_at,
    )


# --- Change Events ---


async def list_changes(
    db: AsyncSession, status: str | None = None, limit: int = 50
) -> list[ChangeEventSchema]:
    query = select(ChangeEvent).order_by(ChangeEvent.detected_at.desc())
    if status:
        query = query.where(ChangeEvent.status == status)
    query = query.limit(limit)

    result = await db.execute(query)
    return [
        ChangeEventSchema(
            id=evt.id,
            source_id=evt.source_id,
            manifest_id=evt.manifest_id,
            detection_method=evt.detection_method,
            change_type=evt.change_type,
            previous_hash=evt.previous_hash,
            current_hash=evt.current_hash,
            description=evt.description,
            status=evt.status,
            impact_assessment=evt.impact_assessment,
            detected_at=evt.detected_at,
            resolved_at=evt.resolved_at,
        )
        for evt in result.scalars().all()
    ]


async def get_change(db: AsyncSession, event_id: str) -> ChangeEventSchema | None:
    result = await db.execute(
        select(ChangeEvent).where(ChangeEvent.id == event_id)
    )
    evt = result.scalar_one_or_none()
    if not evt:
        return None
    return ChangeEventSchema(
        id=evt.id,
        source_id=evt.source_id,
        manifest_id=evt.manifest_id,
        detection_method=evt.detection_method,
        change_type=evt.change_type,
        previous_hash=evt.previous_hash,
        current_hash=evt.current_hash,
        description=evt.description,
        status=evt.status,
        impact_assessment=evt.impact_assessment,
        detected_at=evt.detected_at,
        resolved_at=evt.resolved_at,
    )


# --- Accuracy Dashboard ---


async def get_accuracy_dashboard(db: AsyncSession) -> AccuracyDashboardData:
    """Compute accuracy metrics from feedback, sources, and queue state."""
    # Feedback counts by type
    type_counts: dict[str, int] = {}
    for ftype in FeedbackType:
        count = (
            await db.execute(
                select(func.count()).select_from(ResponseFeedback).where(
                    ResponseFeedback.feedback_type == ftype
                )
            )
        ).scalar() or 0
        type_counts[ftype.value] = count

    total = sum(type_counts.values())
    correct = type_counts.get("correct", 0)
    inaccurate = type_counts.get("inaccurate", 0)
    outdated = type_counts.get("outdated", 0)
    incomplete = type_counts.get("incomplete", 0)
    irrelevant = type_counts.get("irrelevant", 0)

    # Accuracy score: correct / (correct + inaccurate) if any exist
    accuracy_denominator = correct + inaccurate
    accuracy_score = correct / accuracy_denominator if accuracy_denominator > 0 else 1.0

    # Resolution rate
    resolved = (
        await db.execute(
            select(func.count()).select_from(ResponseFeedback).where(
                ResponseFeedback.status.in_(["resolved", "dismissed"])
            )
        )
    ).scalar() or 0
    resolution_rate = resolved / total if total > 0 else 1.0

    # Average source confidence
    avg_conf = (
        await db.execute(select(func.avg(Source.confidence)))
    ).scalar() or 0.0

    # Pending queue items
    pending_queue = (
        await db.execute(
            select(func.count()).select_from(CurationQueueItem).where(
                CurationQueueItem.status == CurationQueueStatus.pending
            )
        )
    ).scalar() or 0

    # Unresolved changes
    unresolved_changes = (
        await db.execute(
            select(func.count()).select_from(ChangeEvent).where(
                ChangeEvent.status.in_(["detected", "processing"])
            )
        )
    ).scalar() or 0

    current = AccuracyMetrics(
        total_feedback=total,
        correct_count=correct,
        inaccurate_count=inaccurate,
        outdated_count=outdated,
        incomplete_count=incomplete,
        irrelevant_count=irrelevant,
        accuracy_score=round(accuracy_score, 3),
        resolution_rate=round(resolution_rate, 3),
        avg_source_confidence=round(float(avg_conf), 3),
        stale_sources=0,
        pending_queue_items=pending_queue,
        unresolved_changes=unresolved_changes,
    )

    # Trends from snapshots
    trend_result = await db.execute(
        select(AccuracySnapshot)
        .order_by(AccuracySnapshot.snapshot_date.desc())
        .limit(30)
    )
    snapshots = trend_result.scalars().all()
    trends = [
        AccuracyTrendPoint(
            date=s.snapshot_date.strftime("%Y-%m-%d"),
            accuracy_score=s.accuracy_score,
            total_feedback=s.total_feedback,
            resolution_rate=s.resolution_rate,
        )
        for s in reversed(snapshots)
    ]

    # By vertical (coverage scores)
    vert_result = await db.execute(
        select(Vertical.name, Vertical.coverage_score).where(
            Vertical.coverage_score > 0
        )
    )
    by_vertical = {name: score for name, score in vert_result.all()}

    return AccuracyDashboardData(
        current=current,
        trends=trends,
        by_feedback_type=type_counts,
        by_vertical=by_vertical,
    )
