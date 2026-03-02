---
type: handoff
created: 2026-03-02T21:30:00
sessionId: S20260302_1400
source: cursor-agent
description: Handoff to planning agent for V5 Graph BFS Discovery Engine rewrite
---

# Handoff — Discovery V5: Graph BFS Engine

## Mandatory Reads Before Planning

1. `docs/DFW-CONSTITUTION.md` — universal rules
2. `context/_ACTIVE_CONTEXT.md` — current project state
3. `plans/_TODO.md` — active tasks
4. `backend/app/agent/graph_discovery.py` — the current V4 engine to be replaced
5. `prompts/FrankPromptTest.ms` — Frank's new prompt (the design input for V5)
6. `backend/app/agent/prompts.py` — all engine prompts (L0–L3)
7. `backend/app/models/manifest.py` — DB schema (AuthorityType, Program, RegulatoryBody)

---

## Why This Handoff Exists

The V4 engine was a significant improvement over V3 (generic prompts) but has a **fundamental architecture flaw** discovered during live validation runs (March 2, 2026):

### The V4 Flaw — Sequential Pipeline Disguised as a Graph

V4 labels its stages L0–L3 but these are NOT graph depth levels. They are sequential processing passes:
- L0 = one giant LLM call trying to discover everything
- L1 = expand entities L0 returned
- L2 = verify low-confidence programs
- L3 = gap fill

The result: L0 is constrained to one API call with a 64-search AFC budget. With a national DPA scope, 64 searches finds ~1 body. L1 then runs as "batch 1/1" because there's only 1 body to expand. Total output: 6–13 programs.

### The Correct Mental Model (Frank's Design)

L0–LN are **graph depth levels** not processing passes:

```
L0 (Domain Anchor)
│
└── L1 (Sector Entities — discovered separately per sector)
    ├── Federal/National entities
    ├── State HFA entities (all 50)
    ├── Employer/Industry entities
    ├── Nonprofit/CDFI entities
    ├── Tribal entities
    └── Municipal/County/PHA entities
              │
              └── L2 (Programs per entity — one expansion call per L1 node)
                        │
                        └── L3 (Program detail — benefits, eligibility, status, portals)
```

**k_depth is a true graph depth limit.** `k_depth=1` → discover L1 entities only. `k_depth=2` → discover L1 entities + L2 programs. `k_depth=3` → full detail.

---

## Current Engine State

### File: `backend/app/agent/graph_discovery.py`

Key methods and their problems:

| Method | Current behavior | Problem |
|--------|-----------------|---------|
| `run()` | Orchestrates L0→L1→L2→L3 sequentially | Labels are processing passes, not graph depth |
| `_l0_discovery()` | Single `complete_grounded()` call with full instruction prompt | One call, one AFC budget, tries to find everything |
| `_run_l1_expansion()` | Batches entities from L0 output, runs one call per batch | Dependent on L0 finding enough entities first |
| `_run_l2_verification()` | Verifies low-confidence programs | Useful but misnamed |
| `_l3_gap_fill()` | Gap analysis vs. seeds and sector coverage | Useful but fires too late |

### `_SEED_TO_ENTITY_TYPE` mapping (lines 68–78)

```python
_SEED_TO_ENTITY_TYPE = {
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
```

This seed-to-entity mapping is still valid and should be preserved in V5.

### `AuthorityType` enum (models/manifest.py lines 70–74)

Currently only has 4 values: `regulator`, `gse`, `sro`, `industry_body`. The V5 entity model needs: `state_hfa`, `municipal`, `pha`, `nonprofit`, `cdfi`, `employer`, `tribal`. This is a prerequisite for V5 and requires `native_enum=False` on the column to avoid a PostgreSQL ENUM migration.

### AFC Limit Fix (already applied)

`backend/app/llm/gemini_provider.py` — `complete_grounded()` now passes `maximum_remote_calls=64`. This should be preserved but the architecture fix reduces dependence on a single large call.

---

## Frank's New Prompt — `prompts/FrankPromptTest.ms`

This is the **design input** for the V5 engine. Key concepts to implement:

### Traversal Priority (ordered, MUST BE DONE SEPARATELY)
```
1. Federal/National
2. State HFA
3. Employer/Industry
4. Nonprofit/CDFI
5. Tribal
6. Municipal/County/PHA
```

Each sector is a **separate LLM call** with its own 64-search AFC budget. This is the core fix. 6 sector calls × 64 searches = 384 searches for L1 entity discovery alone.

### BFS Queue Model
```
Queue items: {target_type: entity|source, category: 1–6, priority_rank, discovered_from, urls}
Maintain: VisitedEntities, VisitedSources
Stop when: Queue empty AND all sectors attempted AND cross-check done
```

### Completeness Gates (define "done")
- Coverage: attempted discovery for every category 1–6, with negative evidence if none found
- Closure: Queue empty
- Verification: all non-candidate Programs have Tier 1–3 evidence
- Cross-check: aggregator sweep vs. what the graph contains

### Output Schema (Frank's format — richer than current)
```json
{
  "scope": { ... },
  "run_metadata": { "as_of_date": "...", "notes": [...] },
  "coverage_summary": {
    "federal": { "entities_found": N, "programs_found": N, "gaps": [...] },
    "state_hfa": { ... },
    "employer": { ... },
    "nonprofit": { ... },
    "tribal": { ... },
    "municipal": { ... }
  },
  "graph": {
    "administering_entities": [...],
    "funding_streams": [...],
    "programs": [...],
    "edges": [...]
  },
  "queue_state": {
    "visited_entities": [...],
    "visited_sources": [...],
    "next_actions": [...]
  }
}
```

