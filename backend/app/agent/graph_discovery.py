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
If no sector file is provided, the engine builds neutral runtime sectors so it
never falls back to a domain-specific config.

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
from app.agent.prompts import L0_ORCHESTRATOR_SYSTEM, SECTOR_SCOPE_HEADER, DISCOVERY_OUTPUT_SCHEMA, build_expansion_prompt, resolve_jurisdiction_code, JURISDICTION_CITATION_HINTS
from app.config import settings
from app.llm.base import LLMProvider
from app.llm.call_logger import log_heartbeat, log_prompt, log_stage
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


class EntityRegistry:
    """In-run registry that enforces stable, canonical entity IDs across all LLM calls.

    Problem: Different LLM calls for the same real-world entity independently invent IDs
    (e.g. L1 returns 'new-jersey-doi', L2 returns 'nj-dobi'). Sources persisted under
    the L2 ID become orphaned because the regulatory_bodies row uses the L1 ID.

    Solution: The first ID seen for a (jurisdiction_code, normalized_name) pair becomes
    the canonical ID for the entire run. All subsequent calls that return the same entity
    have their ID rewritten to the canonical one before DB insertion or queue enqueue.
    An alias map (any_seen_id → canonical_id) lets source regulatory_body references
    be resolved even when the LLM returns a body reference by a non-canonical ID.
    """

    def __init__(self) -> None:
        self._name_to_canonical: dict[str, str] = {}  # key → canonical_id
        self._alias_to_canonical: dict[str, str] = {}  # any_seen_id → canonical_id

    def _key(self, entity: dict) -> str:
        jcode = (entity.get("jurisdiction_code") or "XX").upper()
        name = entity.get("name", "").lower().strip()
        return f"{jcode}:{name}"

    def resolve(self, entity: dict) -> str:
        """Return the canonical ID for entity, registering it on first sight."""
        key = self._key(entity)
        proposed_id = (
            entity.get("id")
            or re.sub(r"[^a-z0-9]+", "-", entity.get("name", "unknown").lower()).strip("-")[:40]
        )
        if key not in self._name_to_canonical:
            self._name_to_canonical[key] = proposed_id
            # Seed the alias map so the proposed ID resolves to itself
            self._alias_to_canonical.setdefault(proposed_id, proposed_id)
        canonical = self._name_to_canonical[key]
        # Register any new alias (e.g. 'nj-dobi' when canonical is 'new-jersey-doi')
        if proposed_id != canonical:
            self._alias_to_canonical[proposed_id] = canonical
        return canonical

    def rewrite(self, entity: dict) -> dict:
        """Return a copy of entity with id set to the canonical ID."""
        return {**entity, "id": self.resolve(entity)}

    def resolve_id(self, entity_id: str) -> str:
        """Map any seen entity ID (including aliases) to the canonical ID."""
        return self._alias_to_canonical.get(entity_id, entity_id)

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

