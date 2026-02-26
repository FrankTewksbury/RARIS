"""Ingestion service — CRUD and business logic for ingestion runs and documents."""

from datetime import UTC, datetime

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models.acquisition import AcquisitionRun
from app.models.ingestion import (
    Chunk,
    CurationStatus,
    IngestionRun,
    IngestionRunStatus,
    InternalDocument,
)
from app.schemas.ingestion import (
    DocumentDetail,
    DocumentSummary,
    IngestionRunDetail,
    IngestionRunSummary,
)


async def create_ingestion_run(
    db: AsyncSession, acquisition_id: str
) -> IngestionRun | None:
    """Create an ingestion run from a completed acquisition run."""
    result = await db.execute(
        select(AcquisitionRun).where(AcquisitionRun.id == acquisition_id)
    )
    acq_run = result.scalar_one_or_none()
    if not acq_run:
        return None

    timestamp = datetime.now(UTC).strftime("%Y%m%d%H%M%S")
    run_id = f"ing-{timestamp}"

    run = IngestionRun(
        id=run_id,
        acquisition_id=acquisition_id,
        manifest_id=acq_run.manifest_id,
        status=IngestionRunStatus.pending,
    )
    db.add(run)
    await db.commit()
    await db.refresh(run)
    return run


async def get_ingestion_run(
    db: AsyncSession, ingestion_id: str
) -> IngestionRunDetail | None:
    result = await db.execute(
        select(IngestionRun).where(IngestionRun.id == ingestion_id)
    )
    run = result.scalar_one_or_none()
    if not run:
        return None

    return IngestionRunDetail(
        ingestion_id=run.id,
        acquisition_id=run.acquisition_id,
        manifest_id=run.manifest_id,
        status=run.status,
        started_at=run.started_at,
        completed_at=run.completed_at,
        total_documents=run.total_documents,
        processed=run.processed,
        failed=run.failed,
    )


async def list_ingestion_runs(db: AsyncSession) -> list[IngestionRunSummary]:
    result = await db.execute(
        select(IngestionRun).order_by(IngestionRun.started_at.desc())
    )
    runs = result.scalars().all()
    return [
        IngestionRunSummary(
            ingestion_id=r.id,
            acquisition_id=r.acquisition_id,
            manifest_id=r.manifest_id,
            status=r.status,
            started_at=r.started_at,
            total_documents=r.total_documents,
            processed=r.processed,
            failed=r.failed,
        )
        for r in runs
    ]


async def list_documents(
    db: AsyncSession, ingestion_id: str
) -> list[DocumentSummary] | None:
    result = await db.execute(
        select(IngestionRun).where(IngestionRun.id == ingestion_id)
    )
    if not result.scalar_one_or_none():
        return None

    docs_result = await db.execute(
        select(InternalDocument).where(
            InternalDocument.ingestion_run_id == ingestion_id
        )
    )
    docs = docs_result.scalars().all()

    summaries = []
    for d in docs:
        chunk_count = (
            await db.execute(
                select(func.count()).select_from(Chunk).where(Chunk.document_id == d.id)
            )
        ).scalar() or 0

        summaries.append(DocumentSummary(
            document_id=d.id,
            source_id=d.source_id,
            title=d.title,
            status=d.status,
            quality_score=d.quality_score,
            document_type=d.document_type,
            jurisdiction=d.jurisdiction,
            regulatory_body=d.regulatory_body,
            chunk_count=chunk_count,
        ))

    return summaries


async def get_document(
    db: AsyncSession, doc_id: str
) -> DocumentDetail | None:
    result = await db.execute(
        select(InternalDocument)
        .options(
            selectinload(InternalDocument.sections),
            selectinload(InternalDocument.tables),
            selectinload(InternalDocument.chunks),
        )
        .where(InternalDocument.id == doc_id)
    )
    doc = result.scalar_one_or_none()
    if not doc:
        return None

    return DocumentDetail(
        document_id=doc.id,
        source_id=doc.source_id,
        staged_document_id=doc.staged_document_id,
        manifest_id=doc.manifest_id,
        title=doc.title,
        full_text_preview=doc.full_text[:500] if doc.full_text else "",
        status=doc.status,
        quality_score=doc.quality_score,
        quality_gates=doc.quality_gates or {},
        curation_notes=doc.curation_notes or [],
        effective_date=doc.effective_date,
        jurisdiction=doc.jurisdiction,
        regulatory_body=doc.regulatory_body,
        authority_level=doc.authority_level,
        document_type=doc.document_type,
        classification_tags=doc.classification_tags or [],
        cross_references=doc.cross_references or [],
        section_count=len(doc.sections),
        table_count=len(doc.tables),
        chunk_count=len(doc.chunks),
        created_at=doc.created_at,
        curated_at=doc.curated_at,
    )


async def approve_document(db: AsyncSession, doc_id: str) -> InternalDocument | None:
    """Approve a document for indexing."""
    result = await db.execute(
        select(InternalDocument).where(InternalDocument.id == doc_id)
    )
    doc = result.scalar_one_or_none()
    if not doc:
        return None

    doc.status = CurationStatus.approved
    doc.curated_at = datetime.now(UTC)
    doc.curation_notes = (doc.curation_notes or []) + ["Manually approved"]
    await db.commit()
    return doc


async def reject_document(
    db: AsyncSession, doc_id: str, reason: str = ""
) -> InternalDocument | None:
    """Reject a document."""
    result = await db.execute(
        select(InternalDocument).where(InternalDocument.id == doc_id)
    )
    doc = result.scalar_one_or_none()
    if not doc:
        return None

    doc.status = CurationStatus.rejected
    doc.curated_at = datetime.now(UTC)
    note = f"Rejected: {reason}" if reason else "Rejected manually"
    doc.curation_notes = (doc.curation_notes or []) + [note]
    await db.commit()
    return doc
