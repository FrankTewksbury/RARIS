import json
import logging
import re
from collections import Counter
from collections.abc import AsyncGenerator
from pathlib import Path
from time import perf_counter
from urllib.error import URLError
from urllib.request import Request, urlopen

from sqlalchemy.ext.asyncio import AsyncSession

from app.agent.prompts import (
    COVERAGE_ASSESSOR_PROMPT,
    GUIDANCE_CONTEXT_BLOCK,
    LANDSCAPE_MAPPER_PROMPT,
    PROGRAM_ENUMERATOR_PROMPT,
    RELATIONSHIP_MAPPER_PROMPT,
    SEED_ENUMERATOR_PROMPT,
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
    Program,
    ProgramGeoScope,
    ProgramStatus,
    RegulatoryBody,
    Source,
    SourceFormat,
    SourceType,
)

logger = logging.getLogger(__name__)

# Max bodies per source-hunter batch to stay within output token limits
SOURCE_HUNTER_BATCH_SIZE = 10
PROGRAM_ENUMERATOR_BATCH_SIZE = 20
SEED_BATCH_SIZE = 100
SEED_SOURCE_CONTEXT_SIZE = 20
MAX_SEED_HINT_BUDGET = 8_000  # chars reserved for seed hints within 24k guidance ceiling
DEBUG_LOG_ENDPOINTS = (
    "http://127.0.0.1:7884/ingest/644327d9-ea5d-464a-b97e-a7bf1c844fd6",
    "http://host.docker.internal:7884/ingest/644327d9-ea5d-464a-b97e-a7bf1c844fd6",
)
DEBUG_LOG_FILE = Path("/workspace/.cursor/debug-2fe1ec.log")


