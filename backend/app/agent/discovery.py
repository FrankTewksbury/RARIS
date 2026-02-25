import json
import logging
import re
from collections import Counter
from collections.abc import AsyncGenerator

from sqlalchemy.ext.asyncio import AsyncSession

from app.agent.prompts import (
    COVERAGE_ASSESSOR_PROMPT,
    LANDSCAPE_MAPPER_PROMPT,
    RELATIONSHIP_MAPPER_PROMPT,
    SOURCE_HUNTER_PROMPT,
    SYSTEM_PROMPT,
)
from app.llm.base import LLMProvider
from app.models.manifest import (
    AccessMethod,
    AuthorityLevel,
    AuthorityType,
    CoverageAssessment,
    GapSeverity,
    Jurisdiction,
    KnownGap,
    Manifest,
    ManifestStatus,
    RegulatoryBody,
    Source,
    SourceFormat,
    SourceType,
)

logger = logging.getLogger(__name__)


def _extract_json(text: str) -> dict:
    """Extract JSON from LLM response, handling markdown code blocks."""
    # Try to find JSON in code blocks first
    match = re.search(r"```(?:json)?\s*\n?(.*?)\n?```", text, re.DOTALL)
    if match:
        return json.loads(match.group(1))
    # Try parsing the whole thing
    return json.loads(text)


def _safe_enum(enum_cls, value, default=None):
    """Safely convert a string to an enum value."""
    try:
        return enum_cls(value)
    except (ValueError, KeyError):
        return default or list(enum_cls)[0]


