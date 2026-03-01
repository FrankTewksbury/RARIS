import asyncio
import csv
import io
import json
import logging
from datetime import UTC, datetime
from pathlib import Path

import pdfplumber
from docx import Document
from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Request, UploadFile
from fastapi.exceptions import RequestValidationError
from pydantic import ValidationError
from sqlalchemy.ext.asyncio import AsyncSession
from starlette.datastructures import UploadFile as StarletteUploadFile
from sse_starlette.sse import EventSourceResponse

from app.agent.discovery import DomainDiscoveryAgent
from app.config import settings
from app.database import async_session, get_db
from app.llm.registry import get_provider, resolve_provider_name
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
ALLOWED_UPLOAD_EXTENSIONS = {".txt", ".md", ".pdf", ".docx"}
ALLOWED_SEED_EXTENSIONS = {".json", ".jsonl", ".csv", ".txt", ".md"}

# In-memory store for SSE event queues per manifest
_event_queues: dict[str, asyncio.Queue] = {}


@router.post("/generate", status_code=202, response_model=GenerateManifestResponse)
async def generate_manifest(
    request: Request,
    background_tasks: BackgroundTasks,
    db: AsyncSession = Depends(get_db),
):
    payload = await _parse_generate_request(request)

    # Generate manifest ID
    domain = payload.domain_description.strip()
    timestamp = datetime.now(UTC).strftime("%Y%m%d%H%M%S")
    domain_slug = domain[:30].lower().replace(" ", "-")
    manifest_id = f"raris-manifest-{domain_slug}-{timestamp}"

    # Create manifest record
    manifest = Manifest(
        id=manifest_id,
        domain=domain,
        status=ManifestStatus.generating,
        created_by="domain-discovery-agent-v1",
    )
    db.add(manifest)
    await db.commit()

    # Set up event queue for SSE
    _event_queues[manifest_id] = asyncio.Queue()

    # Launch agent in background
    background_tasks.add_task(
        _run_agent,
        manifest_id,
        domain,
        payload.llm_provider,
        payload.k_depth,
        payload.geo_scope,
        payload.target_segments,
        payload.seed_anchors,
        payload.seed_programs,
        payload.seed_metrics,
        payload.constitution_text,
        payload.instruction_text,
    )

    return GenerateManifestResponse(
        manifest_id=manifest_id,
        status="generating",
        stream_url=f"/api/manifests/{manifest_id}/stream",
    )


class _GeneratePayload:
    def __init__(
        self,
        domain_description: str,
        llm_provider: str,
        k_depth: int,
        geo_scope: str,
        target_segments: list[str],
        seed_anchors: list[dict],
        seed_programs: list[dict],
        seed_metrics: dict,
        constitution_text: str = "",
        instruction_text: str = "",
    ) -> None:
        self.domain_description = domain_description
        self.llm_provider = llm_provider
        self.k_depth = k_depth
        self.geo_scope = geo_scope
        self.target_segments = target_segments
        self.seed_anchors = seed_anchors
        self.seed_programs = seed_programs
        self.seed_metrics = seed_metrics
        self.constitution_text = constitution_text
        self.instruction_text = instruction_text


def _raise_missing_domain_validation() -> None:
    raise RequestValidationError(
        [
            {
                "type": "missing",
                "loc": ("body", "domain_description"),
                "msg": "Field required",
                "input": None,
            }
        ]
    )


def _ensure_allowed_file(upload: UploadFile) -> str:
    extension = Path(upload.filename or "").suffix.lower()
    if extension not in ALLOWED_UPLOAD_EXTENSIONS:
        raise HTTPException(
            status_code=422,
            detail=f"Unsupported file type '{extension}'. Allowed: .txt, .md, .pdf, .docx",
        )
    return extension


def _ensure_allowed_seed_file(upload: UploadFile) -> str:
    extension = Path(upload.filename or "").suffix.lower()
    if extension not in ALLOWED_SEED_EXTENSIONS:
        raise HTTPException(
            status_code=422,
            detail=f"Unsupported seed file type '{extension}'. Allowed: .json, .jsonl, .csv, .txt, .md",
        )
    return extension


