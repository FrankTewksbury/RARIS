import asyncio
import json
import logging

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sse_starlette.sse import EventSourceResponse

from app.acquisition.orchestrator import AcquisitionOrchestrator
from app.database import async_session, get_db
from app.schemas.acquisition import (
    AcquisitionListResponse,
    AcquisitionRunDetail,
    AcquisitionSourcesResponse,
    AcquisitionSourceStatus,
    RetryResponse,
    StartAcquisitionRequest,
    StartAcquisitionResponse,
)
from app.services import acquisition_service

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/acquisitions", tags=["acquisitions"])

# In-memory SSE event queues per acquisition run
_event_queues: dict[str, asyncio.Queue] = {}


@router.post("", status_code=202, response_model=StartAcquisitionResponse)
async def start_acquisition(
    request: StartAcquisitionRequest,
    background_tasks: BackgroundTasks,
    db: AsyncSession = Depends(get_db),
):
    run = await acquisition_service.create_acquisition_run(db, request.manifest_id)
    if not run:
        raise HTTPException(
            status_code=409,
            detail="Manifest not found or not approved",
        )

    _event_queues[run.id] = asyncio.Queue()

    background_tasks.add_task(_run_acquisition, run.id)

    return StartAcquisitionResponse(
        acquisition_id=run.id,
        manifest_id=run.manifest_id,
        status="running",
        total_sources=run.total_sources,
        stream_url=f"/api/acquisitions/{run.id}/stream",
    )


async def _run_acquisition(acquisition_id: str):
    """Run acquisition orchestrator in background, pushing events to SSE queue."""
    queue = _event_queues.get(acquisition_id)
    try:
        async with async_session() as db:
            orchestrator = AcquisitionOrchestrator(db=db, acquisition_id=acquisition_id)
            async for event in orchestrator.run():
                if queue:
                    await queue.put(event)
    except Exception:
        logger.exception("Acquisition run failed for %s", acquisition_id)
        if queue:
            await queue.put({
                "event": "error",
                "data": {"message": "Acquisition run failed. Check server logs."},
            })
    finally:
        if queue:
            await queue.put(None)


@router.get("/{acquisition_id}/stream")
async def stream_acquisition_progress(acquisition_id: str):
    queue = _event_queues.get(acquisition_id)
    if not queue:
        raise HTTPException(status_code=404, detail="No active acquisition for this ID")

    async def event_generator():
        while True:
            event = await queue.get()
            if event is None:
                break
            yield {
                "event": event.get("event", "message"),
                "data": json.dumps(event.get("data", {})),
            }
        _event_queues.pop(acquisition_id, None)

    return EventSourceResponse(event_generator())


@router.get("/{acquisition_id}", response_model=AcquisitionRunDetail)
async def get_acquisition(
    acquisition_id: str, db: AsyncSession = Depends(get_db)
):
    result = await acquisition_service.get_acquisition_run(db, acquisition_id)
    if not result:
        raise HTTPException(status_code=404, detail="Acquisition run not found")
    return result


@router.get("", response_model=AcquisitionListResponse)
async def list_acquisitions(db: AsyncSession = Depends(get_db)):
    runs = await acquisition_service.list_acquisition_runs(db)
    return AcquisitionListResponse(acquisitions=runs)


@router.get("/{acquisition_id}/sources", response_model=AcquisitionSourcesResponse)
async def get_acquisition_sources(
    acquisition_id: str, db: AsyncSession = Depends(get_db)
):
    sources = await acquisition_service.get_acquisition_sources(db, acquisition_id)
    if sources is None:
        raise HTTPException(status_code=404, detail="Acquisition run not found")
    return AcquisitionSourcesResponse(sources=sources)


@router.get(
    "/{acquisition_id}/sources/{source_id}", response_model=AcquisitionSourceStatus
)
async def get_acquisition_source(
    acquisition_id: str, source_id: str, db: AsyncSession = Depends(get_db)
):
    result = await acquisition_service.get_single_source(db, acquisition_id, source_id)
    if not result:
        raise HTTPException(status_code=404, detail="Source not found")
    return result


@router.post(
    "/{acquisition_id}/sources/{source_id}/retry",
    status_code=202,
    response_model=RetryResponse,
)
async def retry_source(
    acquisition_id: str, source_id: str, db: AsyncSession = Depends(get_db)
):
    source = await acquisition_service.retry_source(db, acquisition_id, source_id)
    if not source:
        raise HTTPException(status_code=404, detail="Source not found")
    return RetryResponse(
        source_id=source.source_id,
        status="retrying",
        retry_count=source.retry_count,
        message="Source re-queued for acquisition",
    )
