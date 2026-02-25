"""Direct Download Adapter — HTTP fetch for PDFs and structured files."""

import logging
import time

import httpx

from app.acquisition.staging import stage_document

logger = logging.getLogger(__name__)

MAX_REDIRECTS = 5


async def download_source(
    manifest_id: str,
    source_id: str,
    url: str,
    expected_format: str | None = None,
) -> dict:
    """Download a file from a URL and stage it.

    Returns a dict with staged document info or raises on failure.
    """
    start = time.monotonic()

    async with httpx.AsyncClient(follow_redirects=True, max_redirects=MAX_REDIRECTS) as client:
        response = await client.get(url, timeout=60.0)
        response.raise_for_status()

    content_type = response.headers.get("content-type", "application/octet-stream").split(";")[0]
    content = response.content
    duration_ms = int((time.monotonic() - start) * 1000)

    result = stage_document(
        manifest_id=manifest_id,
        source_id=source_id,
        content=content,
        content_type=content_type,
        provenance={
            "source_url": url,
            "scraping_tool": "httpx",
            "tool_version": httpx.__version__,
            "acquisition_duration_ms": duration_ms,
            "http_status": response.status_code,
        },
    )
    result["duration_ms"] = duration_ms
    result["content_type"] = content_type
    return result