async def _extract_upload_text(upload: UploadFile) -> str:
    extension = _ensure_allowed_file(upload)
    content = await upload.read()
    if not content:
        return ""

    if extension in {".txt", ".md"}:
        try:
            return content.decode("utf-8")
        except UnicodeDecodeError:
            return content.decode("utf-8", errors="ignore")

    if extension == ".pdf":
        pages: list[str] = []
        with pdfplumber.open(io.BytesIO(content)) as pdf:
            for page in pdf.pages:
                page_text = page.extract_text() or ""
                if page_text.strip():
                    pages.append(page_text.strip())
        return "\n\n".join(pages)

    if extension == ".docx":
        document = Document(io.BytesIO(content))
        paragraphs = [paragraph.text.strip() for paragraph in document.paragraphs if paragraph.text.strip()]
        return "\n\n".join(paragraphs)

    return ""


def _classify_seed_record(record: dict) -> str:
    program_markers = {"program_name", "administering_entity", "benefits", "eligibility", "provider"}
    if program_markers.intersection(set(record.keys())):
        return "program_seed"
    if "name" in record and ("benefits" in record or "eligibility" in record):
        return "program_seed"
    return "anchor_seed"


# ---------------------------------------------------------------------------
# Program type inference — maps seeds to taxonomy categories for topic-indexed
# injection during hierarchical discovery (L1 entity expansion).
# See research/003-analysis-dpa-program-taxonomy.md for the full taxonomy.
# ---------------------------------------------------------------------------

_PROGRAM_TYPE_KEYWORDS: dict[str, list[str]] = {
    "veteran": ["veteran", "va ", "military", "service member", "armed forces"],
    "tribal": ["tribal", "native american", "alaska native", "section 184", "indian"],
    "occupation": [
        "teacher", "firefighter", "police", "ems", "good neighbor",
        "gnnd", "first responder", "law enforcement", "educator",
    ],
    "cdfi": ["cdfi", "community development financial"],
    "eah": ["employer", "workforce housing", "employee homeownership"],
    "municipal": [
        "city of", "county of", "cdbg", "home funds", "block grant",
        "municipal", "town of", "village of",
    ],
    "lmi": ["low income", "moderate income", "lmi", "80% ami", "120% ami"],
    "fthb": ["first-time", "first time", "fthb", "homebuyer"],
}


def _infer_program_type(record: dict) -> str:
    """Infer program_type from seed record fields using keyword matching.

    An explicit ``program_type`` or ``category`` field in the record takes
    precedence over keyword inference.
    """
    explicit = record.get("program_type") or record.get("category")
    if explicit:
        return str(explicit).lower().strip()

    searchable = " ".join([
        str(record.get("name", "")),
        str(record.get("program_name", "")),
        str(record.get("administering_entity", "")),
        str(record.get("provider", "")),
        str(record.get("agency", "")),
        str(record.get("benefits", "")),
        str(record.get("eligibility", "")),
    ]).lower()

    for ptype, keywords in _PROGRAM_TYPE_KEYWORDS.items():
        if any(kw in searchable for kw in keywords):
            return ptype
    return "general"


def _index_seeds_by_type(seeds: list[dict]) -> dict[str, list[dict]]:
    """Group seed records by their ``program_type`` field.

    Returns a dict mapping program type strings to lists of seed records.
    Seeds without a ``program_type`` key default to ``"general"``.
    """
    index: dict[str, list[dict]] = {}
    for seed in seeds:
        ptype = seed.get("program_type", "general")
        index.setdefault(ptype, []).append(seed)
    return index


