"""Retrieval and agent API endpoints — Phase 4."""

import asyncio
import json
import logging
from datetime import UTC, datetime

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sse_starlette.sse import EventSourceResponse

from app.database import async_session, get_db
from app.retrieval.agent import DEPTH_CONFIG, RetrievalAgent
from app.retrieval.analysis import run_analysis
from app.retrieval.search import SearchFilters
from app.schemas.retrieval import (
    AnalysisRequest,
    AnalysisResponse,
    CitationSchema,
    CorpusSourceSummary,
    CorpusStats,
    FindingSchema,
    QueryRequest,
    QueryResponse,
)
from app.services import retrieval_service

logger = logging.getLogger(__name__)
router = APIRouter(tags=["retrieval"])

# SSE queues for streaming queries
_query_queues: dict[str, asyncio.Queue] = {}


# --- Query endpoints ---


@router.post("/api/query", response_model=QueryResponse)
async def submit_query(
    request: QueryRequest,
    db: AsyncSession = Depends(get_db),
):
    """Submit a synchronous query with depth and filters."""
    query_id = f"q-{datetime.now(UTC).strftime('%Y%m%d%H%M%S%f')}"

    filters = None
    if request.filters:
        filters = SearchFilters(
            jurisdiction=request.filters.jurisdiction,
            document_type=request.filters.document_type,
            regulatory_body=request.filters.regulatory_body,
            authority_level=request.filters.authority_level,
            tags=request.filters.tags,
        )

    # Save query record
    await retrieval_service.save_query(
        db, query_id, request.query, request.depth,
        request.filters.model_dump() if request.filters else None,
    )

    # Execute
    agent = RetrievalAgent(db)
    result = await agent.query(
        request.query,
        depth=request.depth,
        filters=filters,
        query_id=query_id,
    )

    config = DEPTH_CONFIG[result.depth]

    # Persist result
    citations_data = [
        {
            "chunk_id": c.chunk_id,
            "chunk_text": c.chunk_text,
            "section_path": c.section_path,
            "document_id": c.document_id,
            "document_title": c.document_title,
            "source_id": c.source_id,
            "source_url": c.source_url,
            "regulatory_body": c.regulatory_body,
            "jurisdiction": c.jurisdiction,
            "authority_level": c.authority_level,
            "manifest_id": c.manifest_id,
            "confidence": c.confidence,
        }
        for c in result.citations
    ]

    await retrieval_service.complete_query(
        db, query_id, result.response_text,
        citations_data, len(result.sources_used), result.token_count,
    )

    return QueryResponse(
        query_id=query_id,
        query=result.query,
        depth=result.depth,
        depth_name=config["name"],
        response_text=result.response_text,
        citations=[CitationSchema(**c) for c in citations_data],
        sources_count=len(result.sources_used),
        token_count=result.token_count,
    )


@router.get("/api/query/{query_id}", response_model=QueryResponse)
async def get_query_result(
    query_id: str, db: AsyncSession = Depends(get_db)
):
    """Get a query result by ID."""
    result = await retrieval_service.get_query(db, query_id)
    if not result:
        raise HTTPException(status_code=404, detail="Query not found")
    return result


@router.post("/api/query/stream")
async def stream_query(
    request: QueryRequest,
    background_tasks: BackgroundTasks,
    db: AsyncSession = Depends(get_db),
):
    """SSE stream for real-time response generation."""
    query_id = f"q-{datetime.now(UTC).strftime('%Y%m%d%H%M%S%f')}"

    _query_queues[query_id] = asyncio.Queue()

    # Save query record
    await retrieval_service.save_query(
        db, query_id, request.query, request.depth,
        request.filters.model_dump() if request.filters else None,
    )

    filters_obj = None
    if request.filters:
        filters_obj = request.filters.model_dump()

    background_tasks.add_task(
        _run_streaming_query,
        query_id,
        request.query,
        request.depth,
        filters_obj,
    )

    queue = _query_queues[query_id]

    async def event_generator():
        while True:
            event = await queue.get()
            if event is None:
                break
            yield {
                "event": event.get("event", "message"),
                "data": json.dumps(event.get("data", {})),
            }
        _query_queues.pop(query_id, None)

    return EventSourceResponse(event_generator())


