"""Feedback-to-source tracer — follows citation chains and applies auto-actions."""

import logging
from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.feedback import (
    CurationQueueItem,
    CurationQueuePriority,
    FeedbackType,
    ResponseFeedback,
)
from app.models.manifest import Source
from app.retrieval.citations import build_citation_chain

logger = logging.getLogger(__name__)

# Confidence adjustments by feedback type
_CONFIDENCE_ADJUSTMENTS = {
    FeedbackType.inaccurate: -0.1,
    FeedbackType.correct: 0.05,
}


async def trace_and_act(db: AsyncSession, feedback: ResponseFeedback) -> None:
    """Trace a feedback item back to its source and apply auto-actions.

    Steps:
    1. If citation_id is provided, trace the citation chain
    2. Apply confidence adjustments to the source
    3. Queue re-curation if needed
    """
    # Trace citation chain if citation_id given
    if feedback.citation_id:
        chain = await build_citation_chain(db, feedback.citation_id)
        if chain:
            feedback.traced_source_id = chain.source_id
            feedback.traced_manifest_id = chain.manifest_id
            feedback.traced_document_id = chain.document_id

    ftype = FeedbackType(feedback.feedback_type)

    # Apply auto-actions based on feedback type
    if ftype == FeedbackType.inaccurate:
        feedback.auto_action = "confidence_reduced"
        await _adjust_confidence(db, feedback, -0.1)
        await _queue_for_recuration(
            db, feedback,
            priority=CurationQueuePriority.high,
            reason=f"Inaccuracy reported: {feedback.description[:200]}",
        )

    elif ftype == FeedbackType.outdated:
        feedback.auto_action = "queued_reacquisition"
        await _queue_for_recuration(
            db, feedback,
            priority=CurationQueuePriority.high,
            reason=f"Outdated content reported: {feedback.description[:200]}",
        )

    elif ftype == FeedbackType.incomplete:
        feedback.auto_action = "coverage_gap_flagged"
        await _queue_for_recuration(
            db, feedback,
            priority=CurationQueuePriority.medium,
            reason=f"Coverage gap: {feedback.description[:200]}",
        )

    elif ftype == FeedbackType.irrelevant:
        feedback.auto_action = "logged_for_tuning"
        # No queue action — logged for retrieval tuning

    elif ftype == FeedbackType.correct:
        feedback.auto_action = "confidence_boosted"
        await _adjust_confidence(db, feedback, 0.05)

    await db.flush()


async def _adjust_confidence(
    db: AsyncSession,
    feedback: ResponseFeedback,
    delta: float,
) -> None:
    """Adjust source confidence score based on feedback."""
    if not feedback.traced_source_id or not feedback.traced_manifest_id:
        return

    result = await db.execute(
        select(Source).where(
            Source.id == feedback.traced_source_id,
            Source.manifest_id == feedback.traced_manifest_id,
        )
    )
    source = result.scalar_one_or_none()
    if source:
        new_confidence = max(0.0, min(1.0, source.confidence + delta))
        source.confidence = new_confidence
        if delta < 0:
            source.needs_human_review = True
            source.review_notes = (
                f"Flagged via feedback {feedback.id}: {feedback.feedback_type}"
            )
        await db.flush()


async def _queue_for_recuration(
    db: AsyncSession,
    feedback: ResponseFeedback,
    priority: CurationQueuePriority,
    reason: str,
) -> None:
    """Add a source to the re-curation queue."""
    source_id = feedback.traced_source_id or "unknown"
    manifest_id = feedback.traced_manifest_id or "unknown"

    queue_id = f"rcq-{datetime.now(UTC).strftime('%Y%m%d%H%M%S%f')}"

    item = CurationQueueItem(
        id=queue_id,
        source_id=source_id,
        manifest_id=manifest_id,
        priority=priority,
        reason=reason,
        trigger_type="feedback",
        feedback_id=feedback.id,
    )
    db.add(item)
    await db.flush()
