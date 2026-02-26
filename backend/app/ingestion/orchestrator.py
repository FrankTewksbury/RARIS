"""Ingestion orchestrator — processes staged documents through the full pipeline."""

import logging
import pathlib
from collections.abc import AsyncIterator
from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.ingestion.base import ExtractedSection
from app.ingestion.chunker import chunk_document
from app.ingestion.curation import run_curation
from app.ingestion.indexer import index_document
from app.ingestion.registry import get_adapter
from app.models.acquisition import (
    AcquisitionSource,
    StagedDocument,
)
from app.models.ingestion import (
    Chunk,
    CurationStatus,
    DocumentSection,
    DocumentTable,
    IngestionRun,
    IngestionRunStatus,
    InternalDocument,
)
from app.models.manifest import Source

logger = logging.getLogger(__name__)


class IngestionOrchestrator:
    """Processes an acquisition run's staged documents through ingestion."""

    def __init__(self, db: AsyncSession, ingestion_run_id: str):
        self.db = db
        self.run_id = ingestion_run_id

    async def run(self) -> AsyncIterator[dict]:
        """Execute the ingestion pipeline, yielding SSE events."""
        # Load the ingestion run
        result = await self.db.execute(
            select(IngestionRun).where(IngestionRun.id == self.run_id)
        )
        run = result.scalar_one_or_none()
        if not run:
            yield {"event": "error", "data": "Ingestion run not found"}
            return

        run.status = IngestionRunStatus.running
        await self.db.flush()

        # Load staged documents from the acquisition run
        acq_result = await self.db.execute(
            select(AcquisitionSource)
            .where(AcquisitionSource.acquisition_id == run.acquisition_id)
            .where(AcquisitionSource.staged_document_id.isnot(None))
        )
        acq_sources = acq_result.scalars().all()

        total = len(acq_sources)
        run.total_documents = total
        await self.db.flush()

        yield {
            "event": "started",
            "data": {"run_id": self.run_id, "total_documents": total},
        }

        processed = 0
        failed = 0

        for acq_src in acq_sources:
            try:
                yield {
                    "event": "document_start",
                    "data": {
                        "source_id": acq_src.source_id,
                        "name": acq_src.name,
                    },
                }

                doc_id = f"doc-{run.manifest_id}-{acq_src.source_id}"

                # Load staged document
                stg_result = await self.db.execute(
                    select(StagedDocument).where(
                        StagedDocument.id == acq_src.staged_document_id
                    )
                )
                staged = stg_result.scalar_one_or_none()
                if not staged:
                    raise ValueError(f"Staged document {acq_src.staged_document_id} not found")

                # Load manifest source for metadata
                src_result = await self.db.execute(
                    select(Source).where(
                        Source.id == acq_src.source_id,
                        Source.manifest_id == run.manifest_id,
                    )
                )
                manifest_source = src_result.scalar_one_or_none()
                source_meta = _source_to_dict(manifest_source) if manifest_source else {}

                # Read raw content from staging
                content = _read_staged_content(staged.raw_content_path)

                # Select and run adapter
                source_format = source_meta.get("format", "")
                adapter = get_adapter(staged.content_type, source_format)
                extracted = await adapter.ingest(content, source_url=acq_src.url)

                # Create InternalDocument record
                doc = InternalDocument(
                    id=doc_id,
                    ingestion_run_id=self.run_id,
                    manifest_id=run.manifest_id,
                    source_id=acq_src.source_id,
                    staged_document_id=staged.id,
                    title=extracted.title,
                    full_text=extracted.full_text,
                    jurisdiction=source_meta.get("jurisdiction", ""),
                    regulatory_body=source_meta.get("regulatory_body", ""),
                    authority_level=source_meta.get("authority", "informational"),
                    document_type=source_meta.get("type", "guidance"),
                    classification_tags=source_meta.get("classification_tags", []),
                    status=CurationStatus.raw,
                )
                self.db.add(doc)
                await self.db.flush()

                # Persist sections
                _persist_sections(self.db, doc_id, extracted.sections)

                # Persist tables
                for tbl in extracted.tables:
                    self.db.add(DocumentTable(
                        id=f"{doc_id}-{tbl.id}",
                        document_id=doc_id,
                        section_id=tbl.section_id,
                        caption=tbl.caption,
                        headers=tbl.headers,
                        rows=tbl.rows,
                    ))

                await self.db.flush()

                # Run curation pipeline
                curation = await run_curation(doc, extracted, source_meta, self.db)
                doc.status = curation.status
                doc.quality_score = curation.quality_score
                doc.quality_gates = curation.quality_gates
                doc.curation_notes = curation.curation_notes
                doc.effective_date = curation.effective_date
                doc.cross_references = curation.cross_references
                doc.content_hash = curation.content_hash
                doc.curated_at = datetime.now(UTC)
                await self.db.flush()

                # Chunk if approved or validated
                if doc.status in (CurationStatus.approved, CurationStatus.validated):
                    chunks = chunk_document(extracted.sections, doc_id)
                    for c in chunks:
                        self.db.add(Chunk(
                            id=f"chk-{doc_id}-{c.position:04d}",
                            document_id=doc_id,
                            section_id=c.section_id,
                            section_path=c.section_path,
                            text=c.text,
                            token_count=c.token_count,
                            position=c.position,
                        ))
                    await self.db.flush()

                    # Index if approved
                    if doc.status == CurationStatus.approved:
                        # Reload doc with chunks
                        await self.db.refresh(doc, attribute_names=["chunks"])
                        indexed_count = await index_document(doc, self.db)
                        yield {
                            "event": "document_indexed",
                            "data": {
                                "source_id": acq_src.source_id,
                                "chunks_indexed": indexed_count,
                            },
                        }

                processed += 1
                run.processed = processed
                await self.db.flush()

                yield {
                    "event": "document_complete",
                    "data": {
                        "source_id": acq_src.source_id,
                        "name": acq_src.name,
                        "status": doc.status,
                        "quality_score": doc.quality_score,
                        "processed": processed,
                        "failed": failed,
                        "total": total,
                    },
                }

            except Exception as exc:
                logger.exception("Failed to ingest source %s", acq_src.source_id)
                failed += 1
                run.failed = failed
                await self.db.flush()

                yield {
                    "event": "document_failed",
                    "data": {
                        "source_id": acq_src.source_id,
                        "name": acq_src.name,
                        "error": str(exc),
                        "processed": processed,
                        "failed": failed,
                        "total": total,
                    },
                }

        # Finalize run
        run.status = IngestionRunStatus.complete
        run.completed_at = datetime.now(UTC)
        await self.db.commit()

        yield {
            "event": "complete",
            "data": {
                "run_id": self.run_id,
                "total": total,
                "processed": processed,
                "failed": failed,
            },
        }


