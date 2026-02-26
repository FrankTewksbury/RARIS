"""Web Scraping Engine — Firecrawl for JS-rendered, httpx+BeautifulSoup for static."""

import asyncio
import logging
import time
from urllib.parse import urlparse

import httpx

from app.acquisition.staging import stage_document

logger = logging.getLogger(__name__)

# Per-domain last-request timestamps for rate limiting
_domain_last_request: dict[str, float] = {}


async def _enforce_rate_limit(url: str, rate_limit_ms: int) -> None:
    """Wait if needed to enforce minimum delay between requests to the same domain."""
    if rate_limit_ms <= 0:
        return

    domain = urlparse(url).netloc
    now = time.monotonic()
    last = _domain_last_request.get(domain, 0.0)
    delay_s = rate_limit_ms / 1000.0
    elapsed = now - last

    if elapsed < delay_s:
        wait = delay_s - elapsed
        logger.debug("Rate limit: waiting %.1fs before requesting %s", wait, domain)
        await asyncio.sleep(wait)

    _domain_last_request[domain] = time.monotonic()


async def scrape_source(
    manifest_id: str,
    source_id: str,
    url: str,
    tool: str = "static",
    scraping_notes: str | None = None,
    rate_limit_ms: int = 2000,
) -> dict:
    """Scrape a web page and stage the content.

    Args:
        tool: "firecrawl" for JS-rendered pages, "static" for simple HTTP fetch.
        rate_limit_ms: Minimum delay between requests to the same domain.
    """
    await _enforce_rate_limit(url, rate_limit_ms)

    if tool == "firecrawl":
        return await _scrape_firecrawl(manifest_id, source_id, url)
    return await _scrape_static(manifest_id, source_id, url)


async def _scrape_static(manifest_id: str, source_id: str, url: str) -> dict:
    """Fetch static HTML content using httpx."""
    start = time.monotonic()

    async with httpx.AsyncClient(follow_redirects=True, max_redirects=5) as client:
        response = await client.get(
            url,
            timeout=60.0,
            headers={"User-Agent": "RARIS/0.1 Regulatory Research Bot"},
        )
        response.raise_for_status()

    content = response.content
    content_type = response.headers.get("content-type", "text/html").split(";")[0]
    duration_ms = int((time.monotonic() - start) * 1000)

    result = stage_document(
        manifest_id=manifest_id,
        source_id=source_id,
        content=content,
        content_type=content_type,
        provenance={
            "source_url": url,
            "scraping_tool": "httpx-static",
            "tool_version": httpx.__version__,
            "acquisition_duration_ms": duration_ms,
            "http_status": response.status_code,
        },
    )
    result["duration_ms"] = duration_ms
    result["content_type"] = content_type
    return result


async def _scrape_firecrawl(manifest_id: str, source_id: str, url: str) -> dict:
    """Scrape JS-rendered page using Firecrawl API.

    Requires FIRECRAWL_API_KEY in environment. Falls back to static if unavailable.
    """
    import os

    api_key = os.environ.get("FIRECRAWL_API_KEY")
    if not api_key:
        logger.warning("FIRECRAWL_API_KEY not set, falling back to static scrape for %s", url)
        return await _scrape_static(manifest_id, source_id, url)

    start = time.monotonic()

    async with httpx.AsyncClient() as client:
        response = await client.post(
            "https://api.firecrawl.dev/v1/scrape",
            json={"url": url, "formats": ["html"]},
            headers={"Authorization": f"Bearer {api_key}"},
            timeout=120.0,
        )
        response.raise_for_status()

    data = response.json()
    html_content = data.get("data", {}).get("html", "")
    content = html_content.encode("utf-8")
    duration_ms = int((time.monotonic() - start) * 1000)

    result = stage_document(
        manifest_id=manifest_id,
        source_id=source_id,
        content=content,
        content_type="text/html",
        provenance={
            "source_url": url,
            "scraping_tool": "firecrawl",
            "tool_version": "v1",
            "acquisition_duration_ms": duration_ms,
            "http_status": response.status_code,
        },
    )
    result["duration_ms"] = duration_ms
    result["content_type"] = "text/html"
    return result
