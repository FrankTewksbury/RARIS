"""Vertical service — CRUD, pipeline state management, cross-vertical stats."""

import logging
from datetime import UTC, datetime

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.ingestion import Chunk, CurationStatus, InternalDocument
from app.models.manifest import CoverageAssessment, Source
from app.models.vertical import PipelinePhase, Vertical
from app.schemas.vertical import (
    PipelinePhaseStatus,
    ScopeConfig,
    VerticalDetail,
    VerticalPipelineStatus,
    VerticalSummary,
)

logger = logging.getLogger(__name__)


async def create_vertical(
    db: AsyncSession,
    vertical_id: str,
    name: str,
    domain_description: str,
    scope: ScopeConfig,
    llm_provider: str = "openai",
    expected_source_count_min: int = 100,
    expected_source_count_max: int = 300,
    coverage_target: float = 0.85,
    rate_limit_ms: int = 2000,
    max_concurrent: int = 5,
    timeout_seconds: int = 120,
) -> Vertical:
    """Create a new vertical configuration."""
    vertical = Vertical(
        id=vertical_id,
        name=name,
        domain_description=domain_description,
        scope=scope.model_dump(),
        llm_provider=llm_provider,
        expected_source_count_min=expected_source_count_min,
        expected_source_count_max=expected_source_count_max,
        coverage_target=coverage_target,
        rate_limit_ms=rate_limit_ms,
        max_concurrent=max_concurrent,
        timeout_seconds=timeout_seconds,
    )
    db.add(vertical)
    await db.commit()
    return vertical


async def get_vertical(db: AsyncSession, vertical_id: str) -> VerticalDetail | None:
    """Get vertical with full detail and pipeline status."""
    result = await db.execute(
        select(Vertical).where(Vertical.id == vertical_id)
    )
    v = result.scalar_one_or_none()
    if not v:
        return None

    pipeline = await _build_pipeline_status(db, v)

    return VerticalDetail(
        id=v.id,
        name=v.name,
        domain_description=v.domain_description,
        scope=ScopeConfig(**v.scope) if v.scope else ScopeConfig(),
        llm_provider=v.llm_provider,
        expected_source_count_min=v.expected_source_count_min,
        expected_source_count_max=v.expected_source_count_max,
        coverage_target=v.coverage_target,
        rate_limit_ms=v.rate_limit_ms,
        max_concurrent=v.max_concurrent,
        timeout_seconds=v.timeout_seconds,
        phase=v.phase,
        manifest_id=v.manifest_id,
        acquisition_id=v.acquisition_id,
        ingestion_id=v.ingestion_id,
        source_count=v.source_count,
        document_count=v.document_count,
        chunk_count=v.chunk_count,
        coverage_score=v.coverage_score,
        last_error=v.last_error,
        created_at=v.created_at,
        updated_at=v.updated_at,
        pipeline_status=pipeline,
    )


async def list_verticals(db: AsyncSession) -> list[VerticalSummary]:
    """List all verticals."""
    result = await db.execute(
        select(Vertical).order_by(Vertical.created_at.desc())
    )
    verticals = result.scalars().all()
    return [
        VerticalSummary(
            id=v.id,
            name=v.name,
            domain_description=v.domain_description,
            phase=v.phase,
            source_count=v.source_count,
            document_count=v.document_count,
            chunk_count=v.chunk_count,
            coverage_score=v.coverage_score,
            created_at=v.created_at,
            updated_at=v.updated_at,
        )
        for v in verticals
    ]


async def update_phase(
    db: AsyncSession,
    vertical_id: str,
    phase: PipelinePhase,
    *,
    manifest_id: str | None = None,
    acquisition_id: str | None = None,
    ingestion_id: str | None = None,
    error: str | None = None,
) -> None:
    """Update a vertical's pipeline phase and associated resource IDs."""
    result = await db.execute(
        select(Vertical).where(Vertical.id == vertical_id)
    )
    v = result.scalar_one_or_none()
    if not v:
        return

    v.phase = phase
    v.last_error = error
    v.updated_at = datetime.now(UTC)

    if manifest_id is not None:
        v.manifest_id = manifest_id
    if acquisition_id is not None:
        v.acquisition_id = acquisition_id
    if ingestion_id is not None:
        v.ingestion_id = ingestion_id

    await db.commit()


