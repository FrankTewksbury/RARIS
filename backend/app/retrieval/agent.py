"""Retrieval agent — plans queries, synthesizes responses, threads citations."""

import logging
from collections.abc import AsyncIterator
from dataclasses import dataclass

from sqlalchemy.ext.asyncio import AsyncSession

from app.llm.registry import get_provider
from app.retrieval.citations import CitationChain, build_citations_for_results
from app.retrieval.reranker import rerank
from app.retrieval.search import SearchFilters, SearchResult, hybrid_search

logger = logging.getLogger(__name__)

DEPTH_CONFIG = {
    1: {
        "name": "Quick Check",
        "token_budget": 200,
        "instructions": (
            "Provide a brief yes/no answer with one supporting citation. "
            "Keep the response under 200 tokens."
        ),
    },
    2: {
        "name": "Summary",
        "token_budget": 500,
        "instructions": (
            "Summarize the key regulatory points with supporting citations. "
            "Keep the response under 500 tokens."
        ),
    },
    3: {
        "name": "Analysis",
        "token_budget": 1500,
        "instructions": (
            "Provide a detailed analysis with full citation chains. "
            "Address nuances, exceptions, and jurisdictional differences. "
            "Keep the response under 1500 tokens."
        ),
    },
    4: {
        "name": "Exhaustive",
        "token_budget": 4000,
        "instructions": (
            "Conduct a comprehensive regulatory audit. Cover all relevant "
            "sources, note conflicts and gaps, distinguish binding authority "
            "from advisory guidance. Keep the response under 4000 tokens."
        ),
    },
}

_SYSTEM_PROMPT = """You are a regulatory analysis agent. Answer the user's query using ONLY the \
retrieved regulatory sources provided below. Every factual claim must include \
an inline citation in the format [SOURCE_ID §section].

Depth level: {depth} — {depth_name}
{depth_instructions}

Retrieved sources:
{sources_block}

Rules:
- Never fabricate regulatory content
- If retrieved sources don't cover the query, say so explicitly
- Flag conflicting sources and note the conflict
- Distinguish binding authority from advisory guidance
- Use the exact source IDs provided in citations"""

_PLANNER_PROMPT = """Given the user's regulatory query below, determine if it needs to be \
decomposed into sub-queries for comprehensive retrieval.

Query: {query}

If the query is simple, return: {{"sub_queries": ["{query}"]}}
If it needs decomposition, return: {{"sub_queries": ["sub-query 1", "sub-query 2", ...]}}

Return ONLY valid JSON."""


@dataclass
class AgentResponse:
    query_id: str
    query: str
    depth: int
    response_text: str
    citations: list[CitationChain]
    sources_used: list[SearchResult]
    token_count: int


