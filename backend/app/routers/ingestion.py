"""Ingestion and curation endpoints — Phase 3."""

import asyncio
import json
import logging

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession
from sse_starlette.sse import EventSourceResponse

from app.database import async_session, get_db
from app.ingestion.indexer import get_index_stats
from app.ingestion.orchestrator import IngestionOrchestrator
from app.schemas.ingestion import (
    DocumentDetail,
    DocumentSummary,
    IndexStats,
    IngestionRunDetail,
    StartIngestionRequest,
    StartIngestionResponse,
)
from app.services import ingestion_service

logger = logging.getLogger(__name__)
router = APIRouter(tags=["ingestion"])

# In-memory SSE event queues per ingestion run
_event_queues: dict[str, asyncio.Queue] = {}


# --- Ingestion Run endpoints ---


@router.post("/api/ingestion/run", status_code=202, response_model=StartIngestionResponse)
async def start_ingestion(
    request: StartIngestionRequest,
    background_tasks: BackgroundTasks,
    db: AsyncSession = Depends(get_db),
):
    run = await ingestion_service.create_ingestion_run(db, request.acquisition_id)
    if not run:
        raise HTTPException(
            status_code=409,
            detail="Acquisition run not found",
        )

    _event_queues[run.id] = asyncio.Queue()
    background_tasks.add_task(_run_ingestion, run.id)

    return StartIngestionResponse(
        ingestion_id=run.id,
        acquisition_id=run.acquisition_id,
        manifest_id=run.manifest_id,
        status="running",
        total_documents=run.total_documents,
        stream_url=f"/api/ingestion/{run.id}/stream",
    )


async def _run_ingestion(ingestion_id: str):
    """Run ingestion orchestrator in background, pushing events to SSE queue."""
    queue = _event_queues.get(ingestion_id)
    try:
        async with async_session() as db:
            orchestrator = IngestionOrchestrator(db=db, ingestion_run_id=ingestion_id)
            async for event in orchestrator.run():
                if queue:
                    await queue.put(event)
    except Exception:
        logger.exception("Ingestion run failed for %s", ingestion_id)
        if queue:
            await queue.put({
                "event": "error",
                "data": {"message": "Ingestion run failed. Check server logs."},
            })
    finally:
        if queue:
            await queue.put(None)


@router.get("/api/ingestion/{ingestion_id}/stream")
async def stream_ingestion_progress(ingestion_id: str):
    queue = _event_queues.get(ingestion_id)
    if not queue:
        raise HTTPException(status_code=404, detail="No active ingestion for this ID")

    async def event_generator():
        while True:
            event = await queue.get()
            if event is None:
                break
            yield {
                "event": event.get("event", "message"),
                "data": json.dumps(event.get("data", {})),
            }
        _event_queues.pop(ingestion_id, None)

    return EventSourceResponse(event_generator())


@router.get("/api/ingestion/{ingestion_id}", response_model=IngestionRunDetail)
async def get_ingestion(
    ingestion_id: str, db: AsyncSession = Depends(get_db)
):
    result = await ingestion_service.get_ingestion_run(db, ingestion_id)
    if not result:
        raise HTTPException(status_code=404, detail="Ingestion run not found")
    return result


@router.get("/api/ingestion/{ingestion_id}/documents", response_model=list[DocumentSummary])
async def list_ingestion_documents(
    ingestion_id: str, db: AsyncSession = Depends(get_db)
):
    docs = await ingestion_service.list_documents(db, ingestion_id)
    if docs is None:
        raise HTTPException(status_code=404, detail="Ingestion run not found")
    return docs


# --- Document endpoints ---


@router.get("/api/documents/{doc_id}", response_model=DocumentDetail)
async def get_document(
    doc_id: str, db: AsyncSession = Depends(get_db)
):
    doc = await ingestion_service.get_document(db, doc_id)
    if not doc:
        raise HTTPException(status_code=404, detail="Document not found")
    return doc


class RejectRequest(BaseModel):
    reason: str = ""


@router.patch("/api/documents/{doc_id}/approve")
async def approve_document(doc_id: str, db: AsyncSession = Depends(get_db)):
    doc = await ingestion_service.approve_document(db, doc_id)
    if not doc:
        raise HTTPException(status_code=404, detail="Document not found")
    return {"document_id": doc.id, "status": doc.status}


@router.patch("/api/documents/{doc_id}/reject")
async def reject_document(
    doc_id: str,
    body: RejectRequest | None = None,
    db: AsyncSession = Depends(get_db),
):
    reason = body.reason if body else ""
    doc = await ingestion_service.reject_document(db, doc_id, reason)
    if not doc:
        raise HTTPException(status_code=404, detail="Document not found")
    return {"document_id": doc.id, "status": doc.status}


# --- Index stats ---


@router.get("/api/index/stats", response_model=IndexStats)
async def index_stats(db: AsyncSession = Depends(get_db)):
    stats = await get_index_stats(db)
    return IndexStats(**stats)
