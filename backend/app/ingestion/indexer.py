"""Indexer — generates embeddings and writes to pgvector + tsvector hybrid index."""

import logging

from openai import AsyncOpenAI
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.models.ingestion import CurationStatus, InternalDocument

logger = logging.getLogger(__name__)

_BATCH_SIZE = 64  # OpenAI embedding batch limit


async def index_document(doc: InternalDocument, db: AsyncSession) -> int:
    """Generate embeddings for all chunks of a document and update the index.

    Returns the number of chunks indexed.
    """
    chunks = doc.chunks
    if not chunks:
        return 0

    # Generate embeddings in batches
    texts = [c.text for c in chunks]
    embeddings = await _generate_embeddings(texts)

    for chunk, embedding in zip(chunks, embeddings):
        chunk.embedding = embedding
        # Denormalize document metadata into chunk for filtered retrieval
        chunk.chunk_metadata = {
            "jurisdiction": doc.jurisdiction,
            "regulatory_body": doc.regulatory_body,
            "authority_level": doc.authority_level,
            "document_type": doc.document_type,
            "classification_tags": doc.classification_tags or [],
            "document_id": doc.id,
            "manifest_id": doc.manifest_id,
            "source_id": doc.source_id,
        }

    await db.flush()

    # Update tsvector for lexical search
    for chunk in chunks:
        await db.execute(
            text(
                "UPDATE chunks SET search_vector = to_tsvector('english', :text) "
                "WHERE id = :chunk_id"
            ),
            {"text": chunk.text, "chunk_id": chunk.id},
        )

    # Mark document as indexed
    doc.status = CurationStatus.indexed

    await db.flush()
    return len(chunks)


async def _generate_embeddings(texts: list[str]) -> list[list[float]]:
    """Generate embeddings using OpenAI API in batches."""
    if not texts:
        return []

    client = AsyncOpenAI(api_key=settings.openai_api_key)
    all_embeddings: list[list[float]] = []

    for i in range(0, len(texts), _BATCH_SIZE):
        batch = texts[i : i + _BATCH_SIZE]
        # Truncate texts that are too long (8191 token limit for embedding models)
        batch = [t[:30000] for t in batch]

        try:
            response = await client.embeddings.create(
                model=settings.embedding_model,
                input=batch,
                dimensions=settings.embedding_dimensions,
            )
            for item in response.data:
                all_embeddings.append(item.embedding)
        except Exception:
            logger.exception("Embedding generation failed for batch %d", i)
            # Fill with None-equivalent (zeros) so we don't lose chunks
            for _ in batch:
                all_embeddings.append([0.0] * settings.embedding_dimensions)

    return all_embeddings


async def ensure_pgvector_extension(db: AsyncSession) -> None:
    """Create the pgvector extension if it doesn't exist."""
    await db.execute(text("CREATE EXTENSION IF NOT EXISTS vector"))
    await db.commit()


async def get_index_stats(db: AsyncSession) -> dict:
    """Get index health statistics."""
    total_chunks = (await db.execute(text("SELECT COUNT(*) FROM chunks"))).scalar() or 0
    indexed_chunks = (
        await db.execute(text("SELECT COUNT(*) FROM chunks WHERE embedding IS NOT NULL"))
    ).scalar() or 0
    total_docs = (
        await db.execute(text("SELECT COUNT(*) FROM internal_documents"))
    ).scalar() or 0
    indexed_docs = (
        await db.execute(
            text(
                "SELECT COUNT(*) FROM internal_documents WHERE status = :status"
            ),
            {"status": CurationStatus.indexed},
        )
    ).scalar() or 0

    # Coverage by jurisdiction
    jurisdiction_rows = (
        await db.execute(
            text(
                "SELECT jurisdiction, COUNT(*) as cnt "
                "FROM internal_documents WHERE status = :status "
                "GROUP BY jurisdiction"
            ),
            {"status": CurationStatus.indexed},
        )
    ).all()
    by_jurisdiction = {row[0]: row[1] for row in jurisdiction_rows}

    # Coverage by document type
    type_rows = (
        await db.execute(
            text(
                "SELECT document_type, COUNT(*) as cnt "
                "FROM internal_documents WHERE status = :status "
                "GROUP BY document_type"
            ),
            {"status": CurationStatus.indexed},
        )
    ).all()
    by_type = {row[0]: row[1] for row in type_rows}

    return {
        "total_chunks": total_chunks,
        "indexed_chunks": indexed_chunks,
        "total_documents": total_docs,
        "indexed_documents": indexed_docs,
        "by_jurisdiction": by_jurisdiction,
        "by_document_type": by_type,
    }
