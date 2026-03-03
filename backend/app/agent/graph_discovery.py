"""Hierarchical Graph Discovery Engine (V6) — RLM Queue-Driven BFS.

V6 architecture (ported from prepop1 recursive BFS pattern):
- L1: 6 (or N) parallel sector calls seed the DiscoveryQueue with entities at depth=0.
  Each call receives the full instruction_text prefixed with a sector scope header.
  The [INJECT SECTOR PROMPT HERE] placeholder is replaced with sector_prompt from sector file.
  No domain expertise lives in engine code — all methodology comes from the uploaded prompt.
- L2+: Queue-driven BFS loop processes entities at increasing depth.
  Each entity expansion call finds programs, sources, and sub-entities.
  Newly discovered entities are enqueued at depth+1 if within max_depth.
- Safety caps: max_api_calls, max_discovery_depth, max_entities_per_sector enforce limits.

Sector list is supplied at runtime from the uploaded sector JSON file.
Falls back to DEFAULT_SECTORS (from prompts.py) if no sector file is provided.

k_depth semantics (mapped to queue max_depth):
  k_depth=1 → L1 entity discovery only (queue max_depth=0, no expansion)
  k_depth=2 → L1 entities + L2 program expansion (queue max_depth=1)
  k_depth=3 → L1 + L2 + L3 deeper expansion (queue max_depth=2)

SSE events (unchanged from V5 for frontend compatibility):
  sector_start / sector_complete       — one pair per L1 sector
  l1_assembly_complete                 — after all sectors merged and persisted
  entity_expansion_start / entity_expansion_complete — per queue item (depth >= 1)
  complete                             — final with coverage_summary + seed metrics
"""

import asyncio
import json
import logging
import re
import time
import urllib.request
from collections import Counter
from collections.abc import AsyncGenerator

from sqlalchemy.ext.asyncio import AsyncSession

from app.agent.discovery import _extract_json, _safe_enum
from app.agent.discovery_queue import DiscoveryQueue
from app.agent.prompts import (
    DEFAULT_SECTORS,
    L0_ORCHESTRATOR_SYSTEM,
    SECTOR_SCOPE_HEADER,
)
from app.config import settings
from app.llm.base import LLMProvider
from app.llm.call_logger import log_heartbeat, log_stage
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

# Placeholder token in instruction files that gets replaced with sector-specific content
_SECTOR_PROMPT_PLACEHOLDER = "[INJECT SECTOR PROMPT HERE]"

# region agent log
_DEBUG_ENDPOINT = "http://127.0.0.1:7884/ingest/644327d9-ea5d-464a-b97e-a7bf1c844fd6"
_DEBUG_SESSION = "cb8819"


def _debug_log(*, run_id: str, hypothesis_id: str, location: str, message: str, data: dict) -> None:
    payload = {
        "sessionId": _DEBUG_SESSION,
        "runId": run_id,
        "hypothesisId": hypothesis_id,
        "location": location,
        "message": message,
        "data": data,
        "timestamp": int(time.time() * 1000),
    }
    try:
        body = json.dumps(payload, ensure_ascii=True).encode("utf-8")
        req = urllib.request.Request(
            _DEBUG_ENDPOINT,
            data=body,
            headers={
                "Content-Type": "application/json",
                "X-Debug-Session-Id": _DEBUG_SESSION,
            },
        )
        urllib.request.urlopen(req, timeout=0.5)
    except Exception:
        # Never break the pipeline because of debug logging
        return
# endregion

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


def _build_completeness_block(sector: dict) -> str:
    """Build the sector-specific completeness requirements block for the header.

    Returns an empty string when no requirements are defined so the header
    renders cleanly without a blank section.
    """
    reqs = sector.get("completeness_requirements", [])
    if not reqs:
        return ""
    lines = "\n".join(f"  - {r}" for r in reqs)
    return f"\n## Completeness requirements for YOUR sector only:\n{lines}\n"


def _inject_sector_prompt(instruction_text: str, sector: dict) -> str:
    """Replace the [INJECT SECTOR PROMPT HERE] placeholder with sector-specific content.

    If no sector_prompt is defined, the placeholder is removed cleanly.
    """
    sector_prompt = sector.get("sector_prompt", "").strip()
    if sector_prompt:
        return instruction_text.replace(_SECTOR_PROMPT_PLACEHOLDER, sector_prompt)
    return instruction_text.replace(_SECTOR_PROMPT_PLACEHOLDER, "")