async def _run_streaming_query(
    query_id: str,
    query_text: str,
    depth: int,
    filters_dict: dict | None,
):
    """Run streaming agent query in background."""
    queue = _query_queues.get(query_id)
    try:
        async with async_session() as db:
            filters = None
            if filters_dict:
                filters = SearchFilters(
                    jurisdiction=filters_dict.get("jurisdiction"),
                    document_type=filters_dict.get("document_type"),
                    regulatory_body=filters_dict.get("regulatory_body"),
                    authority_level=filters_dict.get("authority_level"),
                    tags=filters_dict.get("tags"),
                )

            agent = RetrievalAgent(db)
            full_response = ""
            citations_data: list[dict] = []

            async for event in agent.stream_query(
                query_text, depth=depth, filters=filters, query_id=query_id
            ):
                if queue:
                    await queue.put(event)
                if event.get("event") == "complete":
                    data = event.get("data", {})
                    full_response = data.get("response", "")
                    citations_data = data.get("citations", [])

            # Persist
            await retrieval_service.complete_query(
                db, query_id, full_response,
                citations_data, len(citations_data), len(full_response.split()) * 2,
            )
    except Exception:
        logger.exception("Streaming query failed for %s", query_id)
        if queue:
            await queue.put({
                "event": "error",
                "data": {"message": "Query failed. Check server logs."},
            })
    finally:
        if queue:
            await queue.put(None)


# --- Analysis endpoints ---


@router.post("/api/analysis", response_model=AnalysisResponse)
async def submit_analysis(
    request: AnalysisRequest,
    db: AsyncSession = Depends(get_db),
):
    """Submit a cross-corpus analysis."""
    analysis_id = f"a-{datetime.now(UTC).strftime('%Y%m%d%H%M%S%f')}"

    filters = None
    if request.filters:
        filters = SearchFilters(
            jurisdiction=request.filters.jurisdiction,
            document_type=request.filters.document_type,
            regulatory_body=request.filters.regulatory_body,
            authority_level=request.filters.authority_level,
            tags=request.filters.tags,
        )

    # Save record
    await retrieval_service.save_analysis(
        db, analysis_id, request.analysis_type,
        request.primary_text,
        request.filters.model_dump() if request.filters else None,
        request.depth,
    )

    result = await run_analysis(
        db,
        analysis_type=request.analysis_type,
        primary_text=request.primary_text,
        filters=filters,
        depth=request.depth,
        analysis_id=analysis_id,
    )

    # Persist
    findings_data = [
        {
            "category": f.category,
            "severity": f.severity,
            "description": f.description,
            "recommendation": f.recommendation,
        }
        for f in result.findings
    ]
    citations_data = [
        {
            "chunk_id": c.chunk_id,
            "section_path": c.section_path,
            "source_id": c.source_id,
            "source_url": c.source_url,
            "regulatory_body": c.regulatory_body,
            "jurisdiction": c.jurisdiction,
            "authority_level": c.authority_level,
            "confidence": c.confidence,
        }
        for c in result.citations
    ]

    await retrieval_service.complete_analysis(
        db, analysis_id, findings_data,
        result.summary, result.coverage_score, citations_data,
    )

    return AnalysisResponse(
        analysis_id=analysis_id,
        analysis_type=result.analysis_type,
        findings=[FindingSchema(**f) for f in findings_data],
        summary=result.summary,
        coverage_score=result.coverage_score,
        citations=[CitationSchema(**c) for c in citations_data],
    )


@router.get("/api/analysis/{analysis_id}", response_model=AnalysisResponse)
async def get_analysis_result(
    analysis_id: str, db: AsyncSession = Depends(get_db)
):
    """Get an analysis result by ID."""
    record = await retrieval_service.get_analysis(db, analysis_id)
    if not record:
        raise HTTPException(status_code=404, detail="Analysis not found")

    return AnalysisResponse(
        analysis_id=record.id,
        analysis_type=record.analysis_type,
        findings=[FindingSchema(**f) for f in (record.findings or [])],
        summary=record.summary,
        coverage_score=record.coverage_score,
        citations=[CitationSchema(**c) for c in (record.citations or [])],
    )


# --- Corpus endpoints ---


@router.get("/api/corpus/stats", response_model=CorpusStats)
async def corpus_stats(db: AsyncSession = Depends(get_db)):
    return await retrieval_service.get_corpus_stats(db)


@router.get("/api/corpus/sources", response_model=list[CorpusSourceSummary])
async def corpus_sources(db: AsyncSession = Depends(get_db)):
    return await retrieval_service.list_corpus_sources(db)


# --- Citation endpoint ---


@router.get("/api/citations/{chunk_id}", response_model=CitationSchema)
async def get_citation(chunk_id: str, db: AsyncSession = Depends(get_db)):
    """Get full citation chain for a chunk."""
    citation = await retrieval_service.get_citation_chain(db, chunk_id)
    if not citation:
        raise HTTPException(status_code=404, detail="Chunk not found")
    return citation
