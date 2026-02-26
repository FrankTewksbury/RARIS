"""Re-ranking module — batch LLM-based relevance scoring for search results."""

import json
import logging

from app.config import settings
from app.llm.registry import get_provider
from app.retrieval.search import SearchResult

logger = logging.getLogger(__name__)

_BATCH_RERANK_PROMPT = """Score the relevance of each text chunk to the query.
Return ONLY a JSON array of objects: [{{"id": "<chunk_id>", "score": <0-10>}}, ...]

Query: {query}

Chunks:
{chunks}"""


async def rerank(
    query: str, results: list[SearchResult], top_k: int = 10
) -> list[SearchResult]:
    """Re-rank search results using batch LLM relevance scoring.

    Sends all chunks in a single prompt instead of N separate calls.
    Only applied when settings.rerank_method == "llm".
    """
    if settings.rerank_method == "none" or not results:
        return results[:top_k]

    llm = get_provider()

    # Format all chunks into a single prompt
    chunk_lines = []
    for i, r in enumerate(results):
        chunk_lines.append(
            f"[{i}] id={r.chunk_id} section={r.section_path}\n{r.text[:800]}\n"
        )
    chunks_text = "\n---\n".join(chunk_lines)

    try:
        prompt = _BATCH_RERANK_PROMPT.format(query=query, chunks=chunks_text)
        response = await llm.complete([{"role": "user", "content": prompt}])
        scores = _parse_batch_scores(response, results)
    except Exception:
        logger.warning("Batch rerank failed, returning original order")
        return results[:top_k]

    # Build scored list
    scored = []
    for r in results:
        s = scores.get(r.chunk_id, r.score * 10)
        scored.append((r, s))

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


def _parse_batch_scores(response: str, results: list[SearchResult]) -> dict[str, float]:
    """Parse batch scores from LLM response.

    Returns a dict mapping chunk_id -> score.
    """
    scores: dict[str, float] = {}

    # Clean response
    cleaned = response.strip()
    if cleaned.startswith("```"):
        cleaned = cleaned.split("\n", 1)[-1].rsplit("```", 1)[0].strip()

    try:
        data = json.loads(cleaned)
        if isinstance(data, list):
            for item in data:
                chunk_id = item.get("id", "")
                score = float(item.get("score", 5))
                scores[chunk_id] = min(score, 10.0)
    except (json.JSONDecodeError, ValueError, TypeError):
        # Fallback: try to extract index-based scores
        logger.debug("Could not parse batch scores as JSON, using fallback")
        import re

        for m in re.finditer(r'\[(\d+)\].*?(\d+(?:\.\d+)?)', cleaned):
            idx = int(m.group(1))
            score = min(float(m.group(2)), 10.0)
            if idx < len(results):
                scores[results[idx].chunk_id] = score

    return scores


def _parse_score(response: str) -> float:
    """Parse a single LLM score from a response (kept for backward compatibility)."""
    try:
        cleaned = response.strip()
        if cleaned.startswith("```"):
            cleaned = cleaned.split("\n", 1)[-1].rsplit("```", 1)[0]
        data = json.loads(cleaned)
        if isinstance(data, dict):
            return min(float(data.get("score", 5)), 10.0)
        if isinstance(data, (int, float)):
            return min(float(data), 10.0)
        return 5.0
    except (json.JSONDecodeError, ValueError, KeyError):
        import re

        m = re.search(r"\b(\d+(?:\.\d+)?)\b", response)
        if m:
            return min(float(m.group(1)), 10.0)
        return 5.0
