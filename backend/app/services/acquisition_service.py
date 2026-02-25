from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models.acquisition import (
    AcquisitionRun,
    AcquisitionSource,
    AcquisitionStatus,
    SourceAcqStatus,
)
from app.models.manifest import Manifest, ManifestStatus
from app.schemas.acquisition import (
    AcquisitionRunDetail,
    AcquisitionRunSummary,
    AcquisitionSourceStatus,
)


async def create_acquisition_run(
    db: AsyncSession, manifest_id: str
) -> AcquisitionRun | None:
    """Create an acquisition run from an approved manifest."""
    # Verify manifest is approved
    result = await db.execute(
        select(Manifest)
        .options(selectinload(Manifest.sources))
        .where(Manifest.id == manifest_id)
    )
    manifest = result.scalar_one_or_none()
    if not manifest or manifest.status != ManifestStatus.approved:
        return None

    # Generate acquisition ID
    timestamp = datetime.now(UTC).strftime("%Y%m%d%H%M%S")
    acq_id = f"acq-{timestamp}"

    # Create the run
    run = AcquisitionRun(
        id=acq_id,
        manifest_id=manifest_id,
        status=AcquisitionStatus.pending,
        total_sources=len(manifest.sources),
    )
    db.add(run)

    # Create acquisition source entries for each manifest source
    for source in manifest.sources:
        acq_source = AcquisitionSource(
            acquisition_id=acq_id,
            source_id=source.id,
            manifest_id=manifest_id,
            name=source.name,
            regulatory_body=source.regulatory_body_id,
            url=source.url,
            access_method=source.access_method.value,
            status=SourceAcqStatus.pending,
        )
        db.add(acq_source)

    await db.commit()
    await db.refresh(run)
    return run


async def get_acquisition_run(
    db: AsyncSession, acquisition_id: str
) -> AcquisitionRunDetail | None:
    result = await db.execute(
        select(AcquisitionRun)
        .options(selectinload(AcquisitionRun.sources))
        .where(AcquisitionRun.id == acquisition_id)
    )
    run = result.scalar_one_or_none()
    if not run:
        return None

    now = datetime.now(UTC)
    elapsed = (now - run.started_at.replace(tzinfo=UTC)).total_seconds() if run.started_at else 0

    counts = _count_statuses(run.sources)

    return AcquisitionRunDetail(
        acquisition_id=run.id,
        manifest_id=run.manifest_id,
        status=run.status,
        started_at=run.started_at,
        elapsed_seconds=elapsed,
        total_sources=run.total_sources,
        **counts,
    )


async def list_acquisition_runs(db: AsyncSession) -> list[AcquisitionRunSummary]:
    result = await db.execute(
        select(AcquisitionRun)
        .options(selectinload(AcquisitionRun.sources))
        .order_by(AcquisitionRun.started_at.desc())
    )
    runs = result.scalars().all()
    return [
        AcquisitionRunSummary(
            acquisition_id=r.id,
            manifest_id=r.manifest_id,
            status=r.status,
            started_at=r.started_at,
            total_sources=r.total_sources,
            completed=sum(1 for s in r.sources if s.status == SourceAcqStatus.complete),
            failed=sum(1 for s in r.sources if s.status == SourceAcqStatus.failed),
        )
        for r in runs
    ]


async def get_acquisition_sources(
    db: AsyncSession, acquisition_id: str
) -> list[AcquisitionSourceStatus] | None:
    result = await db.execute(
        select(AcquisitionRun)
        .options(selectinload(AcquisitionRun.sources))
        .where(AcquisitionRun.id == acquisition_id)
    )
    run = result.scalar_one_or_none()
    if not run:
        return None

    return [
        AcquisitionSourceStatus(
            source_id=s.source_id,
            name=s.name,
            regulatory_body=s.regulatory_body,
            access_method=s.access_method,
            status=s.status,
            duration_ms=s.duration_ms,
            staged_document_id=s.staged_document_id,
            error=s.error_message,
            retry_count=s.retry_count,
        )
        for s in run.sources
    ]


async def get_single_source(
    db: AsyncSession, acquisition_id: str, source_id: str
) -> AcquisitionSourceStatus | None:
    result = await db.execute(
        select(AcquisitionSource).where(
            AcquisitionSource.acquisition_id == acquisition_id,
            AcquisitionSource.source_id == source_id,
        )
    )
    s = result.scalar_one_or_none()
    if not s:
        return None

    return AcquisitionSourceStatus(
        source_id=s.source_id,
        name=s.name,
        regulatory_body=s.regulatory_body,
        access_method=s.access_method,
        status=s.status,
        duration_ms=s.duration_ms,
        staged_document_id=s.staged_document_id,
        error=s.error_message,
        retry_count=s.retry_count,
    )


async def retry_source(
    db: AsyncSession, acquisition_id: str, source_id: str
) -> AcquisitionSource | None:
    result = await db.execute(
        select(AcquisitionSource).where(
            AcquisitionSource.acquisition_id == acquisition_id,
            AcquisitionSource.source_id == source_id,
        )
    )
    source = result.scalar_one_or_none()
    if not source:
        return None

    source.status = SourceAcqStatus.retrying
    source.error_message = None
    await db.commit()
    return source


def _count_statuses(sources: list[AcquisitionSource]) -> dict:
    completed = sum(1 for s in sources if s.status == SourceAcqStatus.complete)
    failed = sum(1 for s in sources if s.status == SourceAcqStatus.failed)
    retrying = sum(1 for s in sources if s.status == SourceAcqStatus.retrying)
    pending = sum(
        1 for s in sources
        if s.status in (SourceAcqStatus.pending, SourceAcqStatus.running)
    )
    return {
        "completed": completed,
        "failed": failed,
        "retrying": retrying,
        "pending": pending,
    }