def _build_runtime_sectors(geo_scope: str) -> list[dict]:
    """Build neutral sectors when the user omits a sector file."""
    sectors: list[dict] = [
        {
            "key": "federal_national",
            "label": "Federal / National Authorities",
            "priority": 1,
            "search_hints": [
                "Focus on federal or national regulators, departments, commissions, bureaus, and oversight offices.",
            ],
            "completeness_requirements": [],
            "sector_prompt": "",
            "expected_entity_types": [],
        },
    ]

    if geo_scope in {"state", "municipal"}:
        sectors.append(
            {
                "key": "state_regional",
                "label": "State / Regional Authorities",
                "priority": 2,
                "search_hints": [
                    "Focus on state departments, state agencies, commissions, divisions, and regional oversight bodies.",
                ],
                "completeness_requirements": [],
                "sector_prompt": "",
                "expected_entity_types": [],
            }
        )

    if geo_scope == "municipal":
        sectors.append(
            {
                "key": "local_municipal",
                "label": "Municipal / County / Local Authorities",
                "priority": 3,
                "search_hints": [
                    "Focus on county, city, parish, borough, and other local authorities relevant to this domain.",
                ],
                "completeness_requirements": [],
                "sector_prompt": "",
                "expected_entity_types": [],
            }
        )

    sectors.append(
        {
            "key": "industry_bodies",
            "label": "Industry / Self-Regulatory / Trade Bodies",
            "priority": len(sectors) + 1,
            "search_hints": [
                "Focus on industry associations, self-regulatory bodies, accreditation groups, and standards organizations.",
            ],
            "completeness_requirements": [],
            "sector_prompt": "",
            "expected_entity_types": [],
        }
    )
    return sectors


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
        seed_anchors: list[dict] | None = None,
        constitution_text: str = "",
        instruction_text: str = "",
    ) -> AsyncGenerator[dict, None]:
        """Execute V6 RLM BFS discovery, yielding SSE events.

        sectors: list of sector dicts from uploaded sector file.
                 If empty or None, neutral runtime sectors are built from geo_scope.
        instruction_text: full text of the uploaded instruction file.
                          Each sector call receives this verbatim, prefixed by
                          a sector scope header. No domain content lives in code.
        """
        if not instruction_text.strip():
            raise ValueError("instruction_text is required for discovery runs")

        runtime_sectors = sectors if sectors else _build_runtime_sectors(geo_scope)
        if not sectors:
            logger.warning(
                "[graph_discovery] no sector file provided; using %d neutral runtime sectors for geo_scope=%s",
                len(runtime_sectors),
                geo_scope,
            )

        _sectors = sorted(
            runtime_sectors,
            key=lambda s: s.get("priority", 99),
        )
        _seed_index = seed_index or {}
        _seed_programs = seed_programs or []
        _seed_anchors = seed_anchors or []
        _instruction = instruction_text.strip()

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

        # In-run entity ID registry — ensures consistent canonical IDs across all LLM calls
        registry = EntityRegistry()

        all_entities: list[dict] = []
        all_sources: list[dict] = []
        all_programs: list[dict] = []
        source_id_counter = 1
        self._api_calls = 0

        # ── L1: Parallel Sector Discovery (seeds the queue) ──────────────
        l1_start_time = time.monotonic()
        log_stage("l1_sector_discovery", status="running", model=getattr(self.llm, "model", ""), manifest_id=self.manifest_id)
        async for event in self._run_l1_sectors(
            sectors=_sectors,
            instruction_text=_instruction,
            sector_concurrency=sector_concurrency,
            max_entities_per_sector=max_entities_per_sector,
            max_api_calls=max_api_calls,
        ):
            if event.get("event") == "_l1_sector_result":
                # Internal event — harvest entities, sources, and programs
                data = event.get("data", {})
                sector_entities = data.get("administering_entities", [])
                sector_sources = data.get("sources", [])
                sector_programs = data.get("programs", [])
                sector_key = data.get("sector_key", "")
                for src in sector_sources:
                    src.setdefault("id", f"src-{source_id_counter:03d}")
                    source_id_counter += 1
                all_entities.extend(sector_entities)
                all_sources.extend(sector_sources)

                # Collect L1 programs with provenance
                for prog in sector_programs:
                    prog.setdefault("provenance_links", {})
                    prog["provenance_links"]["discovery_level"] = "L1"
                    prog["provenance_links"]["discovered_from"] = f"sector:{sector_key}"
                    all_programs.append(prog)

                # Seed the queue with discovered entities for L2+ expansion
                for entity in sector_entities:
                    entity = registry.rewrite(entity)
                    entity_id = entity["id"]
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

        # Persist L1 entities as RegulatoryBody records (dedup by canonical ID via registry)
        seen_entity_ids: set[str] = set()
        for entity in all_entities:
            eid = registry.resolve(entity)
            if eid in seen_entity_ids:
                continue
            seen_entity_ids.add(eid)
            self.db.add(RegulatoryBody(
                id=eid,
                manifest_id=self.manifest_id,
                name=entity.get("name", "Unknown Entity"),
                jurisdiction=_safe_enum(Jurisdiction, entity.get("jurisdiction")),
                jurisdiction_code=entity.get("jurisdiction_code") or None,
                authority_type=_safe_enum(AuthorityType, entity.get("authority_type") or entity.get("entity_type")),
                url=entity.get("url", ""),
                governs=entity.get("governs", []),
            ))

        seen_source_ids: set[str] = set()
        for src_data in all_sources:
            sid = src_data["id"]
            if sid in seen_source_ids:
                logger.debug("[graph v6] skipping duplicate source %s", sid)
                continue
            seen_source_ids.add(sid)
            self.db.add(Source(
                id=sid,
                manifest_id=self.manifest_id,
                name=src_data.get("name", "Unknown Source"),
                regulatory_body_id=registry.resolve_id(src_data.get("regulatory_body", "")),
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
            manifest_id=self.manifest_id,
        )
        yield self._event("l1_assembly_complete",
                          total_entities=len(all_entities),
                          total_sources=len(all_sources),
                          sector_count=len(_sectors),
                          queue_stats=queue.stats())

        # Inject seed anchors that weren't already queued from L1.
        # This guarantees all known entities enter the BFS regardless of L1 coverage.
        for anchor in (_seed_anchors or []):
            anchor_id = (
                anchor.get("id")
                or self._normalize_name(anchor.get("name", ""))[:40]
            )
            if not anchor_id:
                continue
            queue.enqueue(
                target_type="entity",
                target_id=anchor_id,
                priority=1,
                discovered_from="seed_anchor",
                depth=1,
                metadata=anchor,
            )
        anchor_count = len(_seed_anchors or [])
        if anchor_count:
            logger.info(
                "[graph v6] seed anchors injected — count=%d queue_size=%d",
                anchor_count, queue.size(),
            )

        logger.info(
            "[graph v6] L1 done — k_depth=%d queue_empty=%s queue_size=%d entities=%d api_calls=%d queue_stats=%s",
            k_depth, queue.is_empty(), queue.size(), len(all_entities), self._api_calls, queue.stats(),
        )

        if k_depth < 2 or queue.is_empty():
            # k_depth=1 or no entities discovered — skip expansion
            logger.info("[graph v6] skipping L2 — k_depth=%d queue_empty=%s programs_from_l1=%d",
                        k_depth, queue.is_empty(), len(all_programs))

            # Persist L1-discovered programs
            deduped = self._dedupe_programs(all_programs)
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

            manifest.status = ManifestStatus.approved
            coverage_summary = self._build_coverage_summary(_sectors, all_entities, deduped)
            manifest.coverage_summary = coverage_summary
            await self.db.commit()
            yield self._event("complete",
                              manifest_id=self.manifest_id,
                              total_entities=len(all_entities),
                              total_programs=len(deduped),
                              api_calls=self._api_calls,
                              queue_stats=queue.stats(),
                              coverage_summary=coverage_summary)
            return

        # ── L2+: Queue-Driven BFS Expansion ──────────────────────────────
        log_stage("l2_queue_expansion", status="running", model=getattr(self.llm, "model", ""), manifest_id=self.manifest_id)
        l2_start_time = time.monotonic()
        entity_n = 0
        entity_total = queue.size()
        l2_seen_source_ids: set[str] = set()

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
            node = item.metadata
            node_id = item.target_id
            node_name = node.get("name", node_id)
            node_type = item.target_type  # "entity" | "source_title" | "source_chapter" | "source_section"

            yield self._event("entity_expansion_start",
                              entity_id=node_id,
                              entity_name=node_name,
                              entity_n=entity_n,
                              entity_total=entity_total,
                              depth=item.depth,
                              node_type=node_type,
                              queue_pending=queue.size(),
                              citation_format=node.get("citation_format_hint", ""),
                              jurisdiction_code=node.get("jurisdiction_code", ""),
                              )

            try:
                result = await asyncio.wait_for(
                    self._expand_node(node=node, node_type=node_type, depth=item.depth),
                    timeout=180.0,
                )
                self._api_calls += 1

                programs = result.get("programs", [])
                sources = result.get("sources", [])
                sub_entities = result.get("administering_entities", [])

                # Persist sources from this expansion.
                # Prefix source ID with node_id to prevent PK collisions when
                # multiple nodes return sources with the same LLM-generated ID.
                enqueued_source_children = 0
                for src in sources:
                    src.setdefault("id", f"src-{source_id_counter:03d}")
                    source_id_counter += 1
                    raw_sid = src["id"]
                    sid = f"{node_id}__{raw_sid}"
                    src["id"] = sid
                    if sid in l2_seen_source_ids:
                        logger.debug("[graph v6] L2 skipping duplicate source %s", sid)
                        continue
                    l2_seen_source_ids.add(sid)
                    all_sources.append(src)
                    self.db.add(Source(
                        id=src["id"],
                        manifest_id=self.manifest_id,
                        name=src.get("name", "Unknown Source"),
                        regulatory_body_id=registry.resolve_id(src.get("regulatory_body", "")),
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

                    # ALGO-012: Enqueue source nodes for deeper BFS traversal based on depth_hint.
                    # depth_hint returned by the LLM classifies each source's depth level.
                    # 'title' and 'chapter' nodes become queue items for further expansion.
                    # 'section' nodes are queued only if we have depth remaining.
                    # 'leaf' nodes are persisted only — no further expansion.
                    depth_hint = (src.get("depth_hint") or "").strip().lower()
                    child_node_type = {
                        "title": "source_title",
                        "chapter": "source_chapter",
                        "section": "source_section",
                    }.get(depth_hint)

                    if child_node_type and item.depth + 1 <= queue.max_depth:
                        # Build a metadata dict for the source node so the next
                        # expansion call has name, url, citation, jurisdiction context
                        src_meta = {
                            "name": src.get("name", ""),
                            "url": src.get("url", ""),
                            "citation": src.get("citation") or src.get("name", ""),
                            "jurisdiction_code": src.get("jurisdiction_code") or node.get("jurisdiction_code", ""),
                            "citation_format_hint": src.get("citation_format_hint") or node.get("citation_format_hint", ""),
                            "regulatory_body": src.get("regulatory_body", node_id),
                            "sector_key": node.get("sector_key", ""),
                            "depth_hint": depth_hint,
                        }
                        added_src = queue.enqueue(
                            target_type=child_node_type,
                            target_id=sid,
                            priority=item.priority + 1,
                            discovered_from=f"{node_type}:{node_id}",
                            depth=item.depth + 1,
                            metadata=src_meta,
                        )
                        if added_src:
                            enqueued_source_children += 1

                # Collect programs with provenance
                for prog in programs:
                    prog.setdefault("provenance_links", {})
                    prog["provenance_links"]["discovery_level"] = f"L{item.depth + 1}"
                    prog["provenance_links"]["discovered_from"] = item.discovered_from
                    all_programs.append(prog)

                # Enqueue sub-entities for deeper expansion (RLM recursion)
                enqueued_children = enqueued_source_children
                for sub_entity in sub_entities:
                    sub_entity = registry.rewrite(sub_entity)
                    sub_id = sub_entity["id"]
                    sub_entity.setdefault("sector_key", node.get("sector_key", ""))
                    added = queue.enqueue(
                        target_type="entity",
                        target_id=sub_id,
                        priority=sub_entity.get("priority", item.priority + 1),
                        discovered_from=f"entity:{node_id}",
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
                            jurisdiction_code=sub_entity.get("jurisdiction_code") or None,
                            authority_type=_safe_enum(AuthorityType, sub_entity.get("authority_type") or sub_entity.get("entity_type")),
                            url=sub_entity.get("url", ""),
                            governs=sub_entity.get("governs", []),
                        ))

                # Update total for SSE progress reporting
                entity_total = entity_n + queue.size()

                yield self._event("entity_expansion_complete",
                                  entity_id=node_id,
                                  entity_name=node_name,
                                  entity_n=entity_n,
                                  entity_total=entity_total,
                                  depth=item.depth,
                                  node_type=node_type,
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
                        manifest_id=self.manifest_id,
                    )

            except Exception as exc:
                self._api_calls += 1
                logger.warning("[graph v6] node expansion failed for '%s' (type=%s): %s",
                               node_name, node_type, exc)
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

        jurisdiction_counts = Counter(
            p.get("geo_scope", "unknown") for p in deduped
        )
        type_counts = Counter(
            p.get("status", "unknown") for p in deduped
        )

        assessment = CoverageAssessment(
            manifest_id=self.manifest_id,
            total_sources=len(all_sources),
            by_jurisdiction=dict(jurisdiction_counts),
            by_type=dict(type_counts),
            completeness_score=min(seed_recovery_rate + 0.3, 1.0),
        )
        self.db.add(assessment)

        coverage_summary = self._build_coverage_summary(_sectors, all_entities, deduped)
        manifest.status = ManifestStatus.approved
        manifest.completeness_score = assessment.completeness_score
        manifest.coverage_summary = coverage_summary
        await self.db.commit()

        log_stage(
            "l2_queue_expansion", status="complete",
            model=getattr(self.llm, "model", ""),
            sources=len(all_sources), programs=len(deduped),
            manifest_id=self.manifest_id,
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
                    error_desc = str(result) or f"{type(result).__name__} (no message)"
                    logger.warning("[graph v6] sector '%s' failed: %s", sector["key"], error_desc)
                    yield self._event("sector_complete",
                                      sector_key=sector["key"],
                                      sector_label=sector["label"],
                                      status="failed",
                                      error=error_desc,
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

                    logger.info(
                        "[graph v6] sector '%s' OK — entities=%d programs=%d sources=%d",
                        sector["key"], len(entities), len(result.get("programs", [])), len(sources),
                    )
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
                        "programs": result.get("programs", []),
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
            text = await asyncio.wait_for(
                self.llm.complete([
                    {"role": "system", "content": L0_ORCHESTRATOR_SYSTEM},
                    {"role": "user", "content": prompt},
                ], max_tokens=32768, response_mime_type="application/json"),
                timeout=900.0,
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
        else:
            logger.info(
                "[graph v6] sector '%s' parsed — keys=%s entities=%d programs=%d text_len=%d",
                sector["key"],
                list(result.keys())[:10],
                len(result.get("administering_entities", [])),
                len(result.get("programs", [])),
                len(text),
            )

        # Tag entities with sector key for traceability
        for entity in result.get("administering_entities", []):
            entity.setdefault("sector_key", sector["key"])

        return result

    # ── L2+: Node Expansion (entity and source nodes) ────────────────────

    async def _expand_node(
        self,
        node: dict,
        node_type: str = "entity",
        depth: int = 1,
    ) -> dict:
        """Run one node expansion call using a node-type-aware single-question prompt.

        ALGO-012: Each call asks exactly ONE bounded question scoped to the node type.
        The framework drives traversal; the LLM returns only direct children.
        No internal LLM recursion.

        node_type values:
          "entity"         — L1 entity; ask for top-level titles
          "source_title"   — statute/code title; ask for chapters within
          "source_chapter" — chapter/part; ask for sections within
          "source_section" — section; ask for sub-sections (leaf level)

        Template is always authoritative — stored expansion_prompt from L1 is NOT used.
        """
        expansion_question = build_expansion_prompt(node, node_type=node_type)

        # Resolve jurisdiction_code and emit WARNING if L1 dropped the field
        jcode, jcode_source = resolve_jurisdiction_code(node)
        if jcode_source == "name":
            logger.warning(
                "[graph v6] jurisdiction_code missing from L1 for '%s' — extracted '%s' from name",
                node.get("name"), jcode,
            )
        elif jcode_source == "fallback":
            logger.warning(
                "[graph v6] jurisdiction_code UNRESOLVABLE for '%s' (node_type=%s) — generic citation used",
                node.get("name"), node_type,
            )

        citation_hint = (node.get("citation_format_hint") or "").strip()
        if not citation_hint and jcode:
            citation_hint = JURISDICTION_CITATION_HINTS.get(jcode, "standard")
        if not citation_hint:
            citation_hint = "standard"

        # For source nodes, show the citation being expanded in the header
        target_label = node.get("citation") or node.get("name", "Unknown")

        prompt = (
            f"## NODE EXPANSION — DEPTH L{depth + 1}  [{node_type}]\n"
            f"## Target: {node.get('name', 'Unknown')} ({node_type})\n"
            f"## Citation: {target_label}\n"
            f"## URL: {node.get('url', 'unknown')}\n"
            f"## Jurisdiction: {jcode or node.get('jurisdiction', 'unknown')}\n"
            f"## Citation format: {citation_hint}\n"
            f"\n---\n\n"
            f"{expansion_question}\n\n"
            f"{DISCOVERY_OUTPUT_SCHEMA}"
        )
        log_prompt(
            entity_id=node.get("id", "?"),
            entity_name=node.get("name", "?"),
            depth=depth,
            prompt_text=prompt,
            authority_type=node.get("authority_type", node_type),
            jurisdiction_code=jcode or "",
            manifest_id=self.manifest_id,
        )
        logger.info(
            "[graph v6][expansion_prompt] node=%s node_type=%s depth=%d chars=%d prompt_preview=%r",
            node.get("id") or node.get("citation", "?"), node_type, depth, len(prompt), prompt[:200],
        )
        text = await self.llm.complete([
            {"role": "system", "content": L0_ORCHESTRATOR_SYSTEM},
            {"role": "user", "content": prompt},
        ], max_tokens=16384, response_mime_type="application/json")
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
