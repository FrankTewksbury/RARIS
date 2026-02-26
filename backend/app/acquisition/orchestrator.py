"""Acquisition Orchestrator — routes sources to adapters, manages job queue and retries."""

import asyncio
import logging
from collections.abc import AsyncGenerator
from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.acquisition.api_adapter import fetch_api_source
from app.acquisition.downloader import download_source
from app.acquisition.scraper import scrape_source
from app.models.acquisition import (
    AcquisitionRun,
    AcquisitionSource,
    AcquisitionStatus,
    SourceAcqStatus,
    StagedDocStatus,
    StagedDocument,
)

logger = logging.getLogger(__name__)

MAX_RETRIES = 3
BACKOFF_BASE = 1  # seconds: 1, 4, 16


class AcquisitionOrchestrator:
    """Coordinates acquisition of all sources from an approved manifest."""

    def __init__(self, db: AsyncSession, acquisition_id: str, rate_limit_ms: int = 2000):
        self.db = db
        self.acquisition_id = acquisition_id
        self.rate_limit_ms = rate_limit_ms

    async def run(self) -> AsyncGenerator[dict, None]:
        """Execute acquisition for all sources, yielding SSE events."""
        run = await self.db.get(AcquisitionRun, self.acquisition_id)
        if not run:
            yield {"event": "error", "data": {"message": "Acquisition run not found"}}
            return

        run.status = AcquisitionStatus.running
        await self.db.commit()

        # Load all acquisition sources
        result = await self.db.execute(
            select(AcquisitionSource).where(
                AcquisitionSource.acquisition_id == self.acquisition_id
            )
        )
        sources = list(result.scalars().all())

        completed = 0
        failed = 0

        for source in sources:
            if source.access_method == "manual":
                source.status = SourceAcqStatus.skipped
                await self.db.commit()
                continue

            yield {
                "event": "source_start",
                "data": {
                    "source_id": source.source_id,
                    "name": source.name,
                    "method": source.access_method,
                },
            }

            success = await self._acquire_source(source)

            if success:
                completed += 1
                yield {
                    "event": "source_complete",
                    "data": {
                        "source_id": source.source_id,
                        "staged_id": source.staged_document_id,
                        "duration_ms": source.duration_ms,
                        "byte_size": 0,
                    },
                }
            else:
                failed += 1
                yield {
                    "event": "source_failed",
                    "data": {
                        "source_id": source.source_id,
                        "error": source.error_message,
                        "retry_count": source.retry_count,
                    },
                }

            pending = len(sources) - completed - failed
            retrying = sum(1 for s in sources if s.status == SourceAcqStatus.retrying)
            yield {
                "event": "progress",
                "data": {
                    "completed": completed,
                    "failed": failed,
                    "pending": pending,
                    "retrying": retrying,
                },
            }

        # Finalize
        run.status = AcquisitionStatus.complete
        run.completed_at = datetime.now(UTC)
        await self.db.commit()

        yield {
            "event": "complete",
            "data": {
                "acquisition_id": self.acquisition_id,
                "completed": completed,
                "failed": failed,
                "total": len(sources),
            },
        }

    async def _acquire_source(self, source: AcquisitionSource) -> bool:
        """Attempt to acquire a single source with retries."""
        for attempt in range(MAX_RETRIES):
            source.status = SourceAcqStatus.running
            source.last_attempt_at = datetime.now(UTC)
            await self.db.commit()

            try:
                if source.access_method == "scrape":
                    result = await scrape_source(
                        manifest_id=source.manifest_id,
                        source_id=source.source_id,
                        url=source.url,
                        rate_limit_ms=self.rate_limit_ms,
                    )
                elif source.access_method == "download":
                    result = await download_source(
                        manifest_id=source.manifest_id,
                        source_id=source.source_id,
                        url=source.url,
                    )
                elif source.access_method == "api":
                    result = await fetch_api_source(
                        manifest_id=source.manifest_id,
                        source_id=source.source_id,
                        url=source.url,
                    )
                else:
                    source.status = SourceAcqStatus.skipped
                    await self.db.commit()
                    return False

                # Stage the document
                staged_id = f"stg-{source.source_id}"
                is_duplicate = result.get("is_duplicate", False)

                staged_doc = StagedDocument(
                    id=staged_id,
                    manifest_id=source.manifest_id,
                    source_id=source.source_id,
                    acquisition_method=source.access_method,
                    content_hash=result["content_hash"],
                    content_type=result.get("content_type", "application/octet-stream"),
                    raw_content_path=result["raw_content_path"],
                    byte_size=result["byte_size"],
                    status=StagedDocStatus.duplicate if is_duplicate else StagedDocStatus.staged,
                    provenance={
                        "source_url": source.url,
                        "duration_ms": result.get("duration_ms", 0),
                    },
                )
                self.db.add(staged_doc)

                source.status = SourceAcqStatus.complete
                source.staged_document_id = staged_id
                source.duration_ms = result.get("duration_ms", 0)
                source.error_message = None
                await self.db.commit()
                return True

            except Exception as e:
                source.retry_count = attempt + 1
                source.error_message = str(e)
                logger.warning(
                    "Acquisition failed for %s (attempt %d/%d): %s",
                    source.source_id, attempt + 1, MAX_RETRIES, e,
                )

                if attempt < MAX_RETRIES - 1:
                    source.status = SourceAcqStatus.retrying
                    await self.db.commit()
                    backoff = BACKOFF_BASE * (4 ** attempt)  # 1s, 4s, 16s
                    await asyncio.sleep(backoff)
                else:
                    source.status = SourceAcqStatus.failed
                    await self.db.commit()
                    return False

        return False
