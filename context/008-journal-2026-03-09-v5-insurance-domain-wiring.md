---
type: journal
created: 2026-03-09T03:30:00
sessionId: S20260309_0030
source: cursor-agent
description: Insurance domain v3 wiring — adaptive prompting, seed anchors, authority_type fixes, DB column widening, L2 source dedup
---

# Journal — 2026-03-09 — Insurance V3 Engine Wiring

## Session Goal

Complete the "Insurance V3 Engine Wiring Plan" — wire the new fields introduced
in `Insurance_Prompt_v3.md` into the engine, fix two pre-existing bugs exposed
during the first real insurance domain run, and make the engine fully capable
of executing deep, jurisdiction-aware BFS discovery for the insurance regulatory
domain.

---

## What Was Built

### 1. `authority_type` Field Mapping Bug — Fixed

The engine was persisting every entity with `authority_type=None` because it
was reading `entity.get("entity_type")` but v3 entities (and the prompt schema)
use the key `authority_type`. One-line fix with a fallback for legacy data:

```python
authority_type=_safe_enum(AuthorityType, entity.get("authority_type") or entity.get("entity_type"))
```

### 2. New v3 Authority Types Added to DB Enum

`AuthorityType` in `models/manifest.py` now includes five new values needed to
correctly classify the full insurance regulatory landscape:

- `residual_market_mechanism` — FAIR Plans, JUAs, assigned risk pools, windstorm pools
- `compact` — IIPRC, NARAB, NIMA and similar interstate agreements
- `advisory_org` — ISO/Verisk, AAIS and similar rating/filing organizations
- `actuarial_body` — AAA, CAS, SOA
- `trade_association` — ACLI, AHIP, APCIA, RAA, IIABA, NAPIA

The column already uses `native_enum=False` (VARCHAR) so no Alembic migration
was required for the enum itself. However, the column was sized `VARCHAR(13)`
(sized to the longest old value at creation time: `industry_body`). The new
values exceed 13 characters, causing `StringDataRightTruncationError` on the
first real insurance run. Fixed with:
- `Enum(..., length=50)` added to the model column definition
- `ALTER TABLE regulatory_bodies ALTER COLUMN authority_type TYPE VARCHAR(50)`
  executed directly via psql in the DB container
- Migration file `004_widen_authority_type.py` created for the record

### 3. Adaptive Expansion Prompts — Citation Hints Wired

`build_expansion_prompt()` in `prompts.py` now reads two new fields from each
entity and injects them into the expansion template:

- `citation_format_hint` — e.g. "N.J.S.A." for NJ, "Tex. Ins. Code" for TX
- `jurisdiction_code` — machine-readable state/territory code

The `regulator` template was updated to use both. Five new templates were also
added for the new authority types (`advisory_org`, `actuarial_body`,
`trade_association`, `residual_market_mechanism`, `compact`), each with
appropriate domain-specific instructions.

The `_expand_entity` prompt header in `graph_discovery.py` was also updated to
show both fields, so every L2+ LLM call now carries a header like:

```
## Jurisdiction: New Jersey (NJ)
## Citation format: N.J.S.A.
```

### 4. Seed Anchors Wired into BFS Queue

The seed file was previously parsed, stored, and silently dropped — it never
entered the BFS queue. Now `agent.run()` accepts `seed_anchors: list[dict]`
and injects them at `priority=1` (highest) after L1 completes. The queue's
visited set ensures no entity is processed twice.

`manifests.py` was updated to forward `seed_anchors` from `_run_agent()` to
`agent.run()`. This fulfills the "entity coverage guarantee" principle: known
entities from the seed file enter the queue even if L1 missed them.

### 5. SSE Jurisdiction Display

`entity_expansion_start` SSE events now carry `citation_format` and
`jurisdiction_code`. The UI expansion message updated to:

```
[L2][NJ] New Jersey Dept. of Banking and Insurance (1/123)
```

Previously it showed a generic "Expanding [1/123]: ..." format with no
jurisdiction context.

---

## Bugs Encountered During Live Testing

### Bug 1: `StringDataRightTruncationError` — VARCHAR(13) column

First insurance run failed immediately at L1 persistence. New v3 authority
types (`trade_association`, `residual_market_mechanism`) are longer than the
column allowed. Fixed with `ALTER COLUMN` + model `length=50`.

### Bug 2: `UniqueViolationError` on `sources_pkey` — L2 Phase

Second run reached entity 123/246 before failing. The L1 source dedup fix
(applied in a previous session) only covered L1. The L2 expansion loop had
the same unguarded insert — multiple entity expansions return the same shared
sources (e.g., `naic.org` cited by 50+ state regulators).

Fixed by initializing `l2_seen_source_ids: set[str]` before the L2 while-loop
and guarding every source insert. This is the same pattern as the L1 fix,
scoped correctly to the L2 phase. Duplicate sources are logged at DEBUG level
and skipped cleanly.

---

## Key Numbers From the Run (Before L2 Failure)

- L1: **150 entities** across 3 neutral runtime sectors (50 entities/sector cap)
- Sectors: Federal/National, State/Regional, Industry/SRO/Trade
- L2 reached entity **123/246** before the source dedup error
- Seed anchors: 70+ entities injected into queue after L1

The run was healthy and producing good results up to the failure point. With
the L2 dedup fix applied, a full K=1 run with 246 entities should complete
cleanly.

---

## State of `Insurance_Prompt_v3.md`

v3 is a significant improvement over v2:

- **L1/L2 separation is explicit** — v3 states clearly that L1 is entity
  discovery only; statute enumeration happens at L2+
- **New fields**: `citation_format_hint`, `jurisdiction_code`, `mechanism_type`
- **New authority types**: all five v3 types are in both the prompt schema and
  the engine enum
- **Seed awareness**: prompt instructs the LLM to treat seed entities as
  confirmed and find everything beyond them
- **Residual market coverage**: FAIR Plans, JUAs, guaranty funds, windstorm
  pools explicitly called out
- **`regulatory_mechanisms` replaces `programs`** — correct vocabulary for
  insurance domain

The prompt is production-ready for the insurance domain.

---

## Files Changed

| File | Change |
|------|--------|
| `backend/app/agent/graph_discovery.py` | authority_type key fix, seed_anchors param + queue injection, L2 source dedup, SSE event fields, _expand_entity header |
| `backend/app/agent/prompts.py` | 5 new EXPANSION_TEMPLATES, updated regulator template with citation/jurisdiction placeholders, updated build_expansion_prompt() |
| `backend/app/models/manifest.py` | 5 new AuthorityType enum values, Enum length=50 |
| `backend/app/routers/manifests.py` | Forward seed_anchors to agent.run() |
| `frontend/src/hooks/useSSE.ts` | Updated entity_expansion_start message format |
| `backend/alembic/versions/004_widen_authority_type.py` | Migration record for VARCHAR(50) |
| `backend/tests/test_graph_discovery_v4.py` | Fixed 2 tests to match updated engine behavior |

---

## Next Steps

1. Run K=1 insurance discovery to full completion — verify 0 errors
2. Confirm `authority_type` populated correctly in DB for all 246 entities
3. Check L2 logs for `## Citation format: N.J.S.A.` on NJ DOBI expansion
4. Confirm seed anchor log: `[graph v6] seed anchors injected — count=70`
5. Update model defaults: bump `anthropic_model` and `gemini_model` to latest
   versions in `config.py` (noted for next session)
6. Consider K=2 or K=3 run once K=1 is validated clean
