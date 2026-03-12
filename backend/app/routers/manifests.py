import asyncio
import csv
import io
import json
import logging
from datetime import UTC, datetime
from pathlib import Path

import pdfplumber
from docx import Document
from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Query, Request, UploadFile
from fastapi.exceptions import RequestValidationError
from pydantic import ValidationError
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from starlette.datastructures import UploadFile as StarletteUploadFile
from sse_starlette.sse import EventSourceResponse

from app.config import settings
from app.database import async_session, get_db
from app.llm.registry import get_provider, resolve_provider_name
from app.models.manifest import LogicalRunStatus, Manifest, ManifestStatus
from app.schemas.manifest import (
    GenerateManifestRequest,
    GenerateManifestResponse,
    GoldenRunDetailResponse,
    GoldenRunListResponse,
    GoldenRunSummaryResponse,
    GoldenProgramListResponse,
    GoldenProgramResponse,
    GoldenProgramStatsResponse,
    LogicalRunListResponse,
    LogicalRunResponse,
    ManifestDetail,
    ManifestListResponse,
    MergeManifestsRequest,
    MergeManifestsResponse,
    PromoteGoldenRunRequest,
    PromoteGoldenRunResponse,
    ReviewRequest,
    ReviewResponse,
    SourceCreate,
    SourceResponse,
    SourceUpdate,
)
from app.services import ensemble_service, golden_run_service, manifest_service

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/manifests", tags=["manifests"])
golden_router = APIRouter(prefix="/api/golden-programs", tags=["golden-programs"])
golden_runs_router = APIRouter(prefix="/api/golden-runs", tags=["golden-runs"])
ALLOWED_UPLOAD_EXTENSIONS = {".txt", ".md", ".pdf", ".docx"}
ALLOWED_SEED_EXTENSIONS = {".json", ".jsonl", ".csv", ".txt", ".md"}
ALLOWED_SECTOR_EXTENSIONS = {".json"}

# In-memory store for SSE event queues per manifest
_event_queues: dict[str, asyncio.Queue] = {}


async def _reconcile_orphaned_generating_manifests(
    db: AsyncSession,
    *,
    manifest_id: str | None = None,
) -> set[str]:
    """Mark DB rows as no longer generating when their in-memory SSE queue is gone."""
    stmt = select(Manifest).where(Manifest.status == ManifestStatus.generating)
    if manifest_id:
        stmt = stmt.where(Manifest.id == manifest_id)

    result = await db.execute(stmt)
    manifests = result.scalars().all()
    reconciled: set[str] = set()
    for manifest in manifests:
        if manifest.id in _event_queues:
            continue
        manifest.status = ManifestStatus.pending_review
        reconciled.add(manifest.id)

    if reconciled:
        await db.commit()
        logger.warning(
            "[manifests] reconciled %d orphaned generating manifest(s): %s",
            len(reconciled),
            ", ".join(sorted(reconciled)),
        )

    return reconciled


@router.post("/generate", status_code=202, response_model=GenerateManifestResponse)
async def generate_manifest(
    request: Request,
    background_tasks: BackgroundTasks,
    db: AsyncSession = Depends(get_db),
):
    payload = await _parse_generate_request(request)

    # Generate manifest ID
    domain = payload.manifest_name.strip()
    timestamp = datetime.now(UTC).strftime("%Y%m%d%H%M%S")
    domain_slug = domain[:30].lower().replace(" ", "-")
    manifest_id = f"raris-manifest-{domain_slug}-{timestamp}"

    # Create manifest record
    manifest = Manifest(
        id=manifest_id,
        domain=domain,
        status=ManifestStatus.generating,
        created_by="domain-discovery-agent-v1",
        run_params={
            "llm_provider": payload.llm_provider,
            "llm_model": payload.llm_model,
            "k_depth": payload.k_depth,
            "geo_scope": payload.geo_scope,
        },
    )
    db.add(manifest)
    await db.commit()
    await golden_run_service.create_logical_run_for_manifest(db, manifest)

    # Set up event queue for SSE
    _event_queues[manifest_id] = asyncio.Queue()

    # Launch agent in background — always V5 BFS engine
    background_tasks.add_task(
        _run_agent,
        manifest_id,
        domain,
        payload.llm_provider,
        payload.llm_model,
        payload.k_depth,
        payload.geo_scope,
        payload.target_segments,
        payload.sectors,
        payload.seed_anchors,
        payload.seed_programs,
        payload.seed_metrics,
        payload.constitution_text,
        payload.instruction_texts,
    )

    return GenerateManifestResponse(
        manifest_id=manifest_id,
        status="generating",
        stream_url=f"/api/manifests/{manifest_id}/stream",
    )