def _source_to_dict(source: Source) -> dict:
    """Convert a manifest Source ORM object to a dict for the curation pipeline."""
    return {
        "jurisdiction": source.jurisdiction.value if source.jurisdiction else "",
        "regulatory_body": source.regulatory_body_id or "",
        "authority": source.authority.value if source.authority else "informational",
        "type": source.type.value if source.type else "guidance",
        "format": source.format.value if source.format else "",
        "classification_tags": source.classification_tags or [],
        "relationships": source.relationships or {},
        "estimated_size": source.estimated_size or "",
    }


def _read_staged_content(path: str) -> str | bytes:
    """Read content from the staging directory."""
    p = pathlib.Path(path)
    if not p.exists():
        raise FileNotFoundError(f"Staged content not found: {path}")

    suffix = p.suffix.lower()
    if suffix in (".pdf",):
        return p.read_bytes()
    return p.read_text(encoding="utf-8", errors="replace")


def _persist_sections(
    db: AsyncSession, doc_id: str, sections: list[ExtractedSection], parent_id: str | None = None
) -> None:
    """Recursively persist sections to the database."""
    for i, section in enumerate(sections):
        section_db_id = f"{doc_id}-{section.id}"
        db.add(DocumentSection(
            id=section_db_id,
            document_id=doc_id,
            parent_id=parent_id,
            heading=section.heading,
            level=section.level,
            text=section.text,
            position=i,
        ))
        if section.children:
            _persist_sections(db, doc_id, section.children, parent_id=section_db_id)