async def refresh_metrics(db: AsyncSession, vertical_id: str) -> None:
    """Refresh source/document/chunk counts and coverage from linked resources."""
    result = await db.execute(
        select(Vertical).where(Vertical.id == vertical_id)
    )
    v = result.scalar_one_or_none()
    if not v:
        return

    # Source count from manifest
    if v.manifest_id:
        count = (
            await db.execute(
                select(func.count()).select_from(Source).where(
                    Source.manifest_id == v.manifest_id
                )
            )
        ).scalar() or 0
        v.source_count = count

        # Coverage score
        ca = (
            await db.execute(
                select(CoverageAssessment).where(
                    CoverageAssessment.manifest_id == v.manifest_id
                )
            )
        ).scalar_one_or_none()
        if ca:
            v.coverage_score = ca.completeness_score

    # Document count from internal_documents linked to this manifest
    if v.manifest_id:
        doc_count = (
            await db.execute(
                select(func.count()).select_from(InternalDocument).where(
                    InternalDocument.manifest_id == v.manifest_id,
                    InternalDocument.status == CurationStatus.indexed,
                )
            )
        ).scalar() or 0
        v.document_count = doc_count

        # Chunk count
        chunk_count = (
            await db.execute(
                select(func.count())
                .select_from(Chunk)
                .join(InternalDocument, Chunk.document_id == InternalDocument.id)
                .where(
                    InternalDocument.manifest_id == v.manifest_id,
                    Chunk.embedding.isnot(None),
                )
            )
        ).scalar() or 0
        v.chunk_count = chunk_count

    v.updated_at = datetime.now(UTC)
    await db.commit()


async def get_pipeline_status(
    db: AsyncSession, vertical_id: str
) -> VerticalPipelineStatus | None:
    """Get full pipeline status for a vertical."""
    result = await db.execute(
        select(Vertical).where(Vertical.id == vertical_id)
    )
    v = result.scalar_one_or_none()
    if not v:
        return None

    phases = await _build_pipeline_status(db, v)

    return VerticalPipelineStatus(
        vertical_id=v.id,
        phase=v.phase,
        phases=phases,
        source_count=v.source_count,
        document_count=v.document_count,
        chunk_count=v.chunk_count,
        coverage_score=v.coverage_score,
    )


async def _build_pipeline_status(
    db: AsyncSession, v: Vertical
) -> list[PipelinePhaseStatus]:
    """Build per-phase status list."""
    phase_order = [
        "created", "discovering", "discovered",
        "acquiring", "acquired",
        "ingesting", "indexed",
    ]
    current_idx = phase_order.index(v.phase) if v.phase in phase_order else 0

    phases: list[PipelinePhaseStatus] = []

    # Discovery
    disc_status = "pending"
    if current_idx >= phase_order.index("discovered"):
        disc_status = "complete"
    elif v.phase == "discovering":
        disc_status = "running"
    elif v.phase == "failed" and v.manifest_id is None:
        disc_status = "failed"
    phases.append(PipelinePhaseStatus(
        phase="discovery", status=disc_status, resource_id=v.manifest_id
    ))

    # Acquisition
    acq_status = "pending"
    if current_idx >= phase_order.index("acquired"):
        acq_status = "complete"
    elif v.phase == "acquiring":
        acq_status = "running"
    elif v.phase == "failed" and v.manifest_id and v.acquisition_id is None:
        acq_status = "failed"
    phases.append(PipelinePhaseStatus(
        phase="acquisition", status=acq_status, resource_id=v.acquisition_id
    ))

    # Ingestion
    ing_status = "pending"
    if current_idx >= phase_order.index("indexed"):
        ing_status = "complete"
    elif v.phase == "ingesting":
        ing_status = "running"
    elif v.phase == "failed" and v.acquisition_id and v.ingestion_id is None:
        ing_status = "failed"
    phases.append(PipelinePhaseStatus(
        phase="ingestion", status=ing_status, resource_id=v.ingestion_id
    ))

    # Indexed (terminal)
    idx_status = "complete" if v.phase == "indexed" else "pending"
    phases.append(PipelinePhaseStatus(phase="indexed", status=idx_status))

    return phases
