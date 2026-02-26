"""API Acquisition Adapter — fetch regulatory data from REST APIs."""

import logging
import time

import httpx

from app.acquisition.staging import stage_document

logger = logging.getLogger(__name__)


async def fetch_api_source(
    manifest_id: str,
    source_id: str,
    url: str,
    auth_type: str = "none",
    auth_value: str = "",
    pagination: str = "none",
    max_pages: int = 10,
) -> dict:
    """Fetch data from a REST API and stage the content.

    Args:
        auth_type: "none", "bearer", "header", "query_param"
        auth_value: Token value or "HeaderName:value" for header auth
        pagination: "none", "offset", "cursor", "link"
        max_pages: Maximum pages to fetch when paginating
    """
    start = time.monotonic()

    headers = {"User-Agent": "RARIS/0.1 Regulatory Research Bot"}
    params: dict[str, str] = {}

    # Configure authentication
    if auth_type == "bearer" and auth_value:
        headers["Authorization"] = f"Bearer {auth_value}"
    elif auth_type == "header" and ":" in auth_value:
        header_name, header_val = auth_value.split(":", 1)
        headers[header_name.strip()] = header_val.strip()
    elif auth_type == "query_param" and "=" in auth_value:
        param_name, param_val = auth_value.split("=", 1)
        params[param_name.strip()] = param_val.strip()

    # Fetch pages
    all_content = []
    next_url: str | None = url

    async with httpx.AsyncClient(follow_redirects=True) as client:
        for page in range(max_pages):
            if not next_url:
                break

            response = await client.get(
                next_url, headers=headers, params=params if page == 0 else {},
                timeout=60.0,
            )
            response.raise_for_status()

            all_content.append(response.text)

            # Handle pagination
            if pagination == "link":
                next_url = _parse_link_header(response.headers.get("link", ""))
            elif pagination == "offset":
                data = response.json()
                if isinstance(data, dict) and data.get("next"):
                    next_url = data["next"]
                else:
                    break
            elif pagination == "cursor":
                data = response.json()
                cursor = data.get("next_cursor") or data.get("cursor")
                if cursor:
                    next_url = f"{url}{'&' if '?' in url else '?'}cursor={cursor}"
                else:
                    break
            else:
                break

    combined_content = "\n".join(all_content)
    content_bytes = combined_content.encode("utf-8")
    duration_ms = int((time.monotonic() - start) * 1000)

    result = stage_document(
        manifest_id=manifest_id,
        source_id=source_id,
        content=content_bytes,
        content_type="application/json",
        provenance={
            "source_url": url,
            "scraping_tool": "api-adapter",
            "tool_version": "v1",
            "acquisition_duration_ms": duration_ms,
            "pages_fetched": len(all_content),
            "auth_type": auth_type,
            "pagination": pagination,
        },
    )
    result["duration_ms"] = duration_ms
    result["content_type"] = "application/json"
    return result


def _parse_link_header(link_header: str) -> str | None:
    """Parse RFC 5988 Link header for rel=next URL."""
    for part in link_header.split(","):
        if 'rel="next"' in part:
            url_part = part.split(";")[0].strip()
            if url_part.startswith("<") and url_part.endswith(">"):
                return url_part[1:-1]
    return None