def _normalize_program_seed(record: dict) -> dict:
    return {
        "name": record.get("program_name") or record.get("name") or "Seed Program",
        "administering_entity": record.get("administering_entity")
        or record.get("provider")
        or record.get("agency")
        or "Unknown",
        "geo_scope": record.get("geo_scope") or "state",
        "jurisdiction": record.get("jurisdiction"),
        "benefits": record.get("benefits"),
        "eligibility": record.get("eligibility"),
        "program_type": _infer_program_type(record),
        "status": record.get("status") or "verification_pending",
        "evidence_snippet": record.get("evidence_snippet") or record.get("evidence"),
        "source_urls": record.get("source_urls") or ([record["url"]] if record.get("url") else []),
        "provenance_links": {
            "seed_file": record.get("__seed_file"),
            "seed_row": record.get("__seed_row"),
            "seed_type": "program_seed",
        },
        "confidence": float(record.get("confidence", 0.5) or 0.5),
        "needs_human_review": bool(record.get("needs_human_review", False)),
    }


async def _parse_seed_upload(upload: UploadFile) -> tuple[list[dict], list[dict], dict]:
    extension = _ensure_allowed_seed_file(upload)
    filename = upload.filename or "seed-file"
    content = await upload.read()
    if not content:
        return [], [], {"file": filename, "status": "invalid", "accepted": 0, "rejected": 0}

    records: list[dict] = []
    try:
        if extension == ".json":
            parsed = json.loads(content.decode("utf-8"))
            if isinstance(parsed, dict):
                if isinstance(parsed.get("records"), list):
                    records = [item for item in parsed["records"] if isinstance(item, dict)]
                else:
                    records = [parsed]
            elif isinstance(parsed, list):
                records = [item for item in parsed if isinstance(item, dict)]
        elif extension == ".jsonl":
            for idx, raw_line in enumerate(content.decode("utf-8").splitlines(), start=1):
                line = raw_line.strip()
                if not line:
                    continue
                item = json.loads(line)
                if isinstance(item, dict):
                    item["__seed_row"] = idx
                    records.append(item)
        elif extension == ".csv":
            decoded = content.decode("utf-8")
            reader = csv.DictReader(io.StringIO(decoded))
            for idx, row in enumerate(reader, start=1):
                item = dict(row)
                item["__seed_row"] = idx
                records.append(item)
        else:
            text = content.decode("utf-8", errors="ignore")
            for idx, raw_line in enumerate(text.splitlines(), start=1):
                line = raw_line.strip()
                if not line:
                    continue
                records.append({"url": line, "__seed_row": idx})
    except (UnicodeDecodeError, json.JSONDecodeError, csv.Error):
        return [], [], {"file": filename, "status": "invalid", "accepted": 0, "rejected": 1}

    anchor_seeds: list[dict] = []
    program_seeds: list[dict] = []
    rejected = 0
    for idx, record in enumerate(records, start=1):
        record["__seed_file"] = filename
        record.setdefault("__seed_row", idx)
        if _classify_seed_record(record) == "program_seed":
            program_seeds.append(_normalize_program_seed(record))
            continue
        if not record.get("url") and not record.get("name"):
            rejected += 1
            continue
        anchor_seeds.append(record)

    metrics = {
        "file": filename,
        "status": "parsed",
        "accepted": len(anchor_seeds) + len(program_seeds),
        "rejected": rejected,
        "anchors": len(anchor_seeds),
        "programs": len(program_seeds),
    }
    return anchor_seeds, program_seeds, metrics


