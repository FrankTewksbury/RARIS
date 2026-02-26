"""Vertical onboarding and pipeline management endpoints — Phase 5."""

import logging
import re
from datetime import UTC, datetime

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import async_session, get_db
from app.schemas.vertical import (
    CreateVerticalRequest,
    TriggerResponse,
    VerticalDetail,
    VerticalPipelineStatus,
    VerticalSummary,
)
from app.services import vertical_service
from app.verticals.pipeline import run_acquisition, run_discovery, run_ingestion

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/verticals", tags=["verticals"])


@router.get("", response_model=list[VerticalSummary])
async def list_verticals(db: AsyncSession = Depends(get_db)):
    """List all configured verticals."""
    return await vertical_service.list_verticals(db)


@router.post("", status_code=201, response_model=VerticalDetail)
async def create_vertical(
    request: CreateVerticalRequest,
    db: AsyncSession = Depends(get_db),
):
    """Create a new vertical configuration."""
    slug = re.sub(r"[^a-z0-9]+", "-", request.name.lower()).strip("-")
    timestamp = datetime.now(UTC).strftime("%Y%m%d%H%M%S")
    vertical_id = f"vert-{slug}-{timestamp}"

    await vertical_service.create_vertical(
        db,
        vertical_id=vertical_id,
        name=request.name,
        domain_description=request.domain_description,
        scope=request.scope,
        llm_provider=request.llm_provider,
        expected_source_count_min=request.expected_source_count_min,
        expected_source_count_max=request.expected_source_count_max,
        coverage_target=request.coverage_target,
        rate_limit_ms=request.rate_limit_ms,
        max_concurrent=request.max_concurrent,
        timeout_seconds=request.timeout_seconds,
    )

    detail = await vertical_service.get_vertical(db, vertical_id)
    return detail


@router.get("/{vertical_id}", response_model=VerticalDetail)
async def get_vertical(
    vertical_id: str, db: AsyncSession = Depends(get_db)
):
    """Get vertical details and pipeline status."""
    detail = await vertical_service.get_vertical(db, vertical_id)
    if not detail:
        raise HTTPException(status_code=404, detail="Vertical not found")
    return detail


@router.post("/{vertical_id}/discover", status_code=202, response_model=TriggerResponse)
async def trigger_discovery(
    vertical_id: str,
    background_tasks: BackgroundTasks,
    db: AsyncSession = Depends(get_db),
):
    """Trigger domain discovery for a vertical."""
    detail = await vertical_service.get_vertical(db, vertical_id)
    if not detail:
        raise HTTPException(status_code=404, detail="Vertical not found")

    if detail.phase not in ("created", "failed"):
        raise HTTPException(
            status_code=409,
            detail=f"Cannot discover in phase '{detail.phase}'. Must be 'created' or 'failed'.",
        )

    background_tasks.add_task(_bg_discover, vertical_id)

    return TriggerResponse(
        vertical_id=vertical_id,
        phase="discovering",
        resource_id="",
        message="Domain discovery started",
    )


@router.post("/{vertical_id}/acquire", status_code=202, response_model=TriggerResponse)
async def trigger_acquisition(
    vertical_id: str,
    background_tasks: BackgroundTasks,
    db: AsyncSession = Depends(get_db),
):
    """Trigger acquisition for a vertical."""
    detail = await vertical_service.get_vertical(db, vertical_id)
    if not detail:
        raise HTTPException(status_code=404, detail="Vertical not found")

    if detail.phase not in ("discovered", "failed"):
        raise HTTPException(
            status_code=409,
            detail=f"Cannot acquire in phase '{detail.phase}'. Must be 'discovered' or 'failed'.",
        )

    background_tasks.add_task(_bg_acquire, vertical_id)

    return TriggerResponse(
        vertical_id=vertical_id,
        phase="acquiring",
        resource_id=detail.manifest_id or "",
        message="Acquisition started",
    )


@router.post("/{vertical_id}/ingest", status_code=202, response_model=TriggerResponse)
async def trigger_ingestion(
    vertical_id: str,
    background_tasks: BackgroundTasks,
    db: AsyncSession = Depends(get_db),
):
    """Trigger ingestion for a vertical."""
    detail = await vertical_service.get_vertical(db, vertical_id)
    if not detail:
        raise HTTPException(status_code=404, detail="Vertical not found")

    if detail.phase not in ("acquired", "failed"):
        raise HTTPException(
            status_code=409,
            detail=f"Cannot ingest in phase '{detail.phase}'. Must be 'acquired' or 'failed'.",
        )

    background_tasks.add_task(_bg_ingest, vertical_id)

    return TriggerResponse(
        vertical_id=vertical_id,
        phase="ingesting",
        resource_id=detail.acquisition_id or "",
        message="Ingestion started",
    )


@router.get("/{vertical_id}/status", response_model=VerticalPipelineStatus)
async def get_pipeline_status(
    vertical_id: str, db: AsyncSession = Depends(get_db)
):
    """Full pipeline status (discovery → indexed)."""
    status = await vertical_service.get_pipeline_status(db, vertical_id)
    if not status:
        raise HTTPException(status_code=404, detail="Vertical not found")
    return status


# --- Background tasks ---


async def _bg_discover(vertical_id: str):
    try:
        async with async_session() as db:
            await run_discovery(db, vertical_id)
    except Exception:
        logger.exception("Background discovery failed for %s", vertical_id)


async def _bg_acquire(vertical_id: str):
    try:
        async with async_session() as db:
            await run_acquisition(db, vertical_id)
    except Exception:
        logger.exception("Background acquisition failed for %s", vertical_id)


async def _bg_ingest(vertical_id: str):
    try:
        async with async_session() as db:
            await run_ingestion(db, vertical_id)
    except Exception:
        logger.exception("Background ingestion failed for %s", vertical_id)
