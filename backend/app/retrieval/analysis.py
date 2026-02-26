"""Cross-corpus analysis — gap detection, conflict detection, coverage mapping."""

import json
import logging
from dataclasses import dataclass, field

from sqlalchemy.ext.asyncio import AsyncSession

from app.llm.registry import get_provider
from app.retrieval.citations import CitationChain, build_citations_for_results
from app.retrieval.search import SearchFilters, SearchResult, hybrid_search

logger = logging.getLogger(__name__)


@dataclass
class Finding:
    category: str  # gap | conflict | coverage | impact
    severity: str  # high | medium | low
    description: str
    primary_citation: dict
    comparison_citation: dict | None = None
    recommendation: str = ""


@dataclass
class AnalysisResult:
    analysis_id: str
    analysis_type: str
    findings: list[Finding]
    summary: str
    coverage_score: float | None = None
    citations: list[CitationChain] = field(default_factory=list)


_GAP_PROMPT = """You are a regulatory compliance analyst. Analyze the following document \
against the retrieved regulatory sources to identify compliance gaps.

Primary document text:
{primary_text}

Regulatory sources:
{sources_block}

Identify gaps where the primary document fails to address regulatory requirements.
Return a JSON object:
{{
  "findings": [
    {{
      "category": "gap",
      "severity": "high|medium|low",
      "description": "Description of the gap",
      "regulatory_requirement": "The requirement that is not met",
      "recommendation": "How to address the gap"
    }}
  ],
  "summary": "Overall gap analysis summary",
  "coverage_score": 0.0-1.0
}}"""

_CONFLICT_PROMPT = """You are a regulatory analyst. Compare the following regulatory sources \
and identify any conflicting requirements.

Sources:
{sources_block}

Identify conflicts, contradictions, or overlapping requirements between sources.
Return a JSON object:
{{
  "findings": [
    {{
      "category": "conflict",
      "severity": "high|medium|low",
      "description": "Description of the conflict",
      "recommendation": "How to resolve or manage the conflict"
    }}
  ],
  "summary": "Overall conflict analysis summary"
}}"""


async def run_analysis(
    db: AsyncSession,
    analysis_type: str,
    primary_text: str,
    filters: SearchFilters | None = None,
    depth: int = 3,
    analysis_id: str = "",
) -> AnalysisResult:
    """Run a cross-corpus analysis.

    Args:
        analysis_type: gap | conflict | coverage | change_impact
        primary_text: The document or text to analyze.
        filters: Scope of comparison.
        depth: Analysis depth (affects search breadth).
    """
    llm = get_provider()

    # Retrieve relevant regulatory sources
    top_k = depth * 10
    results = await hybrid_search(db, primary_text[:500], filters, top_k=top_k)

    # Build citations
    citations = await build_citations_for_results(db, results)

    # Format sources
    sources_block = _format_sources(results, citations)

    # Select prompt based on analysis type
    if analysis_type == "gap":
        prompt = _GAP_PROMPT.format(
            primary_text=primary_text[:3000],
            sources_block=sources_block,
        )
    elif analysis_type == "conflict":
        prompt = _CONFLICT_PROMPT.format(sources_block=sources_block)
    else:
        # Coverage and change_impact use the gap prompt as base
        prompt = _GAP_PROMPT.format(
            primary_text=primary_text[:3000],
            sources_block=sources_block,
        )

    # Get LLM analysis
    response = await llm.complete([{"role": "user", "content": prompt}])

    # Parse response
    findings, summary, coverage = _parse_analysis_response(response)

    return AnalysisResult(
        analysis_id=analysis_id,
        analysis_type=analysis_type,
        findings=findings,
        summary=summary,
        coverage_score=coverage,
        citations=list(citations.values()),
    )


def _parse_analysis_response(
    response: str,
) -> tuple[list[Finding], str, float | None]:
    """Parse the LLM analysis response into structured findings."""
    try:
        cleaned = response.strip()
        if cleaned.startswith("```"):
            cleaned = cleaned.split("\n", 1)[-1].rsplit("```", 1)[0]
        data = json.loads(cleaned)

        findings = []
        for f in data.get("findings", []):
            findings.append(Finding(
                category=f.get("category", "gap"),
                severity=f.get("severity", "medium"),
                description=f.get("description", ""),
                primary_citation={},
                recommendation=f.get("recommendation", ""),
            ))

        summary = data.get("summary", "")
        coverage = data.get("coverage_score")
        if coverage is not None:
            coverage = float(coverage)

        return findings, summary, coverage

    except (json.JSONDecodeError, ValueError):
        logger.debug("Failed to parse analysis response as JSON")
        return (
            [],
            response[:500],
            None,
        )


def _format_sources(
    results: list[SearchResult],
    citations: dict[str, CitationChain],
) -> str:
    """Format search results into a sources block for analysis."""
    blocks: list[str] = []
    for r in results:
        chain = citations.get(r.chunk_id)
        source_id = chain.source_id if chain else r.source_id
        authority = chain.authority_level if chain else "unknown"

        blocks.append(
            f"[{source_id} §{r.section_path}] (authority: {authority})\n"
            f"{r.text}\n"
        )
    return "\n---\n".join(blocks) if blocks else "(No sources found)"