@router.post("/merge", response_model=MergeManifestsResponse)
async def merge_manifests(
    request: MergeManifestsRequest,
    db: AsyncSession = Depends(get_db),
):
    stats = await ensemble_service.merge_manifests(db, request.manifest_ids)
    return MergeManifestsResponse(**stats)


@router.get("/logical-runs", response_model=LogicalRunListResponse)
async def list_logical_runs(
    domain: str | None = Query(default=None),
    db: AsyncSession = Depends(get_db),
):
    runs = await golden_run_service.list_logical_runs(db, domain=domain)
    return LogicalRunListResponse(
        runs=[
            LogicalRunResponse(
                run_id=run.run_id,
                manifest_id=run.manifest_id,
                domain=run.domain,
                status=run.status.value,
                created_at=run.created_at,
                promoted_to_golden_run_id=run.promoted_to_golden_run_id,
                notes=run.notes,
            )
            for run in runs
        ]
    )


class _GeneratePayload:
    def __init__(
        self,
        manifest_name: str,
        llm_provider: str,
        llm_model: str | None,
        k_depth: int,
        geo_scope: str,
        target_segments: list[str],
        sectors: list[dict],
        seed_anchors: list[dict],
        seed_programs: list[dict],
        seed_metrics: dict,
        constitution_text: str = "",
        instruction_texts: list[str] | None = None,
    ) -> None:
        self.manifest_name = manifest_name
        self.llm_provider = llm_provider
        self.llm_model = llm_model
        self.k_depth = k_depth
        self.geo_scope = geo_scope
        self.target_segments = target_segments
        self.sectors = sectors
        self.seed_anchors = seed_anchors
        self.seed_programs = seed_programs
        self.seed_metrics = seed_metrics
        self.constitution_text = constitution_text
        self.instruction_texts: list[str] = instruction_texts or []


def _raise_missing_domain_validation() -> None:
    raise RequestValidationError(
        [
            {
                "type": "missing",
                "loc": ("body", "manifest_name"),
                "msg": "Field required",
                "input": None,
            }
        ]
    )


