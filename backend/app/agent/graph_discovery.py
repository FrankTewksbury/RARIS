"""Hierarchical Graph Discovery Engine (V3).

Implements L0/L1/L2/L3 traversal using grounded LLM calls and topic-indexed
seed injection. Reuses existing pipeline utilities and prompts.

Graph state is in-memory during the run. Final output is a flat manifest
(programs, sources, bodies) — same schema as the V2 DomainDiscoveryAgent.
"""

import json
import logging
import re
from collections import Counter
from collections.abc import AsyncGenerator

from sqlalchemy.ext.asyncio import AsyncSession

from app.agent.discovery import _extract_json, _safe_enum
from app.agent.prompts import (
    GROUNDED_LANDSCAPE_MAPPER_PROMPT,
    GROUNDED_SOURCE_HUNTER_PROMPT,
    GUIDANCE_CONTEXT_BLOCK,
    L1_ENTITY_EXPANSION_PROMPT,
    L3_GAP_FILL_PROMPT,
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
    Program,
    ProgramGeoScope,
    ProgramStatus,
    RegulatoryBody,
    Source,
    SourceFormat,
    SourceType,
)

logger = logging.getLogger(__name__)

# Batch sizes — match V2 pipeline defaults
SOURCE_HUNTER_BATCH_SIZE = 10

# Taxonomy-driven search queries per entity type (from taxonomy doc)
_ENTITY_SEARCH_QUERIES: dict[str, str] = {
    "state_hfa": 'List all State Housing Finance Agency second mortgage programs in {geo_scope} for 2026',
    "municipal": 'city-level down payment assistance grants for {geo_scope} funded by CDBG or HOME funds',
    "nonprofit": 'non-profit homeownership programs in {geo_scope} that offer silent second mortgages',
    "employer": 'employer-assisted housing program {geo_scope} hospital university',
    "tribal": 'Section 184 tribal housing authority homebuyer assistance {geo_scope}',
    "cdfi": 'CDFI down payment assistance programs in {geo_scope}',
}

# Map seed program_type to taxonomy entity types for L1 expansion
_SEED_TO_ENTITY_TYPE: dict[str, str] = {
    "veteran": "federal",
    "tribal": "tribal",
    "occupation": "federal",
    "cdfi": "nonprofit",
    "eah": "employer",
    "municipal": "municipal",
    "lmi": "state_hfa",
    "fthb": "state_hfa",
    "general": "state_hfa",
}