class DiscoveryGraph:
    """V6 RLM queue-driven BFS discovery engine."""

    def __init__(self, llm: LLMProvider, db: AsyncSession, manifest_id: str):
        self.llm = llm
        self.db = db
        self.manifest_id = manifest_id
        self._api_calls: int = 0

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
        """Execute V6 RLM BFS discovery, yielding SSE events.

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

        # Safety caps from config
        max_api_calls = settings.max_api_calls
        max_entities_per_sector = settings.max_entities_per_sector

        # Queue max_depth: k_depth=1 means L1 only (no queue expansion),
        # k_depth=2 means 1 expansion level, etc.
        queue_max_depth = min(k_depth - 1, settings.max_discovery_depth)

        # Initialize the discovery queue
        queue = DiscoveryQueue(max_depth=queue_max_depth)

        all_entities: list[dict] = []
        all_sources: list[dict] = []
        all_programs: list[dict] = []
        source_id_counter = 1
        self._api_calls = 0

        # ── L1: Parallel Sector Discovery (seeds the queue) ──────────────
        l1_start_time = time.monotonic()
        log_stage("l1_sector_discovery", status="running", model=getattr(self.llm, "model", ""))
        async for event in self._run_l1_sectors(
            sectors=_sectors,
            instruction_text=_instruction,
            sector_concurrency=sector_concurrency,
            max_entities_per_sector=max_entities_per_sector,
            max_api_calls=max_api_calls,
        ):
            if event.get("event") == "_l1_sector_result":
                # Internal event — harvest entities and sources
                data = event.get("data", {})
                sector_entities = data.get("administering_entities", [])
                sector_sources = data.get("sources", [])
                sector_key = data.get("sector_key", "")
                for src in sector_sources:
                    src.setdefault("id", f"src-{source_id_counter:03d}")
                    source_id_counter += 1
                all_entities.extend(sector_entities)
                all_sources.extend(sector_sources)

                # Seed the queue with discovered entities for L2+ expansion
                for entity in sector_entities:
                    entity_id = entity.get("id", self._normalize_name(entity.get("name", ""))[:40])
                    queue.enqueue(
                        target_type="entity",
                        target_id=entity_id,
                        priority=entity.get("priority", 10),
                        discovered_from=f"sector:{sector_key}",
                        depth=1,
                        metadata=entity,
                    )
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

        log_stage(
            "l1_sector_discovery", status="complete",
            model=getattr(self.llm, "model", ""),
            sources=len(all_sources), programs=0,
        )
        yield self._event("l1_assembly_complete",
                          total_entities=len(all_entities),
                          total_sources=len(all_sources),
                          sector_count=len(_sectors),
                          queue_stats=queue.stats())

        if k_depth < 2 or queue.is_empty():
            # k_depth=1 or no entities discovered — skip expansion
            manifest.status = ManifestStatus.pending_review
            await self.db.commit()
            yield self._event("complete",
                              manifest_id=self.manifest_id,
                              total_entities=len(all_entities),
                              total_programs=0,
                              api_calls=self._api_calls,
                              queue_stats=queue.stats(),
                              coverage_summary=self._build_coverage_summary(_sectors, all_entities, []))
            return

        # ── L2+: Queue-Driven BFS Expansion ──────────────────────────────
        log_stage("l2_queue_expansion", status="running", model=getattr(self.llm, "model", ""))
        l2_start_time = time.monotonic()
        entity_n = 0
        entity_total = queue.size()

        while not queue.is_empty():
            # Safety cap: stop if we've hit the API call limit
            if self._api_calls >= max_api_calls:
                logger.warning(
                    "[graph v6] API call limit reached (%d/%d) — stopping queue expansion",
                    self._api_calls, max_api_calls,
                )
                break

            item = queue.pop()
            if item is None:
                break

            entity_n += 1
            entity = item.metadata
            entity_id = item.target_id
            entity_name = entity.get("name", entity_id)

            yield self._event("entity_expansion_start",
                              entity_id=entity_id,
                              entity_name=entity_name,
                              entity_n=entity_n,
                              entity_total=entity_total,
                              depth=item.depth,
                              queue_pending=queue.size())

            try:
                result = await asyncio.wait_for(
                    self._expand_entity(entity=entity, instruction_text=_instruction),
                    timeout=180.0,
                )
                self._api_calls += 1

                programs = result.get("programs", [])
                sources = result.get("sources", [])
                sub_entities = result.get("administering_entities", [])

                # Persist sources from this expansion
                for src in sources:
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

                # Collect programs with provenance
                for prog in programs:
                    prog.setdefault("provenance_links", {})
                    prog["provenance_links"]["discovery_level"] = f"L{item.depth + 1}"
                    prog["provenance_links"]["discovered_from"] = item.discovered_from
                    all_programs.append(prog)

                # Enqueue sub-entities for deeper expansion (RLM recursion)
                enqueued_children = 0
                for sub_entity in sub_entities:
                    sub_id = sub_entity.get(
                        "id",
                        self._normalize_name(sub_entity.get("name", ""))[:40],
                    )
                    sub_entity.setdefault("sector_key", entity.get("sector_key", ""))
                    added = queue.enqueue(
                        target_type="entity",
                        target_id=sub_id,
                        priority=sub_entity.get("priority", item.priority + 1),
                        discovered_from=f"entity:{entity_id}",
                        depth=item.depth + 1,
                        metadata=sub_entity,
                    )
                    if added:
                        enqueued_children += 1
                        all_entities.append(sub_entity)
                        # Persist sub-entity
                        self.db.add(RegulatoryBody(
                            id=sub_id,
                            manifest_id=self.manifest_id,
                            name=sub_entity.get("name", "Unknown Entity"),
                            jurisdiction=_safe_enum(Jurisdiction, sub_entity.get("jurisdiction")),
                            authority_type=_safe_enum(AuthorityType, sub_entity.get("entity_type")),
                            url=sub_entity.get("url", ""),
                            governs=sub_entity.get("governs", []),
                        ))

                # Update total for SSE progress reporting
                entity_total = entity_n + queue.size()

                yield self._event("entity_expansion_complete",
                                  entity_id=entity_id,
                                  entity_name=entity_name,
                                  entity_n=entity_n,
                                  entity_total=entity_total,
                                  depth=item.depth,
                                  programs_found=len(programs),
                                  sources_found=len(sources),
                                  children_enqueued=enqueued_children,
                                  queue_pending=queue.size())

                # Heartbeat every 30s during long expansion phases
                elapsed = time.monotonic() - l2_start_time
                if elapsed > 30 and entity_n % 3 == 0:
                    log_heartbeat(
                        stage="l2_queue_expansion",
                        batch=f"{entity_n}/{entity_total}",
                        items_so_far=len(all_programs),
                        elapsed_s=elapsed,
                    )

            except Exception as exc:
                self._api_calls += 1
                logger.warning("[graph v6] entity expansion failed for '%s': %s",
                               entity_name, exc)
                yield self._event("entity_expansion_complete",
                                  entity_id=entity_id,
                                  entity_name=entity_name,
                                  entity_n=entity_n,
                                  entity_total=entity_total,
                                  depth=item.depth,
                                  status="failed",
                                  error=str(exc),
                                  programs_found=0)

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

        log_stage(
            "l2_queue_expansion", status="complete",
            model=getattr(self.llm, "model", ""),
            sources=len(all_sources), programs=len(deduped),
        )
        yield self._event("complete",
                          manifest_id=self.manifest_id,
                          total_entities=len(all_entities),
                          total_sources=len(all_sources),
                          total_programs=len(deduped),
                          api_calls=self._api_calls,
                          coverage_score=assessment.completeness_score,
                          coverage_summary=coverage_summary,
                          queue_stats=queue.stats(),
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
        max_entities_per_sector: int = 50,
        max_api_calls: int = 200,
    ) -> AsyncGenerator[dict, None]:
        """Run all sector calls, yielding SSE events and internal result events."""
        total = len(sectors)

        # Run in batches of sector_concurrency to respect API rate limits
        for batch_start in range(0, total, sector_concurrency):
            # Safety cap check before launching batch
            if self._api_calls >= max_api_calls:
                logger.warning(
                    "[graph v6] API call limit reached (%d/%d) — skipping remaining sectors",
                    self._api_calls, max_api_calls,
                )
                break

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
            self._api_calls += len(batch)

            for sector, result in zip(batch, results):
                if isinstance(result, Exception):
                    # region agent log
                    _debug_log(
                        run_id="v6",
                        hypothesis_id="H1",
                        location="graph_discovery.py:_run_l1_sectors",
                        message="sector_task_exception",
                        data={
                            "sector_key": sector.get("key", ""),
                            "sector_label": sector.get("label", ""),
                            "exc_type": type(result).__name__,
                            "exc_message": str(result),
                        },
                    )
                    # endregion
                    logger.warning("[graph v6] sector '%s' failed: %s", sector["key"], result)
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

                    # Enforce per-sector entity cap
                    if len(entities) > max_entities_per_sector:
                        logger.warning(
                            "[graph v6] sector '%s' returned %d entities, capping at %d",
                            sector["key"], len(entities), max_entities_per_sector,
                        )
                        entities = entities[:max_entities_per_sector]

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
            completeness_block=_build_completeness_block(sector),
        )

        # Inject sector-specific prompt content into instruction text
        sector_instruction = _inject_sector_prompt(instruction_text, sector)

        prompt = sector_header + sector_instruction

        # region agent log
        _debug_log(
            run_id="v6",
            hypothesis_id="H3",
            location="graph_discovery.py:_discover_sector",
            message="sector_prompt_ready",
            data={
                "sector_key": sector.get("key", ""),
                "sector_label": sector.get("label", ""),
                "prompt_chars": len(prompt),
                "header_chars": len(sector_header),
                "instruction_chars": len(sector_instruction),
                "search_hints_count": len(search_hints),
                "completeness_count": len(sector.get("completeness_requirements", [])),
                "has_sector_prompt": bool(sector.get("sector_prompt")),
            },
        )
        # endregion

        logger.debug(
            "[graph v6] sector '%s' prompt assembled — prompt_chars=%d instruction_chars=%d header_chars=%d",
            sector["key"], len(prompt), len(sector_instruction), len(sector_header),
        )

        try:
            text, _citations = await asyncio.wait_for(
                self.llm.complete_grounded([
                    {"role": "system", "content": L0_ORCHESTRATOR_SYSTEM},
                    {"role": "user", "content": prompt},
                ], max_tokens=16384),
                timeout=300.0,
            )
        except Exception as exc:
            # region agent log
            _debug_log(
                run_id="v6",
                hypothesis_id="H1",
                location="graph_discovery.py:_discover_sector",
                message="sector_call_error",
                data={
                    "sector_key": sector.get("key", ""),
                    "sector_label": sector.get("label", ""),
                    "exc_type": type(exc).__name__,
                    "exc_message": str(exc),
                },
            )
            # endregion
            raise

        # region agent log
        _debug_log(
            run_id="v6",
            hypothesis_id="H2",
            location="graph_discovery.py:_discover_sector",
            message="sector_call_response",
            data={
                "sector_key": sector.get("key", ""),
                "text_len": len(text),
                "tail": text[-200:] if len(text) > 200 else text,
            },
        )
        # endregion

        logger.debug(
            "[graph v6] sector '%s' raw response — text_len=%d head=%r tail=%r",
            sector["key"], len(text), text[:500], text[-200:] if len(text) > 200 else "",
        )

        result = _extract_json(text)

        # region agent log
        _debug_log(
            run_id="v6",
            hypothesis_id="H2",
            location="graph_discovery.py:_discover_sector",
            message="sector_parse_result",
            data={
                "sector_key": sector.get("key", ""),
                "entities_found": len(result.get("administering_entities", [])),
                "programs_found": len(result.get("programs", [])),
                "sources_found": len(result.get("sources", [])),
                "empty_result": not bool(result),
            },
        )
        # endregion

        if not result:
            logger.warning(
                "[graph v6] sector '%s' JSON parse produced empty result — text_len=%d tail=%r",
                sector["key"], len(text), text[-300:] if len(text) > 300 else text,
            )

        # Tag entities with sector key for traceability
        for entity in result.get("administering_entities", []):
            entity.setdefault("sector_key", sector["key"])

        return result

    # ── L2+: Entity Expansion (called from queue loop) ───────────────────

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