def _raise_missing_instruction_validation(field_name: str = "instruction_text") -> None:
    raise RequestValidationError(
        [
            {
                "type": "missing",
                "loc": ("body", field_name),
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


async def _parse_sector_upload(upload: UploadFile) -> list[dict]:
    """Parse a sector config JSON file.

    Expected format: list of objects with at minimum ``key`` and ``label`` fields.
    Returns empty list on any parse failure so the engine can build neutral runtime
    sectors instead of loading a domain-specific fallback file.
    """
    extension = Path(upload.filename or "").suffix.lower()
    if extension not in ALLOWED_SECTOR_EXTENSIONS:
        logger.warning("[manifests] sector file '%s' has unsupported extension — ignored", upload.filename)
        return []

    content = await upload.read()
    if not content:
        return []

    try:
        parsed = json.loads(content.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        logger.warning("[manifests] sector file parse error: %s — using runtime fallback sectors", exc)
        return []

    if not isinstance(parsed, list):
        logger.warning("[manifests] sector file must be a JSON array — using runtime fallback sectors")
        return []

    sectors: list[dict] = []
    for item in parsed:
        if not isinstance(item, dict):
            continue
        if not item.get("key") or not item.get("label"):
            logger.warning("[manifests] sector entry missing key/label — skipped: %s", item)
            continue
        sector: dict = {
            "key": str(item["key"]),
            "label": str(item["label"]),
            "priority": int(item.get("priority", len(sectors) + 1)),
            "search_hints": list(item.get("search_hints", [])),
            "completeness_requirements": list(item.get("completeness_requirements", [])),
            "sector_prompt": str(item.get("sector_prompt", "")),
            "expected_entity_types": list(item.get("expected_entity_types", [])),
        }
        sectors.append(sector)

    if not sectors:
        logger.warning("[manifests] sector file contained no valid entries — using runtime fallback sectors")

    return sectors


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
        if not parsed.manifest_name.strip():
            _raise_missing_domain_validation()
        if not (parsed.instruction_text or "").strip():
            _raise_missing_instruction_validation()
        return _GeneratePayload(
            manifest_name=parsed.manifest_name,
            llm_provider=resolve_provider_name(parsed.llm_provider),
            llm_model=parsed.llm_model,
            k_depth=parsed.k_depth,
            geo_scope=parsed.geo_scope,
            target_segments=parsed.target_segments,
            sectors=[],
            seed_anchors=[],
            seed_programs=[],
            seed_metrics={},
            instruction_texts=[parsed.instruction_text or ""],
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
            "manifest_name": str(form.get("manifest_name", "")).strip(),
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
        if not parsed.manifest_name.strip():
            _raise_missing_domain_validation()

        raw_llm_model = form.get("llm_model")
        llm_model = str(raw_llm_model).strip() if raw_llm_model else None

        constitution_upload = form.get("constitution_file")
        instruction_uploads = form.getlist("instruction_files")
        sector_upload = form.get("sector_file")
        seed_uploads = form.getlist("seeding_files")

        constitution_text = ""
        if isinstance(constitution_upload, (UploadFile, StarletteUploadFile)):
            constitution_text = await _extract_upload_text(constitution_upload)

        instruction_texts: list[str] = []
        for instr_upload in instruction_uploads:
            if isinstance(instr_upload, (UploadFile, StarletteUploadFile)):
                text = await _extract_upload_text(instr_upload)
                if text.strip():
                    instruction_texts.append(text)

        sectors: list[dict] = []
        if isinstance(sector_upload, (UploadFile, StarletteUploadFile)):
            sectors = await _parse_sector_upload(sector_upload)

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

        if not instruction_texts:
            _raise_missing_instruction_validation("instruction_files")

        return _GeneratePayload(
            manifest_name=parsed.manifest_name,
            llm_provider=resolve_provider_name(parsed.llm_provider),
            llm_model=llm_model,
            k_depth=parsed.k_depth,
            geo_scope=parsed.geo_scope,
            target_segments=parsed.target_segments,
            sectors=sectors,
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
            instruction_texts=instruction_texts,
        )

    raise HTTPException(status_code=415, detail="Unsupported content type")


async def _run_agent(
    manifest_id: str,
    manifest_name: str,
    llm_provider: str,
    llm_model: str | None = None,
    k_depth: int = 2,
    geo_scope: str = "state",
    target_segments: list[str] | None = None,
    sectors: list[dict] | None = None,
    seed_anchors: list[dict] | None = None,
    seed_programs: list[dict] | None = None,
    seed_metrics: dict | None = None,
    constitution_text: str = "",
    instruction_texts: list[str] | None = None,
):
    """Run the V5 BFS discovery engine in background and push events to the queue."""
    queue = _event_queues.get(manifest_id)
    try:
        from app.agent.graph_discovery import DiscoveryGraph

        provider = get_provider(llm_provider, model=llm_model)
        seed_index = _index_seeds_by_type(seed_programs or [])
        async with async_session() as db:
            agent = DiscoveryGraph(llm=provider, db=db, manifest_id=manifest_id)
            async for event in agent.run(
                manifest_name,
                k_depth=k_depth,
                geo_scope=geo_scope,
                sectors=sectors or [],
                seed_index=seed_index,
                seed_programs=seed_programs or [],
                seed_anchors=seed_anchors or [],
                constitution_text=constitution_text,
                instruction_texts=instruction_texts or [],
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
        async with async_session() as db:
            manifest = await db.get(Manifest, manifest_id)
            if manifest:
                manifest.status = ManifestStatus.pending_review
                await db.commit()
    finally:
        if queue:
            await queue.put(None)  # Sentinel to close SSE stream


async def _run_agent_resumed(
    manifest_id: str,
    manifest_name: str,
    llm_provider: str,
    llm_model: str | None = None,
    k_depth: int = 2,
    checkpoint: dict | None = None,
):
    """Resume a halted BFS discovery from a checkpoint — skips L1, continues L2."""
    queue = _event_queues.get(manifest_id)
    try:
        from app.agent.graph_discovery import DiscoveryGraph

        provider = get_provider(llm_provider, model=llm_model)
        async with async_session() as db:
            agent = DiscoveryGraph(llm=provider, db=db, manifest_id=manifest_id)
            async for event in agent.run_resumed(
                manifest_name,
                checkpoint=checkpoint or {},
                k_depth=k_depth,
            ):
                if queue:
                    await queue.put(event)
    except Exception:
        logger.exception("Agent resume failed for manifest %s", manifest_id)
        if queue:
            await queue.put({
                "event": "error",
                "data": {"message": "Resume run failed. Check server logs."},
            })
        async with async_session() as db:
            manifest = await db.get(Manifest, manifest_id)
            if manifest:
                manifest.status = ManifestStatus.pending_review
                await db.commit()
    finally:
        if queue:
            await queue.put(None)


@router.post("/{manifest_id}/resume", status_code=202, response_model=GenerateManifestResponse)
async def resume_manifest(
    manifest_id: str,
    background_tasks: BackgroundTasks,
    db: AsyncSession = Depends(get_db),
):
    """Resume a halted discovery run from its last saved checkpoint.

    The manifest must have ``checkpoint_data`` stored (written at L1 boundary or
    every 50 L2 items). L1 is skipped — the BFS queue is restored from the
    checkpoint and expansion continues.
    """
    manifest = await db.get(Manifest, manifest_id)
    if not manifest:
        raise HTTPException(status_code=404, detail="Manifest not found")
    if not manifest.checkpoint_data:
        raise HTTPException(
            status_code=409,
            detail="No checkpoint available for this manifest. Run a fresh generation first.",
        )
    if manifest_id in _event_queues:
        raise HTTPException(
            status_code=409,
            detail="A generation stream for this manifest is already active.",
        )

    manifest.status = ManifestStatus.generating
    await db.commit()

    _event_queues[manifest_id] = asyncio.Queue()

    # Restore original run settings from stored run_params; fall back to config defaults
    run_params = manifest.run_params or {}
    resume_provider = run_params.get("llm_provider") or settings.llm_provider
    resume_model = run_params.get("llm_model") or None
    resume_k_depth = run_params.get("k_depth") or 2

    background_tasks.add_task(
        _run_agent_resumed,
        manifest_id,
        manifest.domain,
        resume_provider,
        resume_model,
        resume_k_depth,
        manifest.checkpoint_data,
    )

    return GenerateManifestResponse(
        manifest_id=manifest_id,
        status="generating",
        stream_url=f"/api/manifests/{manifest_id}/stream",
    )


@router.get("/{manifest_id}/stream")
async def stream_manifest_progress(manifest_id: str, db: AsyncSession = Depends(get_db)):
    queue = _event_queues.get(manifest_id)
    if not queue:
        reconciled = await _reconcile_orphaned_generating_manifests(db, manifest_id=manifest_id)
        if manifest_id in reconciled:
            raise HTTPException(
                status_code=409,
                detail="Generation stream was lost, likely due to a backend restart. Manifest status was reconciled.",
            )
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
    await _reconcile_orphaned_generating_manifests(db, manifest_id=manifest_id)
    result = await manifest_service.get_manifest(db, manifest_id)
    if not result:
        raise HTTPException(status_code=404, detail="Manifest not found")
    return result


@router.get("", response_model=ManifestListResponse)
async def list_manifests(db: AsyncSession = Depends(get_db)):
    await _reconcile_orphaned_generating_manifests(db)
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
    await golden_run_service.set_logical_run_status(
        db, manifest_id, LogicalRunStatus.reviewed
    )
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
    await golden_run_service.set_logical_run_status(
        db, manifest_id, LogicalRunStatus.rejected
    )
    return ReviewResponse(
        manifest_id=result["manifest_id"],
        status=result["status"],
        rejection_notes=result.get("rejection_notes"),
    )


def _to_golden_program_response(program) -> GoldenProgramResponse:
    return GoldenProgramResponse(
        id=program.id,
        domain=getattr(program, "domain", None),
        golden_run_id=getattr(program, "golden_run_id", None),
        merge_key=program.merge_key,
        canonical_id=program.canonical_id,
        name=program.name,
        administering_entity=program.administering_entity,
        geo_scope=program.geo_scope.value,
        jurisdiction=program.jurisdiction,
        benefits=program.benefits,
        eligibility=program.eligibility,
        status=program.status.value,
        last_verified=program.last_verified,
        evidence_snippet=program.evidence_snippet,
        source_urls=program.source_urls or [],
        provenance_links=program.provenance_links or {},
        confidence=program.confidence,
        needs_human_review=program.needs_human_review,
        source_manifest_ids=(
            getattr(program, "source_manifest_ids", None)
            or getattr(program, "source_run_ids", None)
            or []
        ),
        found_by_count=program.found_by_count,
        ensemble_confidence=program.ensemble_confidence,
        merged_at=getattr(program, "merged_at", None) or getattr(program, "created_at", None),
    )


def _to_golden_run_summary(run, current_golden_run_id: str | None) -> GoldenRunSummaryResponse:
    return GoldenRunSummaryResponse(
        golden_run_id=run.id,
        domain=run.domain,
        version=run.version,
        source_run_ids=run.source_run_ids or [],
        accepted_at=run.accepted_at,
        accepted_by=run.accepted_by,
        notes=run.notes,
        strategy=run.strategy,
        item_count=run.item_count,
        is_current=run.id == current_golden_run_id,
    )


@golden_runs_router.post("/promote", response_model=PromoteGoldenRunResponse)
async def promote_golden_run(
    request: PromoteGoldenRunRequest,
    db: AsyncSession = Depends(get_db),
):
    try:
        result = await golden_run_service.promote_to_golden(
            db,
            domain=request.domain.strip(),
            source_run_ids=request.source_run_ids,
            accepted_by=request.accepted_by.strip() or "system",
            notes=request.notes,
        )
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    return PromoteGoldenRunResponse(**result)


@golden_runs_router.get("/runs", response_model=GoldenRunListResponse)
async def list_golden_runs(
    domain: str | None = Query(default=None),
    db: AsyncSession = Depends(get_db),
):
    runs = await golden_run_service.list_golden_runs(db, domain=domain)
    current_golden_run_ids: set[str] = set()
    if domain:
        current = await golden_run_service.get_current_golden_run(db, domain=domain)
        if current:
            current_golden_run_ids.add(current.id)
    else:
        current_golden_run_ids = await golden_run_service.list_current_golden_run_ids(db)
    return GoldenRunListResponse(
        runs=[
            _to_golden_run_summary(
                run,
                run.id if run.id in current_golden_run_ids else None,
            )
            for run in runs
        ]
    )


@golden_runs_router.get("/current", response_model=GoldenRunSummaryResponse)
async def get_current_golden_run(
    domain: str = Query(...),
    db: AsyncSession = Depends(get_db),
):
    run = await golden_run_service.get_current_golden_run(db, domain=domain)
    if not run:
        raise HTTPException(status_code=404, detail="No current golden run for this domain")
    return _to_golden_run_summary(run, run.id)


@golden_runs_router.get("/runs/{golden_run_id}", response_model=GoldenRunDetailResponse)
async def get_golden_run(
    golden_run_id: str,
    db: AsyncSession = Depends(get_db),
):
    run = await golden_run_service.get_golden_run(db, golden_run_id=golden_run_id)
    if not run:
        raise HTTPException(status_code=404, detail="Golden run not found")
    return GoldenRunDetailResponse(
        golden_run_id=run.id,
        domain=run.domain,
        version=run.version,
        source_run_ids=run.source_run_ids or [],
        accepted_at=run.accepted_at,
        accepted_by=run.accepted_by,
        notes=run.notes,
        strategy=run.strategy,
        item_count=run.item_count,
        is_current=False,
        programs=[_to_golden_program_response(item) for item in run.items],
    )


@golden_router.get("", response_model=GoldenProgramListResponse)
async def list_golden_programs(
    offset: int = Query(default=0, ge=0),
    limit: int = Query(default=50, ge=1, le=500),
    domain: str | None = Query(default=None),
    golden_run_id: str | None = Query(default=None),
    geo_scope: str | None = Query(default=None),
    db: AsyncSession = Depends(get_db),
):
    rows, total = await golden_run_service.list_golden_run_items(
        db,
        domain=domain,
        golden_run_id=golden_run_id,
        offset=offset,
        limit=limit,
        geo_scope=geo_scope,
    )
    return GoldenProgramListResponse(
        programs=[_to_golden_program_response(row) for row in rows],
        total=total,
    )


@golden_router.get("/stats", response_model=GoldenProgramStatsResponse)
async def get_golden_program_stats(
    domain: str | None = Query(default=None),
    golden_run_id: str | None = Query(default=None),
    db: AsyncSession = Depends(get_db),
):
    stats = await golden_run_service.golden_program_stats(
        db,
        domain=domain,
        golden_run_id=golden_run_id,
    )
    return GoldenProgramStatsResponse(**stats)
