"""Regulatory change monitor — detects content changes on indexed sources."""

import hashlib
import logging
from datetime import UTC, datetime

import httpx
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.feedback import ChangeEvent, CurationQueueItem, CurationQueuePriority
from app.models.ingestion import InternalDocument
from app.models.manifest import Source

logger = logging.getLogger(__name__)


async def run_change_monitor(db: AsyncSession) -> dict:
    """Run a change monitoring sweep across all indexed sources.

    Checks HTTP headers and content hashes for changes.
    Returns summary stats.
    """
    # Get all sources that have indexed documents
    result = await db.execute(
        select(Source, InternalDocument.content_hash)
        .join(
            InternalDocument,
            (InternalDocument.source_id == Source.id)
            & (InternalDocument.manifest_id == Source.manifest_id),
        )
        .where(InternalDocument.content_hash != "")
    )
    rows = result.all()

    sources_checked = 0
    changes_detected = 0

    async with httpx.AsyncClient(timeout=30.0, follow_redirects=True) as client:
        for source, prev_hash in rows:
            sources_checked += 1
            try:
                change = await _check_source(client, db, source, prev_hash)
                if change:
                    changes_detected += 1
            except Exception:
                logger.debug(
                    "Monitor check failed for source %s", source.id, exc_info=True
                )

    await db.commit()
    return {
        "sources_checked": sources_checked,
        "changes_detected": changes_detected,
    }


async def _check_source(
    client: httpx.AsyncClient,
    db: AsyncSession,
    source: Source,
    previous_hash: str,
) -> ChangeEvent | None:
    """Check a single source for changes via HTTP HEAD + content hash."""
    try:
        # First try HEAD for quick metadata check
        head_resp = await client.head(source.url)
        if head_resp.status_code >= 400:
            return None

        # Check Last-Modified and Content-Length headers
        last_modified = head_resp.headers.get("last-modified")
        content_length = head_resp.headers.get("content-length")

        # If we can't determine from headers, do a full GET and hash
        get_resp = await client.get(source.url)
        if get_resp.status_code >= 400:
            return None

        current_hash = hashlib.sha256(get_resp.content).hexdigest()

        if current_hash == previous_hash:
            return None  # No change

        # Change detected
        event_id = f"chg-{datetime.now(UTC).strftime('%Y%m%d%H%M%S%f')}"
        event = ChangeEvent(
            id=event_id,
            source_id=source.id,
            manifest_id=source.manifest_id,
            detection_method="hash_check",
            change_type="content_update",
            previous_hash=previous_hash,
            current_hash=current_hash,
            description=(
                f"Content hash changed for {source.name}. "
                f"Last-Modified: {last_modified or 'unknown'}, "
                f"Content-Length: {content_length or 'unknown'}"
            ),
        )
        db.add(event)

        # Queue for re-curation
        queue_id = f"rcq-chg-{datetime.now(UTC).strftime('%Y%m%d%H%M%S%f')}"
        queue_item = CurationQueueItem(
            id=queue_id,
            source_id=source.id,
            manifest_id=source.manifest_id,
            priority=CurationQueuePriority.high,
            reason=f"Content change detected: {event.description[:200]}",
            trigger_type="change_detected",
            change_event_id=event_id,
        )
        db.add(queue_item)

        await db.flush()
        return event

    except httpx.HTTPError:
        logger.debug("HTTP error checking source %s", source.id)
        return None
