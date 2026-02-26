"""Re-ranking module — LLM-based relevance scoring for search results."""

import json
import logging

from app.config import settings
from app.llm.registry import get_provider
from app.retrieval.search import SearchResult

logger = logging.getLogger(__name__)

_RERANK_PROMPT = """Score the relevance of the following text chunk to the query.
Return ONLY a JSON object: {{"score": <0-10>, "reason": "<brief reason>"}}

Query: {query}

Chunk (from {section_path}):
{chunk_text}"""


async def rerank(
    query: str, results: list[SearchResult], top_k: int = 10
) -> list[SearchResult]:
    """Re-rank search results using LLM relevance scoring.

    Only applied when settings.rerank_method == "llm".
    """
    if settings.rerank_method == "none" or not results:
        return results[:top_k]

    llm = get_provider()
    scored: list[tuple[SearchResult, float]] = []

    for r in results:
        try:
            prompt = _RERANK_PROMPT.format(
                query=query,
                section_path=r.section_path,
                chunk_text=r.text[:1500],
            )
            response = await llm.complete([{"role": "user", "content": prompt}])
            score = _parse_score(response)
            scored.append((r, score))
        except Exception:
            logger.debug("Rerank failed for chunk %s, keeping original score", r.chunk_id)
            scored.append((r, r.score * 10))

    scored.sort(key=lambda x: x[1], reverse=True)

    return [
        SearchResult(
            chunk_id=r.chunk_id,
            document_id=r.document_id,
            source_id=r.source_id,
            manifest_id=r.manifest_id,
            section_path=r.section_path,
            text=r.text,
            score=s / 10.0,
            chunk_metadata=r.chunk_metadata,
        )
        for r, s in scored[:top_k]
    ]


def _parse_score(response: str) -> float:
    """Parse the LLM score from the response."""
    try:
        # Try JSON parse
        cleaned = response.strip()
        if cleaned.startswith("```"):
            cleaned = cleaned.split("\n", 1)[-1].rsplit("```", 1)[0]
        data = json.loads(cleaned)
        return float(data.get("score", 5))
    except (json.JSONDecodeError, ValueError, KeyError):
        # Fallback: look for a number
        import re

        m = re.search(r"\b(\d+(?:\.\d+)?)\b", response)
        if m:
            return min(float(m.group(1)), 10.0)
        return 5.0
