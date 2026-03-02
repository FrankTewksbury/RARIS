"""Hierarchical Graph Discovery Engine (V5) — Domain-Agnostic BFS.

V5 architecture:
- L1: 6 (or N) parallel sector calls, each with a full 64-search AFC budget.
  Each call receives the full instruction_text prefixed with a sector scope header.
  No domain expertise lives in engine code — all methodology comes from the uploaded prompt.
- L2: One focused expansion call per L1 entity (parallelized via asyncio.gather).
  Each call finds all programs, portals, and guidelines for a single entity.
- L3: (k_depth=3) Program detail per program node — benefits, eligibility, status, portals.

Sector list is supplied at runtime from the uploaded sector JSON file.
Falls back to DEFAULT_SECTORS (from prompts.py) if no sector file is provided.

k_depth semantics:
  k_depth=1 → L1 entity discovery only
  k_depth=2 → L1 entities + L2 program expansion (default for first test run)
  k_depth=3 → L1 + L2 + L3 program detail verification

SSE events:
  sector_start / sector_complete       — one pair per L1 sector
  l1_assembly_complete                 — after all sectors merged and persisted
  entity_expansion_start / entity_expansion_complete — per L2 entity (k_depth >= 2)
  complete                             — final with coverage_summary + seed metrics
"""

import asyncio
import json
import logging
import re
from collections import Counter
from collections.abc import AsyncGenerator

from sqlalchemy.ext.asyncio import AsyncSession