class DiscoveryGraph:
    """Orchestrates hierarchical L0-L3 discovery with web grounding."""

    def __init__(self, llm: LLMProvider, db: AsyncSession, manifest_id: str):
        self.llm = llm
        self.db = db
        self.manifest_id = manifest_id

    async def run(
        self,
        domain_description: str,
        *,
        k_depth: int = 2,
        geo_scope: str = "state",
        target_segments: list[str] | None = None,
        seed_index: dict[str, list[dict]] | None = None,
        seed_programs: list[dict] | None = None,
        seed_anchors: list[dict] | None = None,
        seed_metrics: dict | None = None,
        constitution_text: str = "",
        instruction_text: str = "",
    ) -> AsyncGenerator[dict, None]:
        """Execute hierarchical discovery, yielding SSE events."""
        _seed_index = seed_index or {}
        all_seed_programs = seed_programs or []
        guidance_block = self._build_guidance_block(
            constitution_text, instruction_text,
            k_depth=k_depth, geo_scope=geo_scope,
            target_segments=target_segments or [],
            seed_programs=all_seed_programs,
            seed_metrics=seed_metrics or {},
        )

        all_bodies: list[dict] = []
        all_sources: list[dict] = []
        all_programs: list[dict] = []
        source_id_counter = 1

        # ── L0: Federal/State Landscape (grounded) ───────────────────────
        yield self._event("step", step="L0_landscape", status="running",
                          message="L0: Discovering regulatory landscape with web grounding...",
                          discovery_level=0)

        landscape = await self._grounded_landscape_mapper(
            domain_description, guidance_block,
        )
        bodies = landscape.get("regulatory_bodies", [])
        all_bodies.extend(bodies)

        # Persist L0 bodies
        for body_data in bodies:
            self.db.add(RegulatoryBody(
                id=body_data["id"],
                manifest_id=self.manifest_id,
                name=body_data["name"],
                jurisdiction=_safe_enum(Jurisdiction, body_data.get("jurisdiction")),
                authority_type=_safe_enum(AuthorityType, body_data.get("authority_type")),
                url=body_data.get("url", ""),
                governs=body_data.get("governs", []),
            ))

        manifest = await self.db.get(Manifest, self.manifest_id)
        manifest.jurisdiction_hierarchy = landscape.get("jurisdiction_hierarchy")
        await self.db.flush()

        yield self._event("step", step="L0_landscape", status="complete",
                          message=f"L0: Found {len(bodies)} regulatory bodies.",
                          discovery_level=0, bodies_found=len(bodies),
                          nodes_at_level=len(bodies), cumulative_programs=0)

        # ── L0: Source Hunter (grounded, batched) ─────────────────────────
        yield self._event("step", step="L0_sources", status="running",
                          message=f"L0: Discovering sources for {len(bodies)} bodies...",
                          discovery_level=0)

        batches = [
            bodies[i:i + SOURCE_HUNTER_BATCH_SIZE]
            for i in range(0, len(bodies), SOURCE_HUNTER_BATCH_SIZE)
        ]
        for batch_idx, batch in enumerate(batches):
            batch_sources = await self._grounded_source_hunter(
                batch, start_id=source_id_counter, guidance_block=guidance_block,
            )
            new_sources = batch_sources.get("sources", [])
            for src in new_sources:
                src["id"] = f"src-{source_id_counter:03d}"
                source_id_counter += 1
            all_sources.extend(new_sources)

            yield self._event("progress", discovery_level=0,
                              sources_found=len(all_sources),
                              bodies_processed=(batch_idx + 1) * SOURCE_HUNTER_BATCH_SIZE,
                              total_bodies=len(bodies))

        # Persist L0 sources
        for src_data in all_sources:
            self.db.add(Source(
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
                confidence=src_data.get("confidence", 0.5),
                needs_human_review=src_data.get("needs_human_review", False),
                classification_tags=src_data.get("classification_tags", []),
            ))
        await self.db.commit()

        yield self._event("step", step="L0_sources", status="complete",
                          message=f"L0: Found {len(all_sources)} sources.",
                          discovery_level=0, sources_found=len(all_sources),
                          cumulative_programs=0)

        # ── L1: Entity Expansion (grounded + topic seeds) ────────────────
        yield self._event("step", step="L1_expansion", status="running",
                          message="L1: Expanding discovery graph by entity type...",
                          discovery_level=1)

        # Determine which entity types need expansion based on seed index
        entity_types_to_expand = set()
        for ptype in _seed_index:
            mapped = _SEED_TO_ENTITY_TYPE.get(ptype)
            if mapped:
                entity_types_to_expand.add(mapped)
        # Always expand these underrepresented types if seeds exist
        for forced in ("municipal", "nonprofit", "employer", "tribal"):
            if forced in _ENTITY_SEARCH_QUERIES:
                entity_types_to_expand.add(forced)

        l1_programs: list[dict] = []
        for entity_type in sorted(entity_types_to_expand):
            # Find matching seeds for this entity type
            matching_seeds: list[dict] = []
            for ptype, mapped_entity in _SEED_TO_ENTITY_TYPE.items():
                if mapped_entity == entity_type:
                    matching_seeds.extend(_seed_index.get(ptype, []))

            seed_hints = matching_seeds[:20]  # Cap hints per expansion
            search_query = _ENTITY_SEARCH_QUERIES.get(
                entity_type, f"down payment assistance programs {entity_type} {{geo_scope}}"
            ).format(geo_scope=geo_scope)

            try:
                expansion = await self._entity_expansion(
                    parent_entity_name=domain_description,
                    parent_entity_type="domain",
                    target_entity_type=entity_type,
                    geo_scope=geo_scope,
                    guidance_block=guidance_block,
                    seed_hints=seed_hints,
                    search_query=search_query,
                )

                for entity in expansion.get("entities", []):
                    for program in entity.get("programs", []):
                        program.setdefault("provenance_links", {})
                        program["provenance_links"]["discovery_level"] = "L1"
                        l1_programs.append(program)

            except Exception as exc:
                logger.warning(
                    "[graph] L1 expansion for %s skipped: %s", entity_type, exc,
                )

        all_programs.extend(l1_programs)

        yield self._event("step", step="L1_expansion", status="complete",
                          message=f"L1: Found {len(l1_programs)} programs across "
                                  f"{len(entity_types_to_expand)} entity types.",
                          discovery_level=1, programs_found=len(l1_programs),
                          nodes_at_level=len(entity_types_to_expand),
                          cumulative_programs=len(all_programs))

        # ── L2: Program dedup and merge ───────────────────────────────────
        yield self._event("step", step="L2_dedup", status="running",
                          message="L2: Deduplicating and merging programs...",
                          discovery_level=2)

        deduped = self._dedupe_programs(all_programs)

        yield self._event("step", step="L2_dedup", status="complete",
                          message=f"L2: {len(deduped)} unique programs after dedup.",
                          discovery_level=2, programs_found=len(deduped),
                          cumulative_programs=len(deduped))

        # ── L3: Gap Fill ──────────────────────────────────────────────────
        yield self._event("step", step="L3_gap_fill", status="running",
                          message="L3: Searching for unmatched seeds and coverage gaps...",
                          discovery_level=3)

        # Find unmatched seeds
        discovered_names = {
            self._normalize_name(p.get("name", "")) for p in deduped
        }
        unmatched_seeds = [
            s for s in all_seed_programs
            if self._normalize_name(s.get("name", "")) not in discovered_names
        ]

        # Identify gap categories
        discovered_types = Counter(
            p.get("provenance_links", {}).get("discovery_level", "L0")
            for p in deduped
        )
        gap_categories = [
            etype for etype in _ENTITY_SEARCH_QUERIES
            if etype not in {
                _SEED_TO_ENTITY_TYPE.get(p.get("program_type", "general"), "")
                for p in deduped
            }
        ]

        l3_programs: list[dict] = []
        if unmatched_seeds or gap_categories:
            try:
                gap_result = await self._gap_fill(
                    domain_description=domain_description,
                    geo_scope=geo_scope,
                    guidance_block=guidance_block,
                    discovered_count=len(deduped),
                    unmatched_seeds=unmatched_seeds[:50],  # Cap to avoid token overflow
                    gap_categories=gap_categories,
                )
                l3_programs = gap_result.get("programs", [])
                for p in l3_programs:
                    p.setdefault("provenance_links", {})
                    p["provenance_links"]["discovery_level"] = "L3"
            except Exception as exc:
                logger.warning("[graph] L3 gap fill failed: %s", exc)

        all_programs_final = self._dedupe_programs(deduped + l3_programs)

        yield self._event("step", step="L3_gap_fill", status="complete",
                          message=f"L3: Found {len(l3_programs)} additional programs. "
                                  f"Total: {len(all_programs_final)}.",
                          discovery_level=3, programs_found=len(l3_programs),
                          cumulative_programs=len(all_programs_final))

        # ── Persist programs ──────────────────────────────────────────────
        for idx, program_data in enumerate(all_programs_final, start=1):
            self.db.add(Program(
                id=self._program_row_id(idx),
                manifest_id=self.manifest_id,
                canonical_id=self._canonical_program_id(program_data),
                name=program_data.get("name", "Unknown Program"),
                administering_entity=program_data.get("administering_entity", "Unknown"),
                geo_scope=_safe_enum(
                    ProgramGeoScope, program_data.get("geo_scope"), ProgramGeoScope.state,
                ),
                jurisdiction=program_data.get("jurisdiction"),
                benefits=program_data.get("benefits"),
                eligibility=program_data.get("eligibility"),
                status=_safe_enum(
                    ProgramStatus, program_data.get("status"), ProgramStatus.verification_pending,
                ),
                evidence_snippet=program_data.get("evidence_snippet"),
                source_urls=program_data.get("source_urls", []),
                provenance_links=program_data.get("provenance_links", {}),
                confidence=float(program_data.get("confidence", 0.0) or 0.0),
                needs_human_review=bool(program_data.get("needs_human_review", False)),
            ))
        await self.db.flush()

        # ── Coverage assessment ───────────────────────────────────────────
        # Compute seed match metrics
        seed_match_by_topic = self._compute_seed_match_rates(
            all_seed_programs, all_programs_final, _seed_index,
        )
        total_seed_recovery = sum(
            v["matched"] for v in seed_match_by_topic.values()
        )
        total_seeds = len(all_seed_programs)
        seed_recovery_rate = round(total_seed_recovery / total_seeds, 3) if total_seeds else 0.0

        jurisdiction_counts = Counter(s.get("jurisdiction", "") for s in all_sources)
        type_counts = Counter(s.get("type", "") for s in all_sources)

        assessment = CoverageAssessment(
            manifest_id=self.manifest_id,
            total_sources=len(all_sources),
            by_jurisdiction=dict(jurisdiction_counts),
            by_type=dict(type_counts),
            completeness_score=min(seed_recovery_rate + 0.3, 1.0),
        )
        self.db.add(assessment)

        # Finalize manifest
        manifest.status = ManifestStatus.pending_review
        manifest.completeness_score = assessment.completeness_score
        await self.db.commit()

        yield self._event("complete",
                          manifest_id=self.manifest_id,
                          total_sources=len(all_sources),
                          total_bodies=len(all_bodies),
                          total_programs=len(all_programs_final),
                          coverage_score=assessment.completeness_score,
                          seed_recovery_count=total_seed_recovery,
                          seed_recovery_rate=seed_recovery_rate,
                          seed_match_rate_by_topic={
                              k: v["rate"] for k, v in seed_match_by_topic.items()
                          })

    # ── LLM call wrappers ─────────────────────────────────────────────────

    async def _grounded_landscape_mapper(
        self, domain_description: str, guidance_block: str,
    ) -> dict:
        prompt = GROUNDED_LANDSCAPE_MAPPER_PROMPT.format(
            domain_description=domain_description,
            guidance_block=guidance_block,
        )
        text, citations = await self.llm.complete_grounded([
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": prompt},
        ], max_tokens=16384)
        result = _extract_json(text)
        # Attach grounding citations to bodies
        citation_urls = {c.url for c in citations}
        for body in result.get("regulatory_bodies", []):
            body_url = body.get("url", "")
            body["grounded"] = body_url in citation_urls
        return result

    async def _grounded_source_hunter(
        self, bodies: list[dict], start_id: int, guidance_block: str,
    ) -> dict:
        bodies_json = json.dumps(bodies, indent=2)
        prompt = GROUNDED_SOURCE_HUNTER_PROMPT.format(
            bodies_json=bodies_json,
            start_id=start_id,
            guidance_block=guidance_block,
        )
        text, citations = await self.llm.complete_grounded([
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": prompt},
        ], max_tokens=16384)
        result = _extract_json(text)
        # Mark sources as grounded if their URL was in citations
        citation_urls = {c.url for c in citations}
        for src in result.get("sources", []):
            src_url = src.get("url", "")
            src["grounded"] = src_url in citation_urls
        return result

    async def _entity_expansion(
        self,
        parent_entity_name: str,
        parent_entity_type: str,
        target_entity_type: str,
        geo_scope: str,
        guidance_block: str,
        seed_hints: list[dict],
        search_query: str,
    ) -> dict:
        prompt = L1_ENTITY_EXPANSION_PROMPT.format(
            parent_entity_name=parent_entity_name,
            parent_entity_type=parent_entity_type,
            target_entity_type=target_entity_type,
            geo_scope=geo_scope,
            guidance_block=guidance_block,
            seed_hints_json=json.dumps(seed_hints[:10], indent=2),
            search_queries=search_query,
        )
        text, _citations = await self.llm.complete_grounded([
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": prompt},
        ], max_tokens=8192)
        return _extract_json(text)

    async def _gap_fill(
        self,
        domain_description: str,
        geo_scope: str,
        guidance_block: str,
        discovered_count: int,
        unmatched_seeds: list[dict],
        gap_categories: list[str],
    ) -> dict:
        prompt = L3_GAP_FILL_PROMPT.format(
            domain_description=domain_description,
            geo_scope=geo_scope,
            guidance_block=guidance_block,
            discovered_count=discovered_count,
            unmatched_seeds_json=json.dumps(unmatched_seeds[:30], indent=2),
            gap_categories_json=json.dumps(gap_categories, indent=2),
        )
        text, _citations = await self.llm.complete_grounded([
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": prompt},
        ], max_tokens=8192)
        return _extract_json(text)

    # ── Utility methods ───────────────────────────────────────────────────

    @staticmethod
    def _build_guidance_block(
        constitution_text: str,
        instruction_text: str,
        k_depth: int = 2,
        geo_scope: str = "state",
        target_segments: list[str] | None = None,
        seed_programs: list[dict] | None = None,
        seed_metrics: dict | None = None,
    ) -> str:
        snippets: list[str] = []
        if constitution_text.strip():
            snippets.append(f"Constitution guardrails:\n{constitution_text.strip()[:12000]}")
        if instruction_text.strip():
            snippets.append(f"Instruction guidance:\n{instruction_text.strip()[:12000]}")
        controls = [f"- k_depth: {k_depth}", f"- geo_scope: {geo_scope}"]
        if target_segments:
            controls.append(f"- target_segments: {', '.join(target_segments)}")
        snippets.append("Run controls:\n" + "\n".join(controls))
        if seed_programs:
            snippets.append(f"Seeding context: {len(seed_programs)} program seeds available")
        if not snippets:
            return ""
        return GUIDANCE_CONTEXT_BLOCK.format(guidance_context="\n\n".join(snippets))

    @staticmethod
    def _event(event_type: str, **data) -> dict:
        return {"event": event_type, "data": data}

    @staticmethod
    def _normalize_name(name: str) -> str:
        return re.sub(r"[^a-z0-9]", "", name.lower())

    @staticmethod
    def _canonical_program_id(program_data: dict) -> str:
        name = re.sub(r"[^a-z0-9]+", "-", str(program_data.get("name", "")).lower()).strip("-")
        entity = re.sub(
            r"[^a-z0-9]+", "-", str(program_data.get("administering_entity", "")).lower()
        ).strip("-")
        jurisdiction = re.sub(
            r"[^a-z0-9]+", "-", str(program_data.get("jurisdiction", "")).lower()
        ).strip("-")
        return "-".join(part for part in [entity, name, jurisdiction] if part)[:255] or "unknown-program"

    @classmethod
    def _dedupe_programs(cls, programs: list[dict]) -> list[dict]:
        deduped: dict[str, dict] = {}
        for program in programs:
            key = cls._canonical_program_id(program)
            existing = deduped.get(key)
            if not existing:
                deduped[key] = program
                continue
            if float(program.get("confidence", 0.0) or 0.0) > float(
                existing.get("confidence", 0.0) or 0.0
            ):
                deduped[key] = program
        return list(deduped.values())

    def _program_row_id(self, idx: int) -> str:
        manifest_suffix = re.sub(r"[^a-z0-9]+", "", self.manifest_id.lower())[-12:]
        return f"prog-{manifest_suffix}-{idx:04d}"

    @staticmethod
    def _compute_seed_match_rates(
        all_seeds: list[dict],
        discovered: list[dict],
        seed_index: dict[str, list[dict]],
    ) -> dict[str, dict]:
        """Compute per-topic seed match rates."""
        discovered_names = {
            re.sub(r"[^a-z0-9]", "", p.get("name", "").lower())
            for p in discovered
        }
        result: dict[str, dict] = {}
        for topic, seeds in seed_index.items():
            total = len(seeds)
            matched = sum(
                1 for s in seeds
                if re.sub(r"[^a-z0-9]", "", s.get("name", "").lower()) in discovered_names
            )
            result[topic] = {
                "total": total,
                "matched": matched,
                "rate": round(matched / total, 3) if total else 0.0,
            }
        return result
