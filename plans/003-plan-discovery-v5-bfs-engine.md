---
type: plan
created: 2026-03-02T21:00:00
sessionId: S20260302_2100
source: cursor-plan
description: V5 Graph BFS Discovery Engine — rewrite graph_discovery.py as true BFS with 6 parallel sector L1 calls and per-entity L2 expansion
---

# V5 Graph BFS Discovery Engine — Implementation Plan

## Goal

Rewrite `graph_discovery.py` from a sequential processing pipeline (V4) into a true BFS graph engine where each depth level represents real graph traversal depth, not processing passes. k_depth=2 (L1 entities + L2 programs) is the first validation run.

## Constraints

- All 306 existing tests must remain green
- No destructive changes to existing DB tables — use `native_enum=False` for enum expansion
- SessionId: `S20260302_2100`
- V4 `discovery.py` (flat pipeline) is untouched
- `_extract_json()`, `_safe_enum()`, `_dedupe_programs()` are preserved

## Implementation Steps

### Commit 1 — DB Prereq: Expand `AuthorityType` + add `coverage_summary`

**File:** `backend/app/models/manifest.py`

- Expand `AuthorityType` to include: `state_hfa`, `municipal`, `pha`, `nonprofit`, `cdfi`, `employer`, `tribal` (keep existing 4 values)
- Add `native_enum=False` on the `authority_type` column in `RegulatoryBody`
- Add `coverage_summary: Mapped[dict | None] = mapped_column(JSONB, nullable=True)` to `Manifest`
- **Requires:** `docker-compose down -v && docker-compose up -d` to reset DB in dev

### Commit 2 — Schema + Router: Add `geo_target` field

**Files:** `backend/app/schemas/manifest.py`, `backend/app/routers/manifests.py`

- Add `geo_target: str | None = None` to `GenerateManifestRequest`
- Pass `geo_target` through `_run_agent()` into `DiscoveryGraph.run()`

### Commit 3 — Prompts: 6 sector-specific L1 prompts + L2 entity expansion prompt

**File:** `backend/app/agent/prompts.py`

- Add `L1_SECTOR_SYSTEM` — system prompt for all sector calls
- Add 6 sector user prompts: `L1_SECTOR_FEDERAL`, `L1_SECTOR_STATE_HFA`, `L1_SECTOR_EMPLOYER`, `L1_SECTOR_NONPROFIT`, `L1_SECTOR_TRIBAL`, `L1_SECTOR_MUNICIPAL`
- Add `L2_ENTITY_EXPANSION_PROMPT`
- Add `L1_SECTOR_JSON_SCHEMA_SUFFIX`
- Fix `L0_JSON_SCHEMA_SUFFIX`: "Section 7" → "Section 8"

### Commit 4 — Engine Rewrite: `graph_discovery.py` → V5 BFS

**File:** `backend/app/agent/graph_discovery.py`

- `_run_l1_sectors()` — 6 sector calls via asyncio.gather, batched by sector_concurrency=3
- `_run_l2_entity_expansion()` — one call per L1 entity, parallelized
- k_depth routing: 1=L1 only, 2=L1+L2, 3=L1+L2+L3
- New SSE events: sector_start/complete, l1_assembly_complete, entity_expansion_start/complete

### Commit 5 — Tests + Frontend

- `backend/tests/test_graph_discovery_v5.py` — new V5 test suite
- `backend/tests/test_graph_discovery.py` — update SSE event name assertions
- `frontend/src/components/DomainInputPanel.tsx` — add optional geo_target field

## Files to Create/Update

- `plans/003-plan-discovery-v5-bfs-engine.md` — this plan
- `backend/app/models/manifest.py`
- `backend/app/schemas/manifest.py`
- `backend/app/routers/manifests.py`
- `backend/app/agent/prompts.py`
- `backend/app/agent/graph_discovery.py`
- `backend/tests/test_graph_discovery_v5.py`
- `backend/tests/test_graph_discovery.py`
- `frontend/src/components/DomainInputPanel.tsx`

## Validation

- `k_depth=1` live run: 6 `sector_start`/`sector_complete` SSE pairs visible; total entities > 20
- `k_depth=2` live run: entities > 50, programs > 200, `coverage_summary` populated per sector
- All 306 existing tests pass
- `needs_human_review: true` on confidence < 0.5 items