class RetrievalAgent:
    """Agent that plans retrieval, synthesizes responses, and threads citations."""

    def __init__(self, db: AsyncSession):
        self.db = db
        self.llm = get_provider()

    async def query(
        self,
        query_text: str,
        depth: int = 2,
        filters: SearchFilters | None = None,
        query_id: str = "",
    ) -> AgentResponse:
        """Execute a full agent query pipeline (non-streaming)."""
        depth = max(1, min(4, depth))
        config = DEPTH_CONFIG[depth]

        # Step 1: Plan sub-queries
        sub_queries = await self._plan_queries(query_text, depth)

        # Step 2: Retrieve for each sub-query
        all_results: list[SearchResult] = []
        for sq in sub_queries:
            results = await hybrid_search(self.db, sq, filters)
            all_results.extend(results)

        # Deduplicate by chunk_id
        seen: set[str] = set()
        unique_results: list[SearchResult] = []
        for r in all_results:
            if r.chunk_id not in seen:
                seen.add(r.chunk_id)
                unique_results.append(r)

        # Step 3: Re-rank
        top_k = min(config["token_budget"] // 100, 20)
        reranked = await rerank(query_text, unique_results, top_k=top_k)

        # Step 4: Build citation chains
        citations = await build_citations_for_results(self.db, reranked)

        # Step 5: Synthesize response
        response_text = await self._synthesize(
            query_text, depth, config, reranked, citations
        )

        return AgentResponse(
            query_id=query_id,
            query=query_text,
            depth=depth,
            response_text=response_text,
            citations=list(citations.values()),
            sources_used=reranked,
            token_count=len(response_text.split()) * 2,  # rough estimate
        )

    async def stream_query(
        self,
        query_text: str,
        depth: int = 2,
        filters: SearchFilters | None = None,
        query_id: str = "",
    ) -> AsyncIterator[dict]:
        """Execute agent query with SSE streaming."""
        depth = max(1, min(4, depth))
        config = DEPTH_CONFIG[depth]

        yield {"event": "status", "data": {"step": "planning", "query": query_text}}

        # Plan
        sub_queries = await self._plan_queries(query_text, depth)
        yield {
            "event": "status",
            "data": {"step": "retrieving", "sub_queries": sub_queries},
        }

        # Retrieve
        all_results: list[SearchResult] = []
        for sq in sub_queries:
            results = await hybrid_search(self.db, sq, filters)
            all_results.extend(results)

        seen: set[str] = set()
        unique_results: list[SearchResult] = []
        for r in all_results:
            if r.chunk_id not in seen:
                seen.add(r.chunk_id)
                unique_results.append(r)

        yield {
            "event": "status",
            "data": {
                "step": "reranking",
                "chunks_found": len(unique_results),
            },
        }

        # Re-rank
        top_k = min(config["token_budget"] // 100, 20)
        reranked = await rerank(query_text, unique_results, top_k=top_k)

        # Build citations
        citations = await build_citations_for_results(self.db, reranked)

        yield {
            "event": "status",
            "data": {"step": "synthesizing", "sources_count": len(reranked)},
        }

        # Stream synthesis
        sources_block = self._format_sources(reranked, citations)
        system_prompt = _SYSTEM_PROMPT.format(
            depth=depth,
            depth_name=config["name"],
            depth_instructions=config["instructions"],
            sources_block=sources_block,
        )

        full_response = ""
        async for token in self.llm.stream([
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": query_text},
        ]):
            full_response += token
            yield {"event": "token", "data": {"token": token}}

        # Final event with citations
        yield {
            "event": "complete",
            "data": {
                "query_id": query_id,
                "response": full_response,
                "citations": [
                    {
                        "chunk_id": c.chunk_id,
                        "section_path": c.section_path,
                        "document_title": c.document_title,
                        "source_id": c.source_id,
                        "source_url": c.source_url,
                        "regulatory_body": c.regulatory_body,
                        "jurisdiction": c.jurisdiction,
                        "authority_level": c.authority_level,
                        "confidence": c.confidence,
                    }
                    for c in citations.values()
                ],
                "sources_count": len(reranked),
            },
        }

    async def _plan_queries(self, query: str, depth: int) -> list[str]:
        """Decompose complex queries into sub-queries for depth >= 3."""
        if depth < 3:
            return [query]

        try:
            import json

            prompt = _PLANNER_PROMPT.format(query=query)
            response = await self.llm.complete(
                [{"role": "user", "content": prompt}]
            )
            cleaned = response.strip()
            if cleaned.startswith("```"):
                cleaned = cleaned.split("\n", 1)[-1].rsplit("```", 1)[0]
            data = json.loads(cleaned)
            sub_queries = data.get("sub_queries", [query])
            return sub_queries if sub_queries else [query]
        except Exception:
            logger.debug("Query planning failed, using original query")
            return [query]

    async def _synthesize(
        self,
        query: str,
        depth: int,
        config: dict,
        results: list[SearchResult],
        citations: dict[str, CitationChain],
    ) -> str:
        """Synthesize the final response using retrieved sources."""
        sources_block = self._format_sources(results, citations)

        system_prompt = _SYSTEM_PROMPT.format(
            depth=depth,
            depth_name=config["name"],
            depth_instructions=config["instructions"],
            sources_block=sources_block,
        )

        response = await self.llm.complete([
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": query},
        ])
        return response

    def _format_sources(
        self,
        results: list[SearchResult],
        citations: dict[str, CitationChain],
    ) -> str:
        """Format search results into a sources block for the LLM."""
        blocks: list[str] = []
        for i, r in enumerate(results, 1):
            chain = citations.get(r.chunk_id)
            source_id = chain.source_id if chain else r.source_id
            authority = chain.authority_level if chain else "unknown"
            body = chain.regulatory_body if chain else ""

            blocks.append(
                f"[{source_id} §{r.section_path}] "
                f"(authority: {authority}, body: {body})\n"
                f"{r.text}\n"
            )
        return "\n---\n".join(blocks) if blocks else "(No sources retrieved)"