from app.agent.discovery import _extract_json, _safe_enum
from app.agent.prompts import (
    DEFAULT_SECTORS,
    L0_ORCHESTRATOR_SYSTEM,
    SECTOR_SCOPE_HEADER,
)
from app.llm.base import LLMProvider
from app.models.manifest import (
    AccessMethod,
    AuthorityLevel,
    AuthorityType,
    CoverageAssessment,
    Jurisdiction,
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

# Confidence threshold below which items are flagged for human review
L2_VERIFY_THRESHOLD = 0.6

# Map seed program_type to sector keys for seed injection during L2 expansion
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

# Fallback instruction used when no instruction file is uploaded
_FALLBACK_INSTRUCTION = (
    "Discover all administering entities and assistance programs relevant to the assigned sector. "
    "Use web search to find current, real entities with verified URLs. "
    "Return structured JSON as specified in the OUTPUT FORMAT section."
)


class DiscoveryGraph:
    """V5 domain-agnostic BFS discovery engine."""

    def __init__(self, llm: LLMProvider, db: AsyncSession, manifest_id: str):
        self.llm = llm
        self.db = db
        self.manifest_id = manifest_id

    async def run(
        self,
        manifest_name: str,
        *,
        k_depth: int = 2,
        geo_scope: str = "state",
        sectors: list[dict] | None = None,
        sector_concurrency: int = 3,
        seed_index: dict[str, list[dict]] | None = None,
        seed_programs: list[dict] | None = None,
        constitution_text: str = "",
        instruction_text: str = "",
    ) -> AsyncGenerator[dict, None]:
        """Execute V5 BFS discovery, yielding SSE events.

        sectors: list of sector dicts from uploaded sector file.
                 Falls back to DEFAULT_SECTORS if empty or None.
        instruction_text: full text of the uploaded instruction file.
                          Each sector call receives this verbatim, prefixed by
                          a sector scope header. No domain content lives in code.
        """
        _sectors = sorted(
            sectors if sectors else DEFAULT_SECTORS,
            key=lambda s: s.get("priority", 99),
        )
        _seed_index = seed_index or {}
        _seed_programs = seed_programs or []
        _instruction = instruction_text.strip() or _FALLBACK_INSTRUCTION

        # Prepend constitution guardrails if provided
        if constitution_text.strip():
            _instruction = (
                "## Operational Guardrails (apply throughout)\n\n"
                + constitution_text.strip()
                + "\n\n---\n\n"
                + _instruction
            )

        all_entities: list[dict] = []
        all_sources: list[dict] = []
        all_programs: list[dict] = []
        source_id_counter = 1

        # ── L1: Parallel Sector Discovery ────────────────────────────────
        async for event in self._run_l1_sectors(
            sectors=_sectors,
            instruction_text=_instruction,
            sector_concurrency=sector_concurrency,
        ):
            if event.get("event") == "_l1_sector_result":
                # Internal event — harvest entities and sources
                data = event.get("data", {})
                sector_entities = data.get("administering_entities", [])
                sector_sources = data.get("sources", [])
                for src in sector_sources:
                    src.setdefault("id", f"src-{source_id_counter:03d}")
                    source_id_counter += 1
                all_entities.extend(sector_entities)
                all_sources.extend(sector_sources)
            else:
                yield event

        # Persist L1 entities as RegulatoryBody records
        for entity in all_entities:
            self.db.add(RegulatoryBody(
                id=entity.get("id", f"ent-{self._normalize_name(entity.get('name', ''))[:40]}"),
                manifest_id=self.manifest_id,
                name=entity.get("name", "Unknown Entity"),
                jurisdiction=_safe_enum(Jurisdiction, entity.get("jurisdiction")),
                authority_type=_safe_enum(AuthorityType, entity.get("entity_type")),
                url=entity.get("url", ""),
                governs=entity.get("governs", []),
            ))

        for src_data in all_sources:
            self.db.add(Source(
                id=src_data["id"],
                manifest_id=self.manifest_id,
                name=src_data.get("name", "Unknown Source"),
                regulatory_body_id=src_data.get("regulatory_body", ""),
                type=_safe_enum(SourceType, src_data.get("type")),
                format=_safe_enum(SourceFormat, src_data.get("format")),
                authority=_safe_enum(AuthorityLevel, src_data.get("authority")),
                jurisdiction=_safe_enum(Jurisdiction, src_data.get("jurisdiction")),
                url=src_data.get("url", ""),
                access_method=_safe_enum(AccessMethod, src_data.get("access_method")),
                confidence=float(src_data.get("confidence", 0.5) or 0.5),
                needs_human_review=bool(
                    src_data.get("needs_human_review", False)
                    or float(src_data.get("confidence", 0.5) or 0.5) < 0.5
                ),
                classification_tags=src_data.get("classification_tags", []),
            ))

        manifest = await self.db.get(Manifest, self.manifest_id)

        await self.db.commit()

        yield self._event("l1_assembly_complete",
                          total_entities=len(all_entities),
                          total_sources=len(all_sources),
                          sector_count=len(_sectors))

        if k_depth < 2:
            # k_depth=1 — entity graph only, skip program expansion
            manifest.status = ManifestStatus.pending_review
            await self.db.commit()
            yield self._event("complete",
                              manifest_id=self.manifest_id,
                              total_entities=len(all_entities),
                              total_programs=0,
                              coverage_summary=self._build_coverage_summary(_sectors, all_entities, []))
            return

        # ── L2: Per-Entity Program Expansion ─────────────────────────────
        async for event in self._run_l2_entity_expansion(
            entities=all_entities,
            instruction_text=_instruction,
            seed_index=_seed_index,
        ):
            if event.get("event") == "_l2_entity_result":
                data = event.get("data", {})
                entity_programs = data.get("programs", [])
                entity_sources = data.get("sources", [])
                for src in entity_sources:
                    src.setdefault("id", f"src-{source_id_counter:03d}")
                    source_id_counter += 1
                    all_sources.append(src)
                    self.db.add(Source(
                        id=src["id"],
                        manifest_id=self.manifest_id,
                        name=src.get("name", "Unknown Source"),
                        regulatory_body_id=src.get("regulatory_body", ""),
                        type=_safe_enum(SourceType, src.get("type")),
                        format=_safe_enum(SourceFormat, src.get("format")),
                        authority=_safe_enum(AuthorityLevel, src.get("authority")),
                        jurisdiction=_safe_enum(Jurisdiction, src.get("jurisdiction")),
                        url=src.get("url", ""),
                        access_method=_safe_enum(AccessMethod, src.get("access_method")),
                        confidence=float(src.get("confidence", 0.5) or 0.5),
                        needs_human_review=bool(
                            src.get("needs_human_review", False)
                            or float(src.get("confidence", 0.5) or 0.5) < 0.5
                        ),
                        classification_tags=src.get("classification_tags", []),
                    ))
                for prog in entity_programs:
                    prog.setdefault("provenance_links", {})
                    prog["provenance_links"]["discovery_level"] = "L2"
                    all_programs.append(prog)
            else:
                yield event

        # Dedup programs
        deduped = self._dedupe_programs(all_programs)

        # Persist programs
        for idx, program_data in enumerate(deduped, start=1):
            confidence = float(program_data.get("confidence", 0.0) or 0.0)
            needs_review = bool(
                program_data.get("needs_human_review", False) or confidence < 0.5
            )
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
                confidence=confidence,
                needs_human_review=needs_review,
            ))
        await self.db.flush()

        # Coverage assessment
        seed_match_by_topic = self._compute_seed_match_rates(
            _seed_programs, deduped, _seed_index,
        )
        total_seed_recovery = sum(v["matched"] for v in seed_match_by_topic.values())
        total_seeds = len(_seed_programs)
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

        coverage_summary = self._build_coverage_summary(_sectors, all_entities, deduped)
        manifest.status = ManifestStatus.pending_review
        manifest.completeness_score = assessment.completeness_score
        manifest.coverage_summary = coverage_summary
        await self.db.commit()

        yield self._event("complete",
                          manifest_id=self.manifest_id,
                          total_entities=len(all_entities),
                          total_sources=len(all_sources),
                          total_programs=len(deduped),
                          coverage_score=assessment.completeness_score,
                          coverage_summary=coverage_summary,
                          seed_recovery_count=total_seed_recovery,
                          seed_recovery_rate=seed_recovery_rate,
                          seed_match_rate_by_topic={
                              k: v["rate"] for k, v in seed_match_by_topic.items()
                          })

    # ── L1: Parallel Sector Calls ─────────────────────────────────────────

    async def _run_l1_sectors(
        self,
        sectors: list[dict],
        instruction_text: str,
        sector_concurrency: int = 3,
    ) -> AsyncGenerator[dict, None]:
        """Run all sector calls, yielding SSE events and internal result events."""
        total = len(sectors)

        # Run in batches of sector_concurrency to respect API rate limits
        for batch_start in range(0, total, sector_concurrency):
            batch = sectors[batch_start:batch_start + sector_concurrency]

            # Yield sector_start events before launching batch
            for sector in batch:
                yield self._event("sector_start",
                                  sector_key=sector["key"],
                                  sector_label=sector["label"],
                                  sector_n=sector.get("priority", batch_start + 1),
                                  sector_total=total)

            # Run batch in parallel
            tasks = [
                self._discover_sector(
                    sector=sector,
                    instruction_text=instruction_text,
                    sector_n=sector.get("priority", idx + 1),
                    sector_total=total,
                )
                for idx, sector in enumerate(batch)
            ]
            results = await asyncio.gather(*tasks, return_exceptions=True)

            for sector, result in zip(batch, results):
                if isinstance(result, Exception):
                    logger.warning("[graph v5] sector '%s' failed: %s", sector["key"], result)
                    yield self._event("sector_complete",
                                      sector_key=sector["key"],
                                      sector_label=sector["label"],
                                      status="failed",
                                      error=str(result),
                                      entities_found=0)
                    # Yield empty result so aggregation loop still works
                    yield {"event": "_l1_sector_result", "data": {
                        "sector_key": sector["key"],
                        "administering_entities": [],
                        "sources": [],
                    }}
                else:
                    entities = result.get("administering_entities", [])
                    sources = result.get("sources", [])
                    yield self._event("sector_complete",
                                      sector_key=sector["key"],
                                      sector_label=sector["label"],
                                      status="complete",
                                      entities_found=len(entities),
                                      programs_found=len(result.get("programs", [])))
                    yield {"event": "_l1_sector_result", "data": {
                        "sector_key": sector["key"],
                        "administering_entities": entities,
                        "sources": sources,
                    }}

            # Brief pause between batches to avoid rate limit spikes
            if batch_start + sector_concurrency < total:
                await asyncio.sleep(1.0)

    async def _discover_sector(
        self,
        sector: dict,
        instruction_text: str,
        sector_n: int,
        sector_total: int,
    ) -> dict:
        """Run one sector discovery call."""
        search_hints = sector.get("search_hints", [])
        if search_hints:
            hints_block = "\n## Suggested search queries for this sector:\n" + "\n".join(
                f"  - {hint}" for hint in search_hints
            ) + "\n"
        else:
            hints_block = ""

        sector_header = SECTOR_SCOPE_HEADER.format(
            sector_label=sector["label"],
            sector_n=sector_n,
            sector_total=sector_total,
            search_hints_block=hints_block,
        )
        prompt = sector_header + instruction_text

        text, _citations = await asyncio.wait_for(
            self.llm.complete_grounded([
                {"role": "system", "content": L0_ORCHESTRATOR_SYSTEM},
                {"role": "user", "content": prompt},
            ], max_tokens=32768),
            timeout=300.0,
        )
        result = _extract_json(text)

        # Tag entities with sector key for traceability
        for entity in result.get("administering_entities", []):
            entity.setdefault("sector_key", sector["key"])

        return result

    # ── L2: Per-Entity Program Expansion ─────────────────────────────────

    async def _run_l2_entity_expansion(
        self,
        entities: list[dict],
        instruction_text: str,
        seed_index: dict[str, list[dict]],
    ) -> AsyncGenerator[dict, None]:
        """Expand each L1 entity to find its programs, yielding SSE events."""
        total = len(entities)

        for idx, entity in enumerate(entities, start=1):
            yield self._event("entity_expansion_start",
                              entity_id=entity.get("id", ""),
                              entity_name=entity.get("name", ""),
                              entity_n=idx,
                              entity_total=total)
            try:
                result = await asyncio.wait_for(
                    self._expand_entity(entity=entity, instruction_text=instruction_text),
                    timeout=180.0,
                )
                programs = result.get("programs", [])
                sources = result.get("sources", [])
                yield self._event("entity_expansion_complete",
                                  entity_id=entity.get("id", ""),
                                  entity_name=entity.get("name", ""),
                                  entity_n=idx,
                                  entity_total=total,
                                  programs_found=len(programs),
                                  sources_found=len(sources))
                yield {"event": "_l2_entity_result", "data": {
                    "entity_id": entity.get("id", ""),
                    "programs": programs,
                    "sources": sources,
                }}
            except Exception as exc:
                logger.warning("[graph v5] entity expansion failed for '%s': %s",
                               entity.get("name", ""), exc)
                yield self._event("entity_expansion_complete",
                                  entity_id=entity.get("id", ""),
                                  entity_name=entity.get("name", ""),
                                  entity_n=idx,
                                  entity_total=total,
                                  status="failed",
                                  error=str(exc),
                                  programs_found=0)
                yield {"event": "_l2_entity_result", "data": {
                    "entity_id": entity.get("id", ""),
                    "programs": [],
                    "sources": [],
                }}

    async def _expand_entity(
        self,
        entity: dict,
        instruction_text: str,
    ) -> dict:
        """Run one entity expansion call to find all programs for an entity."""
        entity_context = (
            f"## ENTITY EXPANSION CALL\n"
            f"## Target entity: {entity.get('name', 'Unknown')}\n"
            f"## Entity URL: {entity.get('url', 'unknown')}\n"
            f"## Entity type: {entity.get('entity_type', 'unknown')}\n"
            f"## Find ALL programs, portals, guidelines, and sub-entities for this entity only.\n"
            f"\n---\n\n"
        )
        prompt = entity_context + instruction_text
        text, _citations = await self.llm.complete_grounded([
            {"role": "system", "content": L0_ORCHESTRATOR_SYSTEM},
            {"role": "user", "content": prompt},
        ], max_tokens=16384)
        return _extract_json(text)

    # ── Utility: Coverage summary ─────────────────────────────────────────

    def _build_coverage_summary(
        self,
        sectors: list[dict],
        entities: list[dict],
        programs: list[dict],
    ) -> dict:
        """Build per-sector coverage counts."""
        summary: dict[str, dict] = {}
        for sector in sectors:
            key = sector["key"]
            sector_entities = [e for e in entities if e.get("sector_key") == key]
            sector_programs = [
                p for p in programs
                if any(
                    e.get("name", "") == p.get("administering_entity", "")
                    for e in sector_entities
                )
            ]
            summary[key] = {
                "label": sector["label"],
                "entities_found": len(sector_entities),
                "programs_found": len(sector_programs),
                "gaps": [],
            }
        return summary

    # ── Utility: SSE event builder ────────────────────────────────────────

    @staticmethod
    def _event(event_type: str, **data) -> dict:
        return {"event": event_type, "data": data}

    # ── Utility: Name normalization ───────────────────────────────────────

    @staticmethod
    def _normalize_name(name: str) -> str:
        return re.sub(r"[^a-z0-9]", "", name.lower())

    @staticmethod
    def _canonical_program_id(program_data: dict) -> str:
        name = re.sub(
            r"[^a-z0-9]+", "-", str(program_data.get("name", "")).lower()
        ).strip("-")
        entity = re.sub(
            r"[^a-z0-9]+", "-",
            str(program_data.get("administering_entity", "")).lower(),
        ).strip("-")
        jurisdiction = re.sub(
            r"[^a-z0-9]+", "-",
            str(program_data.get("jurisdiction", "")).lower(),
        ).strip("-")
        return (
            "-".join(part for part in [entity, name, jurisdiction] if part)[:255]
            or "unknown-program"
        )

    @classmethod
    def _dedupe_programs(cls, programs: list[dict]) -> list[dict]:
        """Deduplicate by canonical ID, keeping highest-confidence copy."""
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
                if re.sub(r"[^a-z0-9]", "", s.get("name", "").lower())
                in discovered_names
            )
            result[topic] = {
                "total": total,
                "matched": matched,
                "rate": round(matched / total, 3) if total else 0.0,
            }
        return result
