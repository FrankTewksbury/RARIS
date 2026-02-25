import asyncio
import json
import logging
from datetime import UTC, datetime

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sse_starlette.sse import EventSourceResponse

from app.agent.discovery import DomainDiscoveryAgent
from app.database import async_session, get_db
from app.llm.registry import get_provider
from app.models.manifest import Manifest, ManifestStatus
from app.schemas.manifest import (
    GenerateManifestRequest,
    GenerateManifestResponse,
    ManifestDetail,
    ManifestListResponse,
    ReviewRequest,
    ReviewResponse,
    SourceCreate,
    SourceResponse,
    SourceUpdate,
)
from app.services import manifest_service

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/manifests", tags=["manifests"])

# In-memory store for SSE event queues per manifest
_event_queues: dict[str, asyncio.Queue] = {}


@router.post("/generate", status_code=202, response_model=GenerateManifestResponse)
async def generate_manifest(
    request: GenerateManifestRequest,
    background_tasks: BackgroundTasks,
    db: AsyncSession = Depends(get_db),
):
    # Generate manifest ID
    timestamp = datetime.now(UTC).strftime("%Y%m%d%H%M%S")
    domain_slug = request.domain_description[:30].lower().replace(" ", "-")
    manifest_id = f"raris-manifest-{domain_slug}-{timestamp}"

    # Create manifest record
    manifest = Manifest(
        id=manifest_id,
        domain=request.domain_description,
        status=ManifestStatus.generating,
        created_by="domain-discovery-agent-v1",
    )
    db.add(manifest)
    await db.commit()

    # Set up event queue for SSE
    _event_queues[manifest_id] = asyncio.Queue()

    # Launch agent in background
    background_tasks.add_task(
        _run_agent, manifest_id, request.domain_description, request.llm_provider
    )

    return GenerateManifestResponse(
        manifest_id=manifest_id,
        status="generating",
        stream_url=f"/api/manifests/{manifest_id}/stream",
    )


async def _run_agent(manifest_id: str, domain_description: str, llm_provider: str):
    """Run the discovery agent in background and push events to the queue."""
    queue = _event_queues.get(manifest_id)
    try:
        provider = get_provider(llm_provider)
        async with async_session() as db:
            agent = DomainDiscoveryAgent(llm=provider, db=db, manifest_id=manifest_id)
            async for event in agent.run(domain_description):
                if queue:
                    await queue.put(event)
    except Exception:
        logger.exception("Agent run failed for manifest %s", manifest_id)
        if queue:
            await queue.put({
                "event": "error",
                "data": {"message": "Agent run failed. Check server logs."},
            })
        # Update manifest status
        async with async_session() as db:
            manifest = await db.get(Manifest, manifest_id)
            if manifest:
                manifest.status = ManifestStatus.pending_review
                await db.commit()
    finally:
        if queue:
            await queue.put(None)  # Sentinel to close SSE stream


@router.get("/{manifest_id}/stream")
async def stream_manifest_progress(manifest_id: str):
    queue = _event_queues.get(manifest_id)
    if not queue:
        raise HTTPException(status_code=404, detail="No active generation for this manifest")

    async def event_generator():
        while True:
            event = await queue.get()
            if event is None:
                break
            yield {
                "event": event.get("event", "message"),
                "data": json.dumps(event.get("data", {})),
            }
        # Clean up
        _event_queues.pop(manifest_id, None)

    return EventSourceResponse(event_generator())


@router.get("/{manifest_id}", response_model=ManifestDetail)
async def get_manifest(manifest_id: str, db: AsyncSession = Depends(get_db)):
    result = await manifest_service.get_manifest(db, manifest_id)
    if not result:
        raise HTTPException(status_code=404, detail="Manifest not found")
    return result


@router.get("", response_model=ManifestListResponse)
async def list_manifests(db: AsyncSession = Depends(get_db)):
    manifests = await manifest_service.list_manifests(db)
    return ManifestListResponse(manifests=manifests)


@router.patch("/{manifest_id}/sources/{source_id}", response_model=SourceResponse)
async def update_source(
    manifest_id: str,
    source_id: str,
    update: SourceUpdate,
    db: AsyncSession = Depends(get_db),
):
    result = await manifest_service.update_source(db, manifest_id, source_id, update)
    if not result:
        raise HTTPException(status_code=404, detail="Source not found")
    return result


@router.post("/{manifest_id}/sources", status_code=201, response_model=SourceResponse)
async def add_source(
    manifest_id: str,
    create: SourceCreate,
    db: AsyncSession = Depends(get_db),
):
    result = await manifest_service.add_source(db, manifest_id, create)
    if not result:
        raise HTTPException(status_code=404, detail="Manifest not found")
    return result


@router.post("/{manifest_id}/approve", response_model=ReviewResponse)
async def approve_manifest(
    manifest_id: str,
    request: ReviewRequest,
    db: AsyncSession = Depends(get_db),
):
    result = await manifest_service.approve_manifest(
        db, manifest_id, request.reviewer, request.notes
    )
    if not result:
        raise HTTPException(status_code=404, detail="Manifest not found")
    if "error" in result:
        raise HTTPException(status_code=409, detail=result["error"])
    return ReviewResponse(
        manifest_id=result["manifest_id"],
        status=result["status"],
        approved_at=result.get("approved_at"),
    )


@router.post("/{manifest_id}/reject", response_model=ReviewResponse)
async def reject_manifest(
    manifest_id: str,
    request: ReviewRequest,
    db: AsyncSession = Depends(get_db),
):
    result = await manifest_service.reject_manifest(
        db, manifest_id, request.reviewer, request.notes
    )
    if not result:
        raise HTTPException(status_code=404, detail="Manifest not found")
    return ReviewResponse(
        manifest_id=result["manifest_id"],
        status=result["status"],
        rejection_notes=result.get("rejection_notes"),
    )