class DomainDiscoveryAgent:
    """Orchestrates the 5-step domain discovery pipeline."""

    def __init__(self, llm: LLMProvider, db: AsyncSession, manifest_id: str):
        self.llm = llm
        self.db = db
        self.manifest_id = manifest_id

    async def run(self, domain_description: str) -> AsyncGenerator[dict, None]:
        """Execute the full discovery pipeline, yielding SSE events."""

        # Step 1: Landscape Mapper
        yield {"event": "step", "data": {
            "step": "landscape_mapper", "status": "running",
            "message": "Identifying regulatory bodies and jurisdiction hierarchy...",
        }}

        landscape = await self._landscape_mapper(domain_description)
        bodies = landscape.get("regulatory_bodies", [])

        yield {"event": "step", "data": {
            "step": "landscape_mapper", "status": "complete",
            "bodies_found": len(bodies),
        }}

        # Persist regulatory bodies
        for body_data in bodies:
            body = RegulatoryBody(
                id=body_data["id"],
                manifest_id=self.manifest_id,
                name=body_data["name"],
                jurisdiction=_safe_enum(Jurisdiction, body_data.get("jurisdiction")),
                authority_type=_safe_enum(AuthorityType, body_data.get("authority_type")),
                url=body_data.get("url", ""),
                governs=body_data.get("governs", []),
            )
            self.db.add(body)

        # Update manifest with hierarchy
        manifest = await self.db.get(Manifest, self.manifest_id)
        manifest.jurisdiction_hierarchy = landscape.get("jurisdiction_hierarchy")
        await self.db.flush()

        # Step 2: Source Hunter
        yield {"event": "step", "data": {
            "step": "source_hunter", "status": "running",
            "message": f"Discovering sources for {len(bodies)} regulatory bodies...",
        }}

        sources_data = await self._source_hunter(bodies)
        sources = sources_data.get("sources", [])

        yield {"event": "step", "data": {
            "step": "source_hunter", "status": "complete",
            "sources_found": len(sources),
        }}
        yield {"event": "progress", "data": {
            "sources_found": len(sources),
            "bodies_processed": len(bodies),
            "total_bodies": len(bodies),
        }}

        # Persist sources
        for src_data in sources:
            source = Source(
                id=src_data["id"],
                manifest_id=self.manifest_id,
                name=src_data["name"],
                regulatory_body_id=src_data.get("regulatory_body", ""),
                type=_safe_enum(SourceType, src_data.get("type")),
                format=_safe_enum(SourceFormat, src_data.get("format")),
                authority=_safe_enum(AuthorityLevel, src_data.get("authority")),
                jurisdiction=_safe_enum(Jurisdiction, src_data.get("jurisdiction")),
                url=src_data.get("url", ""),
                access_method=_safe_enum(AccessMethod, src_data.get("access_method")),
                update_frequency=src_data.get("update_frequency"),
                last_known_update=src_data.get("last_known_update"),
                estimated_size=src_data.get("estimated_size"),
                scraping_notes=src_data.get("scraping_notes"),
                confidence=src_data.get("confidence", 0.5),
                needs_human_review=src_data.get("needs_human_review", False),
                classification_tags=src_data.get("classification_tags", []),
                relationships=src_data.get("relationships", {}),
            )
            self.db.add(source)
        await self.db.flush()

        # Step 3: Relationship Mapper
        yield {"event": "step", "data": {
            "step": "relationship_mapper", "status": "running",
            "message": "Mapping cross-references and supersession chains...",
        }}

        relationships = await self._relationship_mapper(sources)

        # Update sources with relationships
        rel_map = relationships.get("relationships", {})
        for src_data in sources:
            src_id = src_data["id"]
            if src_id in rel_map:
                src_data["relationships"] = rel_map[src_id]

        yield {"event": "step", "data": {
            "step": "relationship_mapper", "status": "complete",
            "relationships_mapped": len(rel_map),
        }}

        # Step 4: Coverage Assessor
        yield {"event": "step", "data": {
            "step": "coverage_assessor", "status": "running",
            "message": "Evaluating discovery completeness...",
        }}

        jurisdiction_counts = Counter(s.get("jurisdiction", "") for s in sources)
        type_counts = Counter(s.get("type", "") for s in sources)

        coverage = await self._coverage_assessor(
            domain_description, len(bodies), len(sources),
            dict(jurisdiction_counts), dict(type_counts),
        )

        yield {"event": "step", "data": {
            "step": "coverage_assessor", "status": "complete",
            "completeness_score": coverage.get("completeness_score", 0),
        }}

        # Persist coverage assessment
        assessment = CoverageAssessment(
            manifest_id=self.manifest_id,
            total_sources=len(sources),
            by_jurisdiction=dict(jurisdiction_counts),
            by_type=dict(type_counts),
            completeness_score=coverage.get("completeness_score", 0.0),
        )
        self.db.add(assessment)
        await self.db.flush()

        for gap_data in coverage.get("known_gaps", []):
            gap = KnownGap(
                manifest_id=self.manifest_id,
                description=gap_data.get("description", ""),
                severity=_safe_enum(GapSeverity, gap_data.get("severity", "medium")),
                mitigation=gap_data.get("mitigation"),
            )
            self.db.add(gap)

        # Step 5: Finalize manifest
        yield {"event": "step", "data": {
            "step": "manifest_generator", "status": "running",
            "message": "Assembling final manifest...",
        }}

        manifest.status = ManifestStatus.pending_review
        manifest.completeness_score = coverage.get("completeness_score", 0.0)
        await self.db.commit()

        yield {"event": "step", "data": {
            "step": "manifest_generator", "status": "complete",
        }}
        yield {"event": "complete", "data": {
            "manifest_id": self.manifest_id,
            "total_sources": len(sources),
            "coverage_score": coverage.get("completeness_score", 0.0),
        }}

    async def _landscape_mapper(self, domain_description: str) -> dict:
        prompt = LANDSCAPE_MAPPER_PROMPT.format(domain_description=domain_description)
        response = await self.llm.complete([
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": prompt},
        ])
        return _extract_json(response)

    async def _source_hunter(self, bodies: list[dict]) -> dict:
        bodies_json = json.dumps(bodies, indent=2)
        prompt = SOURCE_HUNTER_PROMPT.format(bodies_json=bodies_json)
        response = await self.llm.complete([
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": prompt},
        ], max_tokens=8192)
        return _extract_json(response)

    async def _relationship_mapper(self, sources: list[dict]) -> dict:
        # Slim down sources for the prompt to avoid token limits
        slim_sources = [
            {"id": s["id"], "name": s["name"], "type": s.get("type"),
             "regulatory_body": s.get("regulatory_body")}
            for s in sources
        ]
        sources_json = json.dumps(slim_sources, indent=2)
        prompt = RELATIONSHIP_MAPPER_PROMPT.format(sources_json=sources_json)
        response = await self.llm.complete([
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": prompt},
        ])
        return _extract_json(response)

    async def _coverage_assessor(
        self, domain_description: str, bodies_count: int, sources_count: int,
        jurisdiction_breakdown: dict, type_breakdown: dict,
    ) -> dict:
        prompt = COVERAGE_ASSESSOR_PROMPT.format(
            domain_description=domain_description,
            bodies_count=bodies_count,
            sources_count=sources_count,
            jurisdiction_breakdown=json.dumps(jurisdiction_breakdown, indent=2),
            type_breakdown=json.dumps(type_breakdown, indent=2),
        )
        response = await self.llm.complete([
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": prompt},
        ])
        return _extract_json(response)