### Template Variables (currently unresolved in Frank's prompt)
`{STATE}`, `{COUNTY}`, `{CITY/PLACE}`, `{ZIPs optional}`, `{METRO/REGION optional}` — the engine must substitute these before sending the prompt. The `manifest_name` field and a new `geo_target` form field are the natural inputs.

---

## V5 Architecture — What to Build

### Core Change: L1 = 6 Parallel Sector Calls

Instead of one `_l0_discovery()` call:

```python
# V5 L1 architecture
async def _run_l1_sectors(geo_target, geo_scope) -> dict:
    sectors = [
        "federal",
        "state_hfa",
        "employer",
        "nonprofit",
        "tribal",
        "municipal",
    ]
    # Run all 6 concurrently (subject to API rate limits)
    results = await asyncio.gather(*[
        _discover_sector(sector, geo_target, geo_scope)
        for sector in sectors
    ], return_exceptions=True)
    return _assemble_l1_graph(results)
```

Each `_discover_sector()` call:
- Gets a focused system prompt for that sector
- Gets the sector-specific queries from Frank's SEARCH BEHAVIOR section
- Has its own 64-search AFC budget
- Returns `administering_entities[]` for that sector

### L2 = One Expansion Call Per L1 Entity

```python
# V5 L2 architecture
async def _run_l2_entity_expansion(entities: list[dict]) -> list[dict]:
    # Parallel expansion — one call per entity
    tasks = [_expand_entity(e) for e in entities]
    results = await asyncio.gather(*tasks, return_exceptions=True)
    return flatten_programs(results)
```

Each entity expansion call asks: "find all programs, portals, and guidelines for {entity_name} at {entity_url}"

### k_depth as True Graph Depth

```
k_depth=1 → Run L1 sector calls only → return entity graph
k_depth=2 → Run L1 + L2 entity expansion → return entities + programs
k_depth=3 → Run L1 + L2 + L3 program detail → return full program records
```

### SSE Event Model (update for V5)

Current SSE events use `step` with `discovery_level=0,1,2,3`. V5 should emit:
- `sector_start` / `sector_complete` — one pair per L1 sector
- `l1_assembly_complete` — after all 6 sectors merged
- `entity_expansion_start` / `entity_expansion_complete` — per L2 entity
- `program_detail_complete` — L3 (if k_depth=3)
- `complete` — final with coverage_summary

---

## What Should NOT Change

- `discovery.py` (flat pipeline) — untouched
- `_extract_json()` / `_safe_enum()` — preserved
- `manifests.py` router — only minor changes for new `geo_target` field
- `gemini_provider.py` AFC=64 fix — preserved
- Test infrastructure — all 306 tests should remain green

---

## Key Decisions for Planning Agent

1. **Schema mapping**: Frank's output has `administering_entities[]` not `regulatory_bodies[]`. Does V5 map Frank's schema to the existing DB tables, or does it add new columns/tables? Recommend: map `administering_entities` → `regulatory_bodies` for backward compat, store `coverage_summary` + `edges` as JSONB on the `Manifest` record.

2. **Concurrency model**: Run all 6 sector calls in parallel (faster, ~2–3 min total) or sequential (safer, ~10–12 min)? Recommend: parallel with `asyncio.gather`, each with independent error handling so one sector failure doesn't abort the run.

3. **Geo target input**: Frank's prompt has `{STATE}`, `{COUNTY}`, `{CITY/PLACE}`. Should this come from the `manifest_name` field, a new `geo_target` form field, or parsed from the instruction file? Recommend: new optional `geo_target` form field alongside `manifest_name`. If absent, defaults to national scope.

4. **`AuthorityType` DB migration**: Must expand enum + use `native_enum=False`. Requires `docker-compose down -v` to reset DB in dev. Plan this as the first commit.

5. **Rate limiting**: 6 parallel grounded calls may hit Gemini quota. Build in a configurable `sector_concurrency` parameter (default 3 — run 2 batches of 3 sectors).

---

## Validation Criteria for V5

- `k_depth=1` run: 6 sector calls visible in SSE events, total entities > 50
- `k_depth=2` run: entities > 50, programs > 200, `coverage_summary` shows counts per sector
- All 306 existing tests pass
- No silent drops — `needs_human_review: true` on low-confidence items
- `queue_state.next_actions` populated — shows what was cut off by AFC limit

---

## Files to Create/Modify

| File | Action |
|------|--------|
| `backend/app/agent/graph_discovery.py` | Full rewrite — V5 BFS engine |
| `backend/app/agent/prompts.py` | New sector-specific L1 prompts + L2 entity expansion prompt |
| `backend/app/models/manifest.py` | Expand `AuthorityType`, add `native_enum=False`, add `coverage_summary` JSONB to `Manifest` |
| `backend/app/schemas/manifest.py` | Add optional `geo_target` field |
| `backend/app/routers/manifests.py` | Pass `geo_target` through to engine |
| `frontend/src/components/DomainInputPanel.tsx` | Add optional `geo_target` input field |
| `prompts/FrankPromptTest.ms` | Rename to `DPA_Prompt_v7.md` and finalize template |
| `backend/tests/test_graph_discovery_v5.py` | New test file |
| `backend/tests/test_graph_discovery.py` | Update for V5 SSE event names |
| `context/_ACTIVE_CONTEXT.md` | Update after planning complete |
| `plans/_TODO.md` | Update after planning complete |

---

## Current System State

- All containers running: frontend `:5900`, backend `:5901`, db `:5902`, redis `:5903`
- Backend: 306 tests passing
- Live bug: `authority_type` enum too narrow (only 4 values) — the V5 plan should address as first commit
- Live bug: `L0_JSON_SCHEMA_SUFFIX` references "Section 7" but V6 has Section 8 — fix in V5 prompt work
- AFC limit raised to 64 (deployed, active)