def _debug_log(message: str, data: dict, hypothesis_id: str, run_id: str = "initial") -> None:
    payload = {
        "sessionId": "2fe1ec",
        "runId": run_id,
        "hypothesisId": hypothesis_id,
        "location": "backend/app/agent/discovery.py",
        "message": message,
        "data": data,
        "timestamp": int(__import__("time").time() * 1000),
    }
    try:
        DEBUG_LOG_FILE.parent.mkdir(parents=True, exist_ok=True)
        with DEBUG_LOG_FILE.open("a", encoding="utf-8") as file:
            file.write(json.dumps(payload, ensure_ascii=True) + "\n")
    except Exception:
        logger.debug("Debug log file append failed", exc_info=True)
    body = json.dumps(payload, ensure_ascii=True).encode("utf-8")
    for endpoint in DEBUG_LOG_ENDPOINTS:
        try:
            request = Request(
                endpoint,
                data=body,
                headers={
                    "Content-Type": "application/json",
                    "X-Debug-Session-Id": "2fe1ec",
                },
                method="POST",
            )
            urlopen(request, timeout=1).read()
            return
        except URLError:
            continue
        except Exception:
            continue
    logger.debug("Debug log POST failed for all endpoints")


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
    """Orchestrates the discovery pipeline."""

    def __init__(self, llm: LLMProvider, db: AsyncSession, manifest_id: str):
        self.llm = llm
        self.db = db
        self.manifest_id = manifest_id

    async def run(
        self,
        domain_description: str,
        k_depth: int = 2,
        geo_scope: str = "state",
        target_segments: list[str] | None = None,
        seed_anchors: list[dict] | None = None,
        seed_programs: list[dict] | None = None,
        seed_metrics: dict | None = None,
        constitution_text: str = "",
        instruction_text: str = "",
    ) -> AsyncGenerator[dict, None]:
        """Execute the full discovery pipeline, yielding SSE events."""
        anchors = seed_anchors or []
        seeded_program_candidates = seed_programs or []
        metrics = seed_metrics or {}
        guidance_block = self._build_guidance_block(
            constitution_text,
            instruction_text,
            k_depth=k_depth,
            geo_scope=geo_scope,
            target_segments=target_segments or [],
            seed_anchors=anchors,
            seed_programs=seeded_program_candidates,
            seed_metrics=metrics,
        )

        # Step 0: Seeding context
        if anchors or seeded_program_candidates:
            yield {"event": "step", "data": {
                "step": "seed_ingestion", "status": "complete",
                "message": "Seed files parsed and queued.",
                "seed_anchor_count": len(anchors),
                "seed_program_count": len(seeded_program_candidates),
                "seed_metrics": metrics,
            }}

        # Step 1: Landscape Mapper
        yield {"event": "step", "data": {
            "step": "landscape_mapper", "status": "running",
            "message": "Identifying regulatory bodies and jurisdiction hierarchy...",
        }}

        landscape = await self._landscape_mapper(domain_description, guidance_block=guidance_block)
        bodies = landscape.get("regulatory_bodies", [])
        # region agent log
        jurisdiction_counts = Counter((b.get("jurisdiction") or "").strip() for b in bodies)
        _debug_log(
            "Landscape mapper output distribution",
            {
                "total_bodies": len(bodies),
                "jurisdiction_counts": dict(jurisdiction_counts),
                "sample_body_ids": [b.get("id") for b in bodies[:20]],
            },
            "H6",
        )
        # endregion

        yield {"event": "step", "data": {
            "step": "landscape_mapper", "status": "complete",
            "message": f"Found {len(bodies)} regulatory bodies.",
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
        for anchor in anchors:
            anchor_name = str(
                anchor.get("name")
                or anchor.get("title")
                or anchor.get("entity")
                or anchor.get("url")
                or "Seed Anchor"
            )
            anchor_url = str(anchor.get("url") or "")
            if not anchor_url:
                continue
            anchor_id = f"seed-anchor-{len(bodies) + 1:03d}"
            bodies.append({
                "id": anchor_id,
                "name": anchor_name,
                "jurisdiction": str(anchor.get("jurisdiction") or "state"),
                "authority_type": "industry_body",
                "url": anchor_url,
                "governs": [],
            })
            self.db.add(RegulatoryBody(
                id=anchor_id,
                manifest_id=self.manifest_id,
                name=anchor_name,
                jurisdiction=_safe_enum(Jurisdiction, anchor.get("jurisdiction"), Jurisdiction.state),
                authority_type=AuthorityType.industry_body,
                url=anchor_url,
                governs=[],
            ))

        # Update manifest with hierarchy
        manifest = await self.db.get(Manifest, self.manifest_id)
        manifest.jurisdiction_hierarchy = landscape.get("jurisdiction_hierarchy")
        await self.db.flush()

        # Step 2: Source Hunter — batched to handle large body counts
        yield {"event": "step", "data": {
            "step": "source_hunter", "status": "running",
            "message": f"Discovering sources for {len(bodies)} regulatory bodies (batched)...",
        }}

        all_sources = []
        source_id_counter = 1
        batches = [
            bodies[i:i + SOURCE_HUNTER_BATCH_SIZE]
            for i in range(0, len(bodies), SOURCE_HUNTER_BATCH_SIZE)
        ]

        for batch_idx, batch in enumerate(batches):
            yield {"event": "progress", "data": {
                "sources_found": len(all_sources),
                "bodies_processed": batch_idx * SOURCE_HUNTER_BATCH_SIZE,
                "total_bodies": len(bodies),
                "message": f"Batch {batch_idx + 1}/{len(batches)}: processing {len(batch)} bodies...",
            }}

            batch_sources = await self._source_hunter(
                batch,
                start_id=source_id_counter,
                guidance_block=guidance_block,
            )
            new_sources = batch_sources.get("sources", [])

            # Re-number source IDs to ensure global uniqueness
            for src in new_sources:
                src["id"] = f"src-{source_id_counter:03d}"
                source_id_counter += 1

            all_sources.extend(new_sources)

        yield {"event": "step", "data": {
            "step": "source_hunter", "status": "complete",
            "message": f"Found {len(all_sources)} sources across {len(batches)} batches.",
            "sources_found": len(all_sources),
        }}
        # region agent log
        source_jur_counts = Counter((s.get("jurisdiction") or "").strip() for s in all_sources)
        _debug_log(
            "Source hunter output distribution",
            {
                "total_sources": len(all_sources),
                "jurisdiction_counts": dict(source_jur_counts),
                "sample_source_urls": [s.get("url") for s in all_sources[:30]],
            },
            "H6",
        )
        # endregion
        yield {"event": "progress", "data": {
            "sources_found": len(all_sources),
            "bodies_processed": len(bodies),
            "total_bodies": len(bodies),
        }}

        # Persist sources
        for src_data in all_sources:
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
        # Commit sources before program enumeration so that a late-stage Gemini
        # failure cannot zero out discovered sources for this manifest.
        await self.db.commit()
        # region agent log
        _debug_log(
            "P0-partial-persistence: source stage committed",
            {
                "manifest_id": self.manifest_id,
                "sources_committed": len(all_sources),
                "provider": type(self.llm).__name__,
                "p0_check": "H1",
            },
            "P0",
            run_id="169697",
        )
        # endregion

        # Step 3: Program Enumerator
        # region agent log
        _debug_log(
            "Program enumerator start",
            {
                "manifest_id": self.manifest_id,
                "source_count": len(all_sources),
                "seed_program_count": len(seeded_program_candidates),
            },
            "H2",
        )
        # endregion
        enum_started = perf_counter()
        yield {"event": "step", "data": {
            "step": "program_enumerator", "status": "running",
            "message": "Extracting normalized program records...",
        }}
        program_records = await self._program_enumerator(
            domain_description,
            all_sources,
            seeded_program_candidates,
            guidance_block=guidance_block,
        )
        programs = program_records.get("programs", [])
        skipped_batches = program_records.get("skipped_batches", 0)
        verified_programs = [program for program in programs if self._is_source_verified_program(program)]
        deduped_programs = self._dedupe_programs(verified_programs)

        seed_program_ids = {
            p.get("provenance_links", {}).get("seed_row", "")
            for p in deduped_programs
            if p.get("provenance_links", {}).get("seed_row")
        }
        seed_recovery_count = len(seed_program_ids)
        seed_recovery_rate = (
            round(seed_recovery_count / len(seeded_program_candidates), 3)
            if seeded_program_candidates else 0.0
        )

        # region agent log
        _debug_log(
            "Program verification gate applied",
            {
                "manifest_id": self.manifest_id,
                "raw_program_count": len(programs),
                "verified_program_count": len(verified_programs),
                "dropped_unverified_count": len(programs) - len(verified_programs),
                "skipped_batches": skipped_batches,
                "seed_recovery_count": seed_recovery_count,
                "seed_recovery_rate": seed_recovery_rate,
            },
            "H2",
        )
        # endregion
        for idx, program_data in enumerate(deduped_programs, start=1):
            program = Program(
                id=self._program_row_id(idx),
                manifest_id=self.manifest_id,
                canonical_id=self._canonical_program_id(program_data),
                name=program_data.get("name", "Unknown Program"),
                administering_entity=program_data.get("administering_entity", "Unknown"),
                geo_scope=_safe_enum(ProgramGeoScope, program_data.get("geo_scope"), ProgramGeoScope.state),
                jurisdiction=program_data.get("jurisdiction"),
                benefits=program_data.get("benefits"),
                eligibility=program_data.get("eligibility"),
                status=_safe_enum(
                    ProgramStatus, program_data.get("status"), ProgramStatus.verification_pending
                ),
                evidence_snippet=program_data.get("evidence_snippet"),
                source_urls=program_data.get("source_urls", []),
                provenance_links=program_data.get("provenance_links", {}),
                confidence=float(program_data.get("confidence", 0.0) or 0.0),
                needs_human_review=bool(program_data.get("needs_human_review", False)),
            )
            self.db.add(program)
        await self.db.flush()
        # region agent log
        _debug_log(
            "Program enumerator complete",
            {
                "manifest_id": self.manifest_id,
                "raw_program_count": len(programs),
                "deduped_program_count": len(deduped_programs),
                "skipped_batches": skipped_batches,
                "duration_ms": round((perf_counter() - enum_started) * 1000, 2),
            },
            "H2",
        )
        # endregion
        yield {"event": "step", "data": {
            "step": "program_enumerator", "status": "complete",
            "programs_found": len(deduped_programs),
            "skipped_batches": skipped_batches,
            "seed_recovery_count": seed_recovery_count,
            "seed_recovery_rate": seed_recovery_rate,
            "seed_total": len(seeded_program_candidates),
        }}

        # Step 4: Relationship Mapper
        yield {"event": "step", "data": {
            "step": "relationship_mapper", "status": "running",
            "message": "Mapping cross-references and supersession chains...",
        }}

        relationships = await self._relationship_mapper(all_sources, guidance_block=guidance_block)

        # Update sources with relationships
        rel_map = relationships.get("relationships", {})
        for src_data in all_sources:
            src_id = src_data["id"]
            if src_id in rel_map:
                src_data["relationships"] = rel_map[src_id]

        yield {"event": "step", "data": {
            "step": "relationship_mapper", "status": "complete",
            "relationships_mapped": len(rel_map),
        }}

        # Step 5: Coverage Assessor
        yield {"event": "step", "data": {
            "step": "coverage_assessor", "status": "running",
            "message": "Evaluating discovery completeness...",
        }}

        jurisdiction_counts = Counter(s.get("jurisdiction", "") for s in all_sources)
        type_counts = Counter(s.get("type", "") for s in all_sources)

        coverage = await self._coverage_assessor(
            domain_description, len(bodies), len(all_sources),
            dict(jurisdiction_counts), dict(type_counts),
            guidance_block=guidance_block,
        )

        yield {"event": "step", "data": {
            "step": "coverage_assessor", "status": "complete",
            "completeness_score": coverage.get("completeness_score", 0),
        }}

        # Persist coverage assessment
        assessment = CoverageAssessment(
            manifest_id=self.manifest_id,
            total_sources=len(all_sources),
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

        # Step 6: Finalize manifest
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
            "total_sources": len(all_sources),
            "total_programs": len(deduped_programs),
            "coverage_score": coverage.get("completeness_score", 0.0),
            "seed_recovery_count": seed_recovery_count,
            "seed_recovery_rate": seed_recovery_rate,
        }}

    @staticmethod
    def _build_guidance_block(
        constitution_text: str,
        instruction_text: str,
        k_depth: int = 2,
        geo_scope: str = "state",
        target_segments: list[str] | None = None,
        seed_anchors: list[dict] | None = None,
        seed_programs: list[dict] | None = None,
        seed_metrics: dict | None = None,
    ) -> str:
        snippets: list[str] = []
        if constitution_text.strip():
            snippets.append(f"Constitution guardrails:\n{constitution_text.strip()[:12000]}")
        if instruction_text.strip():
            snippets.append(f"Instruction and source guidance:\n{instruction_text.strip()[:12000]}")
        segments = target_segments or []
        controls_lines = [f"- k_depth: {k_depth}", f"- geo_scope: {geo_scope}"]
        if segments:
            controls_lines.append(f"- target_segments: {', '.join(segments)}")
        snippets.append("Run controls:\n" + "\n".join(controls_lines))
        anchor_count = len(seed_anchors or [])
        seed_program_count = len(seed_programs or [])
        if anchor_count or seed_program_count:
            seed_program_hints = seed_programs or []
            unique_seed_hints: list[str] = []
            seen_hint_keys: set[str] = set()
            for seed in seed_program_hints:
                name = str(seed.get("name") or "").strip()
                provider = str(seed.get("administering_entity") or "").strip()
                jurisdiction = str(seed.get("jurisdiction") or "").strip()
                key = "|".join([name.lower(), provider.lower(), jurisdiction.lower()])
                if key in seen_hint_keys:
                    continue
                seen_hint_keys.add(key)
                if provider and name:
                    hint = f"{provider} :: {name}"
                    if jurisdiction:
                        hint += f" ({jurisdiction})"
                    running_chars = sum(len(h) for h in unique_seed_hints)
                    if running_chars + len(hint) > MAX_SEED_HINT_BUDGET:
                        break
                    unique_seed_hints.append(hint)
            snippets.append(
                "Seeding context:\n"
                f"- anchor seeds: {anchor_count}\n"
                f"- program seeds: {seed_program_count}\n"
                f"- seed hints shown: {len(unique_seed_hints)} of {seed_program_count} total\n"
                f"- seed metrics: {json.dumps(seed_metrics or {}, ensure_ascii=True)}\n"
                "- seed hints (provider :: program):\n"
                + "\n".join(f"  - {hint}" for hint in unique_seed_hints)
            )
        if not snippets:
            return ""
        return GUIDANCE_CONTEXT_BLOCK.format(guidance_context="\n\n".join(snippets))

    async def _landscape_mapper(self, domain_description: str, guidance_block: str = "") -> dict:
        prompt = LANDSCAPE_MAPPER_PROMPT.format(
            domain_description=domain_description,
            guidance_block=guidance_block,
        )
        response = await self.llm.complete([
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": prompt},
        ], max_tokens=16384)
        return _extract_json(response)

    async def _source_hunter(
        self,
        bodies: list[dict],
        start_id: int = 1,
        guidance_block: str = "",
    ) -> dict:
        bodies_json = json.dumps(bodies, indent=2)
        prompt = SOURCE_HUNTER_PROMPT.format(
            bodies_json=bodies_json,
            start_id=start_id,
            guidance_block=guidance_block,
        )
        # region agent log
        _debug_log(
            "Source hunter prompt snapshot",
            {
                "body_count": len(bodies),
                "prompt_chars": len(prompt),
                "guidance_chars": len(guidance_block),
                "prompt_preview": prompt[:1400],
            },
            "H5",
        )
        # endregion
        response = await self.llm.complete([
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": prompt},
        ], max_tokens=16384)
        # region agent log
        _debug_log(
            "Source hunter raw response snapshot",
            {
                "response_chars": len(response or ""),
                "response_preview": (response or "")[:1400],
            },
            "H5",
        )
        # endregion
        parsed = _extract_json(response)
        # region agent log
        _debug_log(
            "Source hunter parsed output",
            {
                "sources_count": len(parsed.get("sources", [])),
            },
            "H5",
        )
        # endregion
        return parsed

    async def _relationship_mapper(self, sources: list[dict], guidance_block: str = "") -> dict:
        # Slim down sources for the prompt to avoid token limits
        slim_sources = [
            {"id": s["id"], "name": s["name"], "type": s.get("type"),
             "regulatory_body": s.get("regulatory_body")}
            for s in sources
        ]
        sources_json = json.dumps(slim_sources, indent=2)
        prompt = RELATIONSHIP_MAPPER_PROMPT.format(
            sources_json=sources_json,
            guidance_block=guidance_block,
        )
        response = await self.llm.complete([
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": prompt},
        ], max_tokens=8192)
        return _extract_json(response)

    async def _program_enumerator(
        self,
        domain_description: str,
        sources: list[dict],
        seed_programs: list[dict],
        guidance_block: str = "",
    ) -> dict:
        if not sources and not seed_programs:
            return {"programs": [], "skipped_batches": 0}

        merged_programs: list[dict] = []
        skipped_batches = 0
        context_sources = sources[:SEED_SOURCE_CONTEXT_SIZE]

        total_seed_batches = max(1, (len(seed_programs) + SEED_BATCH_SIZE - 1) // SEED_BATCH_SIZE) if seed_programs else 0
        total_source_batches = max(1, (len(sources) + PROGRAM_ENUMERATOR_BATCH_SIZE - 1) // PROGRAM_ENUMERATOR_BATCH_SIZE) if sources else 0
        total_batches = total_seed_batches + total_source_batches

        # --- Pass 1: Seed-driven enumeration ---
        for i in range(0, len(seed_programs), SEED_BATCH_SIZE):
            seed_batch = seed_programs[i:i + SEED_BATCH_SIZE]
            batch_index = (i // SEED_BATCH_SIZE) + 1
            _debug_log(
                "Seed enumerator batch start",
                {
                    "batch_index": batch_index,
                    "total_seed_batches": total_seed_batches,
                    "seed_batch_size": len(seed_batch),
                    "context_source_count": len(context_sources),
                },
                "H3",
            )
            batch_started = perf_counter()
            sources_json = json.dumps(context_sources, indent=2)
            seed_programs_json = json.dumps(seed_batch, indent=2)
            prompt = SEED_ENUMERATOR_PROMPT.format(
                domain_description=domain_description,
                guidance_block=guidance_block,
                sources_json=sources_json,
                seed_programs_json=seed_programs_json,
            )
            if batch_index == 1:
                _debug_log(
                    "Seed enumerator prompt snapshot",
                    {
                        "batch_index": batch_index,
                        "seed_batch_size": len(seed_batch),
                        "context_source_count": len(context_sources),
                        "prompt_chars": len(prompt),
                        "prompt_preview": prompt[:1600],
                    },
                    "H5",
                )
            try:
                response = await self.llm.complete([
                    {"role": "system", "content": SYSTEM_PROMPT},
                    {"role": "user", "content": prompt},
                ], max_tokens=8192)
                if batch_index == 1:
                    _debug_log(
                        "Seed enumerator raw response snapshot",
                        {
                            "batch_index": batch_index,
                            "response_chars": len(response or ""),
                            "response_preview": (response or "")[:1600],
                        },
                        "H5",
                    )
                batch_programs = _extract_json(response).get("programs", [])
            except Exception as exc:
                skipped_batches += 1
                duration_ms = round((perf_counter() - batch_started) * 1000, 2)
                _debug_log(
                    "Seed enumerator batch skipped",
                    {
                        "batch_index": batch_index,
                        "total_seed_batches": total_seed_batches,
                        "skipped_batches_so_far": skipped_batches,
                        "error": str(exc),
                        "duration_ms": duration_ms,
                    },
                    "H3",
                )
                logger.warning(
                    "[discovery] seed_enumerator batch %d/%d skipped — "
                    "programs_so_far=%d error=%s",
                    batch_index, total_seed_batches, len(merged_programs), exc,
                )
                continue

            _debug_log(
                "Seed enumerator batch complete",
                {
                    "batch_index": batch_index,
                    "batch_program_count": len(batch_programs),
                    "duration_ms": round((perf_counter() - batch_started) * 1000, 2),
                },
                "H3",
            )
            merged_programs.extend(batch_programs)

        seed_pass_count = len(merged_programs)

        # --- Pass 2: Source-driven enumeration ---
        for i in range(0, len(sources), PROGRAM_ENUMERATOR_BATCH_SIZE):
            batch_sources = sources[i:i + PROGRAM_ENUMERATOR_BATCH_SIZE]
            batch_index = total_seed_batches + (i // PROGRAM_ENUMERATOR_BATCH_SIZE) + 1
            _debug_log(
                "Program enumerator batch start",
                {
                    "batch_index": batch_index,
                    "total_batches": total_batches,
                    "batch_source_count": len(batch_sources),
                    "seed_program_sample_count": min(100, len(seed_programs)),
                },
                "H3",
            )
            batch_started = perf_counter()
            sources_json = json.dumps(batch_sources, indent=2)
            seed_programs_json = json.dumps(seed_programs[:100], indent=2)
            prompt = PROGRAM_ENUMERATOR_PROMPT.format(
                domain_description=domain_description,
                guidance_block=guidance_block,
                sources_json=sources_json,
                seed_programs_json=seed_programs_json,
            )
            if batch_index == total_seed_batches + 1:
                _debug_log(
                    "Program enumerator prompt snapshot",
                    {
                        "batch_index": batch_index,
                        "batch_source_count": len(batch_sources),
                        "seed_program_sample_count": min(100, len(seed_programs)),
                        "prompt_chars": len(prompt),
                        "prompt_preview": prompt[:1600],
                    },
                    "H5",
                )
            try:
                response = await self.llm.complete([
                    {"role": "system", "content": SYSTEM_PROMPT},
                    {"role": "user", "content": prompt},
                ], max_tokens=8192)
                if batch_index == total_seed_batches + 1:
                    _debug_log(
                        "Program enumerator raw response snapshot",
                        {
                            "batch_index": batch_index,
                            "response_chars": len(response or ""),
                            "response_preview": (response or "")[:1600],
                        },
                        "H5",
                    )
                batch_programs = _extract_json(response).get("programs", [])
            except Exception as exc:
                skipped_batches += 1
                duration_ms = round((perf_counter() - batch_started) * 1000, 2)
                _debug_log(
                    "Program enumerator batch skipped after exhausted retries",
                    {
                        "batch_index": batch_index,
                        "total_batches": total_batches,
                        "skipped_batches_so_far": skipped_batches,
                        "error": str(exc),
                        "duration_ms": duration_ms,
                    },
                    "H3",
                )
                logger.warning(
                    "[discovery] program_enumerator batch %d/%d skipped — "
                    "programs_so_far=%d error=%s",
                    batch_index, total_batches, len(merged_programs), exc,
                )
                continue

            _debug_log(
                "Program enumerator batch complete",
                {
                    "batch_index": batch_index,
                    "batch_program_count": len(batch_programs),
                    "duration_ms": round((perf_counter() - batch_started) * 1000, 2),
                },
                "H3",
            )
            merged_programs.extend(batch_programs)

        _debug_log(
            "Enumerator complete (seed + source passes)",
            {
                "merged_programs": len(merged_programs),
                "seed_pass_programs": seed_pass_count,
                "source_pass_programs": len(merged_programs) - seed_pass_count,
                "skipped_batches": skipped_batches,
                "total_batches": total_batches,
            },
            "H2",
        )
        return {"programs": merged_programs, "skipped_batches": skipped_batches}

    @staticmethod
    def _is_source_verified_program(program_data: dict) -> bool:
        """Two-tier verification gate.

        Tier 1 (full): source_urls + source_ids + evidence_snippet
        Tier 2 (seed-match): source_urls + source_ids + seed provenance marker
        """
        source_urls = program_data.get("source_urls") or []
        provenance = program_data.get("provenance_links") or {}
        source_ids = provenance.get("source_ids") or []
        evidence_snippet = (program_data.get("evidence_snippet") or "").strip()
        seed_file = (provenance.get("seed_file") or "").strip()
        seed_row = str(provenance.get("seed_row") or "").strip()

        has_source_anchors = bool(source_urls and source_ids)

        if has_source_anchors and evidence_snippet:
            return True

        if has_source_anchors and (seed_file or seed_row):
            return True

        return False

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

    async def _coverage_assessor(
        self, domain_description: str, bodies_count: int, sources_count: int,
        jurisdiction_breakdown: dict, type_breakdown: dict,
        guidance_block: str = "",
    ) -> dict:
        prompt = COVERAGE_ASSESSOR_PROMPT.format(
            domain_description=domain_description,
            bodies_count=bodies_count,
            sources_count=sources_count,
            jurisdiction_breakdown=json.dumps(jurisdiction_breakdown, indent=2),
            type_breakdown=json.dumps(type_breakdown, indent=2),
            guidance_block=guidance_block,
        )
        response = await self.llm.complete([
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": prompt},
        ])
        return _extract_json(response)
