"""Feedback, re-curation queue, change monitoring, and accuracy endpoints — Phase 6."""

import logging
from datetime import UTC, datetime

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import async_session, get_db
from app.feedback.monitor import run_change_monitor
from app.feedback.tracer import trace_and_act
from app.schemas.feedback import (
    AccuracyDashboardData,
    ChangeEventSchema,
    CurationQueueItemSchema,
    FeedbackDetail,
    ResolveFeedbackRequest,
    SubmitFeedbackRequest,
    TriggerMonitorResponse,
)
from app.services import feedback_service

logger = logging.getLogger(__name__)
router = APIRouter(tags=["feedback"])


# --- Feedback endpoints ---


@router.post("/api/feedback", status_code=201, response_model=FeedbackDetail)
async def submit_feedback(
    request: SubmitFeedbackRequest,
    db: AsyncSession = Depends(get_db),
):
    """Submit feedback on a query response."""
    feedback_id = f"fb-{datetime.now(UTC).strftime('%Y%m%d%H%M%S%f')}"

    fb = await feedback_service.create_feedback(
        db,
        feedback_id=feedback_id,
        query_id=request.query_id,
        feedback_type=request.feedback_type,
        citation_id=request.citation_id,
        description=request.description,
        submitted_by=request.submitted_by,
    )

    # Run tracer to trace citation chain and apply auto-actions
    await trace_and_act(db, fb)
    await db.commit()

    return await feedback_service.get_feedback(db, feedback_id)


@router.get("/api/feedback", response_model=list[FeedbackDetail])
async def list_feedback(
    status: str | None = Query(None),
    feedback_type: str | None = Query(None),
    limit: int = Query(50, ge=1, le=200),
    db: AsyncSession = Depends(get_db),
):
    """List all feedback, filterable by status and type."""
    return await feedback_service.list_feedback(db, status, feedback_type, limit)


@router.get("/api/feedback/{feedback_id}", response_model=FeedbackDetail)
async def get_feedback(
    feedback_id: str, db: AsyncSession = Depends(get_db)
):
    """Get feedback details with trace information."""
    result = await feedback_service.get_feedback(db, feedback_id)
    if not result:
        raise HTTPException(status_code=404, detail="Feedback not found")
    return result


@router.patch("/api/feedback/{feedback_id}/resolve", response_model=FeedbackDetail)
async def resolve_feedback(
    feedback_id: str,
    request: ResolveFeedbackRequest,
    db: AsyncSession = Depends(get_db),
):
    """Mark feedback as resolved or dismissed."""
    result = await feedback_service.resolve_feedback(
        db, feedback_id, request.resolution, request.status
    )
    if not result:
        raise HTTPException(status_code=404, detail="Feedback not found")
    return result


# --- Curation Queue endpoints ---


@router.get("/api/curation-queue", response_model=list[CurationQueueItemSchema])
async def list_curation_queue(
    status: str | None = Query(None),
    limit: int = Query(50, ge=1, le=200),
    db: AsyncSession = Depends(get_db),
):
    """List items in the re-curation queue."""
    return await feedback_service.list_curation_queue(db, status, limit)


@router.post(
    "/api/curation-queue/{item_id}/process",
    response_model=CurationQueueItemSchema,
)
async def process_queue_item(
    item_id: str, db: AsyncSession = Depends(get_db)
):
    """Trigger re-curation for a queued item."""
    result = await feedback_service.process_queue_item(db, item_id)
    if not result:
        raise HTTPException(status_code=404, detail="Queue item not found")
    return result


# --- Change Monitoring endpoints ---


@router.get("/api/changes", response_model=list[ChangeEventSchema])
async def list_changes(
    status: str | None = Query(None),
    limit: int = Query(50, ge=1, le=200),
    db: AsyncSession = Depends(get_db),
):
    """List detected regulatory changes."""
    return await feedback_service.list_changes(db, status, limit)


@router.get("/api/changes/{event_id}", response_model=ChangeEventSchema)
async def get_change(
    event_id: str, db: AsyncSession = Depends(get_db)
):
    """Get change event details."""
    result = await feedback_service.get_change(db, event_id)
    if not result:
        raise HTTPException(status_code=404, detail="Change event not found")
    return result


@router.post("/api/monitor/run", status_code=202, response_model=TriggerMonitorResponse)
async def trigger_monitor(
    background_tasks: BackgroundTasks,
    db: AsyncSession = Depends(get_db),
):
    """Trigger a manual change monitoring run."""
    background_tasks.add_task(_bg_monitor)
    return TriggerMonitorResponse(
        sources_checked=0,
        changes_detected=0,
        message="Monitor run started in background",
    )


# --- Accuracy Dashboard ---


@router.get("/api/accuracy/dashboard", response_model=AccuracyDashboardData)
async def accuracy_dashboard(db: AsyncSession = Depends(get_db)):
    """Accuracy metrics and trends."""
    return await feedback_service.get_accuracy_dashboard(db)


# --- Background tasks ---


async def _bg_monitor():
    try:
        async with async_session() as db:
            result = await run_change_monitor(db)
            logger.info(
                "Monitor run complete: %d checked, %d changes",
                result["sources_checked"],
                result["changes_detected"],
            )
    except Exception:
        logger.exception("Background monitor run failed")
