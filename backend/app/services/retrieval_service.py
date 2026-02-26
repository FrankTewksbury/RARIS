"""Retrieval service — query persistence, corpus stats, citation lookup."""

from datetime import UTC, datetime

from sqlalchemy import func, select, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.ingestion import Chunk, CurationStatus, InternalDocument
from app.models.manifest import Source
from app.models.retrieval import AnalysisRecord, QueryRecord, QueryStatus
from app.retrieval.citations import build_citation_chain
from app.schemas.retrieval import (
    CitationSchema,
    CorpusSourceSummary,
    CorpusStats,
    QueryResponse,
)


async def save_query(
    db: AsyncSession,
    query_id: str,
    query_text: str,
    depth: int,
    filters: dict | None = None,
) -> QueryRecord:
    """Create a query record."""
    record = QueryRecord(
        id=query_id,
        query=query_text,
        depth=depth,
        filters=filters or {},
    )
    db.add(record)
    await db.flush()
    return record


async def complete_query(
    db: AsyncSession,
    query_id: str,
    response_text: str,
    citations: list,
    sources_count: int,
    token_count: int,
) -> None:
    """Mark a query as complete with its response."""
    result = await db.execute(
        select(QueryRecord).where(QueryRecord.id == query_id)
    )
    record = result.scalar_one_or_none()
    if record:
        record.status = QueryStatus.complete
        record.response_text = response_text
        record.citations = citations
        record.sources_count = sources_count
        record.token_count = token_count
        record.completed_at = datetime.now(UTC)
        await db.commit()


async def get_query(db: AsyncSession, query_id: str) -> QueryResponse | None:
    """Get a query result by ID."""
    result = await db.execute(
        select(QueryRecord).where(QueryRecord.id == query_id)
    )
    record = result.scalar_one_or_none()
    if not record:
        return None

    from app.retrieval.agent import DEPTH_CONFIG

    config = DEPTH_CONFIG.get(record.depth, DEPTH_CONFIG[2])

    return QueryResponse(
        query_id=record.id,
        query=record.query,
        depth=record.depth,
        depth_name=config["name"],
        response_text=record.response_text,
        citations=[CitationSchema(**c) for c in (record.citations or [])],
        sources_count=record.sources_count,
        token_count=record.token_count,
    )


async def save_analysis(
    db: AsyncSession,
    analysis_id: str,
    analysis_type: str,
    primary_text: str,
    filters: dict | None,
    depth: int,
) -> AnalysisRecord:
    """Create an analysis record."""
    record = AnalysisRecord(
        id=analysis_id,
        analysis_type=analysis_type,
        primary_text_preview=primary_text[:500],
        filters=filters or {},
        depth=depth,
    )
    db.add(record)
    await db.flush()
    return record


async def complete_analysis(
    db: AsyncSession,
    analysis_id: str,
    findings: list,
    summary: str,
    coverage_score: float | None,
    citations: list,
) -> None:
    """Mark an analysis as complete."""
    result = await db.execute(
        select(AnalysisRecord).where(AnalysisRecord.id == analysis_id)
    )
    record = result.scalar_one_or_none()
    if record:
        record.status = QueryStatus.complete
        record.findings = findings
        record.summary = summary
        record.coverage_score = coverage_score
        record.citations = citations
        record.completed_at = datetime.now(UTC)
        await db.commit()


async def get_analysis(
    db: AsyncSession, analysis_id: str
) -> AnalysisRecord | None:
    result = await db.execute(
        select(AnalysisRecord).where(AnalysisRecord.id == analysis_id)
    )
    return result.scalar_one_or_none()


async def get_citation_chain(
    db: AsyncSession, chunk_id: str
) -> CitationSchema | None:
    """Get a full citation chain for a chunk."""
    chain = await build_citation_chain(db, chunk_id)
    if not chain:
        return None
    return CitationSchema(
        chunk_id=chain.chunk_id,
        chunk_text=chain.chunk_text,
        section_path=chain.section_path,
        document_id=chain.document_id,
        document_title=chain.document_title,
        source_id=chain.source_id,
        source_url=chain.source_url,
        regulatory_body=chain.regulatory_body,
        jurisdiction=chain.jurisdiction,
        authority_level=chain.authority_level,
        manifest_id=chain.manifest_id,
        confidence=chain.confidence,
    )


async def get_corpus_stats(db: AsyncSession) -> CorpusStats:
    """Get corpus-wide statistics."""
    total_docs = (
        await db.execute(
            select(func.count()).select_from(InternalDocument)
        )
    ).scalar() or 0

    indexed_docs = (
        await db.execute(
            select(func.count()).select_from(InternalDocument).where(
                InternalDocument.status == CurationStatus.indexed
            )
        )
    ).scalar() or 0

    total_chunks = (
        await db.execute(select(func.count()).select_from(Chunk))
    ).scalar() or 0

    indexed_chunks = (
        await db.execute(
            select(func.count()).select_from(Chunk).where(
                Chunk.embedding.isnot(None)
            )
        )
    ).scalar() or 0

    # By jurisdiction
    j_rows = (
        await db.execute(
            text(
                "SELECT jurisdiction, COUNT(*) FROM internal_documents "
                "WHERE status = :s GROUP BY jurisdiction"
            ),
            {"s": CurationStatus.indexed},
        )
    ).all()

    # By document type
    t_rows = (
        await db.execute(
            text(
                "SELECT document_type, COUNT(*) FROM internal_documents "
                "WHERE status = :s GROUP BY document_type"
            ),
            {"s": CurationStatus.indexed},
        )
    ).all()

    # By regulatory body
    b_rows = (
        await db.execute(
            text(
                "SELECT regulatory_body, COUNT(*) FROM internal_documents "
                "WHERE status = :s GROUP BY regulatory_body"
            ),
            {"s": CurationStatus.indexed},
        )
    ).all()

    return CorpusStats(
        total_documents=total_docs,
        indexed_documents=indexed_docs,
        total_chunks=total_chunks,
        indexed_chunks=indexed_chunks,
        by_jurisdiction={r[0]: r[1] for r in j_rows},
        by_document_type={r[0]: r[1] for r in t_rows},
        by_regulatory_body={r[0]: r[1] for r in b_rows},
    )


async def list_corpus_sources(db: AsyncSession) -> list[CorpusSourceSummary]:
    """List all indexed sources with document and chunk counts."""
    rows = (
        await db.execute(
            text("""
                SELECT d.source_id, d.manifest_id, d.regulatory_body,
                       d.jurisdiction, d.authority_level, d.document_type,
                       COUNT(DISTINCT d.id) as doc_count,
                       COUNT(c.id) as chunk_count
                FROM internal_documents d
                LEFT JOIN chunks c ON c.document_id = d.id
                WHERE d.status = :s
                GROUP BY d.source_id, d.manifest_id, d.regulatory_body,
                         d.jurisdiction, d.authority_level, d.document_type
                ORDER BY doc_count DESC
            """),
            {"s": CurationStatus.indexed},
        )
    ).all()

    results = []
    for r in rows:
        # Try to get source name from manifest
        src = (
            await db.execute(
                select(Source.name).where(
                    Source.id == r[0], Source.manifest_id == r[1]
                )
            )
        ).scalar_one_or_none()

        results.append(CorpusSourceSummary(
            source_id=r[0],
            manifest_id=r[1],
            name=src or r[0],
            regulatory_body=r[2],
            jurisdiction=r[3],
            authority_level=r[4],
            document_type=r[5],
            document_count=r[6],
            chunk_count=r[7],
        ))
    return results
