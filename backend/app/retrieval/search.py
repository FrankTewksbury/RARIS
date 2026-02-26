"""Hybrid retrieval engine — dense + sparse + metadata search with RRF fusion."""

import logging
from dataclasses import dataclass, field

from openai import AsyncOpenAI
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings

logger = logging.getLogger(__name__)


@dataclass
class SearchFilters:
    jurisdiction: list[str] | None = None
    document_type: list[str] | None = None
    regulatory_body: list[str] | None = None
    authority_level: list[str] | None = None
    tags: list[str] | None = None


@dataclass
class SearchResult:
    chunk_id: str
    document_id: str
    source_id: str
    manifest_id: str
    section_path: str
    text: str
    score: float
    chunk_metadata: dict = field(default_factory=dict)


async def hybrid_search(
    db: AsyncSession,
    query: str,
    filters: SearchFilters | None = None,
    top_k: int | None = None,
    mode: str = "hybrid",
) -> list[SearchResult]:
    """Execute hybrid search combining dense, sparse, and metadata filters.

    Args:
        db: Database session.
        query: Natural language query.
        filters: Optional metadata filters.
        top_k: Number of results to return.
        mode: "hybrid" | "semantic" | "lexical"
    """
    k = top_k or settings.search_top_k

    dense_results: list[SearchResult] = []
    sparse_results: list[SearchResult] = []

    if mode in ("hybrid", "semantic"):
        dense_results = await _dense_search(db, query, filters, k)

    if mode in ("hybrid", "lexical"):
        sparse_results = await _sparse_search(db, query, filters, k)

    if mode == "semantic":
        return dense_results[:k]
    if mode == "lexical":
        return sparse_results[:k]

    # Reciprocal Rank Fusion
    fused = _rrf_merge(dense_results, sparse_results, k=settings.rrf_k)
    return fused[:k]


async def _dense_search(
    db: AsyncSession,
    query: str,
    filters: SearchFilters | None,
    top_k: int,
) -> list[SearchResult]:
    """Semantic search using pgvector cosine similarity."""
    embedding = await _embed_query(query)
    if not embedding:
        return []

    filter_clause, params = _build_filter_clause(filters)
    params["embedding"] = str(embedding)
    params["limit"] = top_k

    sql = text(f"""
        SELECT id, document_id, section_path, text, chunk_metadata,
               1 - (embedding <=> :embedding::vector) AS score
        FROM chunks
        WHERE embedding IS NOT NULL
        {filter_clause}
        ORDER BY embedding <=> :embedding::vector
        LIMIT :limit
    """)

    result = await db.execute(sql, params)
    rows = result.all()

    return [
        SearchResult(
            chunk_id=r[0],
            document_id=r[1],
            source_id=(r[4] or {}).get("source_id", ""),
            manifest_id=(r[4] or {}).get("manifest_id", ""),
            section_path=r[2],
            text=r[3],
            score=float(r[5]),
            chunk_metadata=r[4] or {},
        )
        for r in rows
    ]


async def _sparse_search(
    db: AsyncSession,
    query: str,
    filters: SearchFilters | None,
    top_k: int,
) -> list[SearchResult]:
    """Lexical search using PostgreSQL tsvector + ts_rank."""
    filter_clause, params = _build_filter_clause(filters)
    params["query"] = query
    params["limit"] = top_k

    sql = text(f"""
        SELECT id, document_id, section_path, text, chunk_metadata,
               ts_rank(search_vector, plainto_tsquery('english', :query)) AS score
        FROM chunks
        WHERE search_vector @@ plainto_tsquery('english', :query)
        {filter_clause}
        ORDER BY score DESC
        LIMIT :limit
    """)

    result = await db.execute(sql, params)
    rows = result.all()

    return [
        SearchResult(
            chunk_id=r[0],
            document_id=r[1],
            source_id=(r[4] or {}).get("source_id", ""),
            manifest_id=(r[4] or {}).get("manifest_id", ""),
            section_path=r[2],
            text=r[3],
            score=float(r[5]),
            chunk_metadata=r[4] or {},
        )
        for r in rows
    ]


def _rrf_merge(
    dense: list[SearchResult],
    sparse: list[SearchResult],
    k: int = 60,
) -> list[SearchResult]:
    """Reciprocal Rank Fusion to combine dense and sparse results."""
    scores: dict[str, float] = {}
    result_map: dict[str, SearchResult] = {}

    for rank, r in enumerate(dense, start=1):
        scores[r.chunk_id] = scores.get(r.chunk_id, 0) + 1 / (k + rank)
        result_map[r.chunk_id] = r

    for rank, r in enumerate(sparse, start=1):
        scores[r.chunk_id] = scores.get(r.chunk_id, 0) + 1 / (k + rank)
        if r.chunk_id not in result_map:
            result_map[r.chunk_id] = r

    # Sort by fused score descending
    sorted_ids = sorted(scores.keys(), key=lambda cid: scores[cid], reverse=True)

    results = []
    for cid in sorted_ids:
        r = result_map[cid]
        results.append(SearchResult(
            chunk_id=r.chunk_id,
            document_id=r.document_id,
            source_id=r.source_id,
            manifest_id=r.manifest_id,
            section_path=r.section_path,
            text=r.text,
            score=scores[cid],
            chunk_metadata=r.chunk_metadata,
        ))

    return results


def _build_filter_clause(
    filters: SearchFilters | None,
) -> tuple[str, dict]:
    """Build SQL WHERE clauses from search filters."""
    clauses: list[str] = []
    params: dict = {}

    if not filters:
        return "", params

    if filters.jurisdiction:
        clauses.append(
            "AND chunk_metadata->>'jurisdiction' = ANY(:jurisdictions)"
        )
        params["jurisdictions"] = filters.jurisdiction

    if filters.document_type:
        clauses.append(
            "AND chunk_metadata->>'document_type' = ANY(:doc_types)"
        )
        params["doc_types"] = filters.document_type

    if filters.regulatory_body:
        clauses.append(
            "AND chunk_metadata->>'regulatory_body' = ANY(:reg_bodies)"
        )
        params["reg_bodies"] = filters.regulatory_body

    if filters.authority_level:
        clauses.append(
            "AND chunk_metadata->>'authority_level' = ANY(:auth_levels)"
        )
        params["auth_levels"] = filters.authority_level

    return "\n".join(clauses), params


async def _embed_query(query: str) -> list[float] | None:
    """Generate embedding for a search query, with Redis caching."""
    from app.embedding_cache import get_cached_embedding, set_cached_embedding

    # Check cache first
    cached = await get_cached_embedding(query)
    if cached:
        return cached

    try:
        client = AsyncOpenAI(api_key=settings.openai_api_key)
        response = await client.embeddings.create(
            model=settings.embedding_model,
            input=query,
            dimensions=settings.embedding_dimensions,
        )
        embedding = response.data[0].embedding
        await set_cached_embedding(query, embedding)
        return embedding
    except Exception:
        logger.exception("Failed to embed query")
        return None