async def _parse_generate_request(request: Request) -> _GeneratePayload:
    content_type = request.headers.get("content-type", "").lower()

    if "application/json" in content_type:
        body = await request.json()
        try:
            parsed = GenerateManifestRequest.model_validate(body)
        except ValidationError as exc:
            raise RequestValidationError(exc.errors()) from exc
        if not parsed.domain_description.strip():
            _raise_missing_domain_validation()
        return _GeneratePayload(
            domain_description=parsed.domain_description,
            llm_provider=resolve_provider_name(parsed.llm_provider),
            k_depth=parsed.k_depth,
            geo_scope=parsed.geo_scope,
            target_segments=parsed.target_segments,
            seed_anchors=[],
            seed_programs=[],
            seed_metrics={},
        )

    if "multipart/form-data" in content_type or "application/x-www-form-urlencoded" in content_type:
        form = await request.form()
        raw_target_segments = form.get("target_segments")
        target_segments: list[str]
        if raw_target_segments is None:
            target_segments = []
        elif isinstance(raw_target_segments, str):
            target_segments = [
                segment.strip()
                for segment in raw_target_segments.split(",")
                if segment.strip()
            ]
        else:
            target_segments = []

        raw_k_depth = str(form.get("k_depth", "2")).strip() or "2"
        try:
            k_depth = int(raw_k_depth)
        except ValueError:
            raise RequestValidationError(
                [
                    {
                        "type": "int_parsing",
                        "loc": ("body", "k_depth"),
                        "msg": "Input should be a valid integer",
                        "input": raw_k_depth,
                    }
                ]
            ) from None
        form_payload = {
            "domain_description": str(form.get("domain_description", "")).strip(),
            "llm_provider": str(form.get("llm_provider", settings.llm_provider)).strip()
            or settings.llm_provider,
            "k_depth": k_depth,
            "geo_scope": str(form.get("geo_scope", "state")).strip() or "state",
            "target_segments": target_segments,
        }
        try:
            parsed = GenerateManifestRequest.model_validate(form_payload)
        except ValidationError as exc:
            raise RequestValidationError(exc.errors()) from exc
        if not parsed.domain_description.strip():
            _raise_missing_domain_validation()

        constitution_upload = form.get("constitution_file")
        instruction_upload = form.get("instruction_file")
        seed_uploads = form.getlist("seeding_files")

        constitution_text = ""
        if isinstance(constitution_upload, (UploadFile, StarletteUploadFile)):
            constitution_text = await _extract_upload_text(constitution_upload)

        instruction_text = ""
        if isinstance(instruction_upload, (UploadFile, StarletteUploadFile)):
            instruction_text = await _extract_upload_text(instruction_upload)

        seed_anchors: list[dict] = []
        seed_programs: list[dict] = []
        file_metrics: list[dict] = []
        for upload in seed_uploads:
            if not isinstance(upload, (UploadFile, StarletteUploadFile)):
                continue
            anchors, programs, metrics = await _parse_seed_upload(upload)
            seed_anchors.extend(anchors)
            seed_programs.extend(programs)
            file_metrics.append(metrics)

        return _GeneratePayload(
            domain_description=parsed.domain_description,
            llm_provider=resolve_provider_name(parsed.llm_provider),
            k_depth=parsed.k_depth,
            geo_scope=parsed.geo_scope,
            target_segments=parsed.target_segments,
            seed_anchors=seed_anchors,
            seed_programs=seed_programs,
            seed_metrics={
                "files": file_metrics,
                "anchor_count": len(seed_anchors),
                "program_count": len(seed_programs),
                "queue_priority": [
                    "program_seed",
                    "anchor_seed",
                    "model_discovered",
                ],
            },
            constitution_text=constitution_text,
            instruction_text=instruction_text,
        )

    raise HTTPException(status_code=415, detail="Unsupported content type")


async def _run_agent(
    manifest_id: str,
    domain_description: str,
    llm_provider: str,
    k_depth: int = 2,
    geo_scope: str = "state",
    target_segments: list[str] | None = None,
    seed_anchors: list[dict] | None = None,
    seed_programs: list[dict] | None = None,
    seed_metrics: dict | None = None,
    constitution_text: str = "",
    instruction_text: str = "",
):
    """Run the discovery agent in background and push events to the queue."""
    queue = _event_queues.get(manifest_id)
    try:
        provider = get_provider(llm_provider)
        async with async_session() as db:
            agent = DomainDiscoveryAgent(llm=provider, db=db, manifest_id=manifest_id)
            async for event in agent.run(
                domain_description,
                k_depth=k_depth,
                geo_scope=geo_scope,
                target_segments=target_segments or [],
                seed_anchors=seed_anchors or [],
                seed_programs=seed_programs or [],
                seed_metrics=seed_metrics or {},
                constitution_text=constitution_text,
                instruction_text=instruction_text,
            ):
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
