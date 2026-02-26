"""Citation chain builder — traces chunk provenance back through the full chain."""

from dataclasses import dataclass

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.ingestion import Chunk, InternalDocument
from app.models.manifest import Source
from app.retrieval.search import SearchResult


@dataclass
class CitationChain:
    chunk_id: str
    chunk_text: str
    section_path: str
    document_id: str
    document_title: str
    source_id: str
    source_url: str
    regulatory_body: str
    jurisdiction: str
    authority_level: str
    manifest_id: str
    confidence: float


async def build_citation_chain(
    db: AsyncSession, chunk_id: str
) -> CitationChain | None:
    """Build a full citation chain from a chunk ID back to the manifest source."""
    # Load chunk
    chunk_result = await db.execute(
        select(Chunk).where(Chunk.id == chunk_id)
    )
    chunk = chunk_result.scalar_one_or_none()
    if not chunk:
        return None

    # Load document
    doc_result = await db.execute(
        select(InternalDocument).where(InternalDocument.id == chunk.document_id)
    )
    doc = doc_result.scalar_one_or_none()
    if not doc:
        return None

    # Load manifest source
    source_result = await db.execute(
        select(Source).where(
            Source.id == doc.source_id,
            Source.manifest_id == doc.manifest_id,
        )
    )
    source = source_result.scalar_one_or_none()

    return CitationChain(
        chunk_id=chunk.id,
        chunk_text=chunk.text[:500],
        section_path=chunk.section_path,
        document_id=doc.id,
        document_title=doc.title,
        source_id=doc.source_id,
        source_url=source.url if source else "",
        regulatory_body=doc.regulatory_body,
        jurisdiction=doc.jurisdiction,
        authority_level=doc.authority_level,
        manifest_id=doc.manifest_id,
        confidence=source.confidence if source else 0.0,
    )


async def build_citations_for_results(
    db: AsyncSession, results: list[SearchResult]
) -> dict[str, CitationChain]:
    """Build citation chains for a batch of search results.

    Returns a dict mapping chunk_id to CitationChain.
    """
    citations: dict[str, CitationChain] = {}
    for r in results:
        chain = await build_citation_chain(db, r.chunk_id)
        if chain:
            citations[r.chunk_id] = chain
    return citations
