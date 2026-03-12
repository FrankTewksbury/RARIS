---
type: handoff
created: 2026-03-10T19:30:00
sessionId: S20260310_1831
source: cursor-agent
description: Handoff after ALGO-012 fine-grain BFS implementation and first validation run — next session fixes entity cap, template sparseness, and runs with seed
---

# Handoff — ALGO-012 Fine-Grain BFS: First Validation & Next Steps

## Session Summary

This session implemented **ALGO-012** (fine-grain BFS recursion) and ran the first validation test
against the NJ statutory baseline. The architecture change is confirmed working but revealed two
concrete issues that must be fixed before the next quality run.

---

## What Was Built This Session

### ALGO-012 — Fine-Grain BFS Recursion (committed `b7ef7c3`)

Replaced the monolithic exhaustive-enumeration prompt with **13 node-type-keyed single-question
templates**. The framework now drives traversal; the LLM answers one bounded question per call.

**Key changes:**
1. `EXPANSION_TEMPLATES` replaced — 13 templates keyed as `node:entity:{authority_type}` and
   `node:source_title` / `node:source_chapter` / `node:source_section`
2. Source nodes enter the BFS queue — `depth_hint` field on every source classifies it as
   `title|chapter|section|leaf` and re-enqueues non-leaf sources for deeper expansion
3. `_expand_entity()` → `_expand_node()` — dispatches by `node_type`
4. Stored L1 `expansion_prompt` removed — template always authoritative
5. `depth_hint` + `citation` fields required on every source
6. NJ-specific hardcoded examples removed — all use `{citation_hint}`
7. Run sequence tag `[RUN-{timestamp}]` on all log output

**Confirmed working in live run:**
- `NODE EXPANSION — DEPTH L3 [source_title]` events visible in logs
- Source nodes (NAIC Model Law Series, IIPRC Compact Statute, 31 U.S.C., 42 U.S.C., etc.)
  successfully enqueued and expanded at L3
- 284 total queue items in second run (63 entities + ~221 source nodes) — BFS traversal is real

---

## Validation Run Results (Run 2 — `20260310183101`)

### L1 Entity Coverage (no seed file used)

| Category | Seed | Found | Coverage |
|----------|------|-------|----------|
| State departments | 52 | 41 | 79% |
| Federal / national | 11 | 11 | 100% |
| Industry / trade / advisory | 17 | 5 | 29% |
| **Total** | **70** | **63** | **90%** |

**11 states missed:** RI, SC, SD, TN, UT, VA, VT, WA, WI, WV, WY + DC
**12 industry bodies missed:** ISO/Verisk, AAIS, NCOIL, AAA, CAS, SOA, ACLI, AHIP, APCIA, RAA,
IIABA, NAPIA

### NJ DOBI Expansion Issue

NJ DOBI was called at L2 (`18:44:45`) with the new `node:entity:regulator` template. The L2
call succeeded but returned **zero sources** that were persisted. Root cause: the template asks
for "top-level statute titles only" — Gemini Flash returned sources but either with no
`depth_hint` field or with an empty `sources[]`. Without `depth_hint`, `child_node_type` resolves
to `None` and sources are neither re-enqueued nor persisted correctly.

**Note:** Other federal source_title nodes (31 U.S.C., 42 U.S.C., NAIC series) DID work
correctly — they enqueued and fired at L3. The NJ DOBI specific issue may be related to the
entity's `authority_type` resolution or Gemini Flash struggling with the strict "titles only"
constraint without the old exhaustive prompt context.

---

## Two Issues to Fix Next Session

### Fix 1 — Remove / raise `max_entities_per_sector` cap

**File:** `backend/app/config.py` line 65
**Current:** `max_entities_per_sector: int = 50`
**Problem:** Hard cap silently truncates sector results. For insurance, the state_regional sector
needs to return 52+ bodies. The cap is a legacy safety guardrail that hurts recall on known
bounded domains.
**Fix:** Raise to `200` (or make it a per-run UI parameter). This alone will fix the 11 missing
states — Gemini returned 43 without it being an issue, but the cap was 50 so nothing was
truncated this run. The real risk is future runs where Gemini returns more entities and gets
silently capped.
**Also consider:** Adding a completeness check warning when `len(entities) > 0.8 *
max_entities_per_sector` to signal "you may be near the cap."

### Fix 2 — Loosen `node:entity:regulator` template to allow titles + chapters

**File:** `backend/app/agent/prompts.py` — `EXPANSION_TEMPLATES["node:entity:regulator"]`
**Problem:** The template says "List ONLY top-level statute titles... Do NOT enumerate chapters."
Gemini Flash interprets this too strictly and returns empty or near-empty `sources[]` for state
regulators because it doesn't have strong enough parametric knowledge of the exact title
structure to name titles confidently without also naming the chapters it knows.
**Fix:** Change to "List statute titles AND their immediate chapters. Classify each with
depth_hint: title for top-level groupings, chapter for individual chapters/named acts."
This gives Gemini enough room to be useful while still enforcing the classification contract.
The BFS re-enqueuing handles the rest based on `depth_hint`.

---

## Pending Algorithm Experiments (from ALGO-012 plan)

- **EXP-003** (highest priority): Source dedup by `(name, entity_id)` not prefixed ID — fixes
  5x source inflation from ALGO-008
- **EXP-001**: Restore `complete_grounded()` for L2+ expansion — +depth for obscure statutes
- **EXP-002**: Parallel entity expansion (asyncio.gather N at a time) — -runtime 5-10x

---

## Files Changed This Session

| File | Change |
|------|--------|
| `backend/app/agent/prompts.py` | ALGO-012 — 13 templates, updated schema, new `build_expansion_prompt` |
| `backend/app/agent/graph_discovery.py` | `_expand_node()`, source enqueue by `depth_hint` |
| `backend/app/llm/call_logger.py` | `manifest_id` → `[RUN-{ts}]` prefix on all log output |
| `docs/014-doc-algo-history.md` | ALGO-012 entry |
| `C:\DATA\DFW\Vault\projects\raris\algo-history.md` | Obsidian sync |
| `prompts/Insurance_Prompt_v4.md` | L1 scoped to entity discovery only, not societies |

---

## Commits This Session

| Hash | Message |
|------|---------|
| `27f02ea` | `chore: checkpoint before ALGO-012 fine-grain BFS recursion #algo` |
| `b7ef7c3` | `feat(algo): ALGO-012 fine-grain BFS recursion — single-question templates, source node queue traversal #algo` |

---

## Next Session — Immediate Actions

1. **Fix `max_entities_per_sector`** — raise to 200 in `backend/app/config.py`
2. **Fix `node:entity:regulator` template** — allow titles + chapters, classify by `depth_hint`
3. **Run with seed file** (`Insurance_seed_v1.md`) at k=3 on Gemini Flash
4. **Compare against NJ baseline** (`research/NJ-example_statutes.md`) — target 70%+ coverage
5. **Check `depth_hint` persistence** — verify that source nodes from NJ DOBI are being
   enqueued at L3 with the loosened template
6. **Consider EXP-003** (source dedup) if 5x duplicates persist

---

## Current State

- Backend: live, healthy, ALGO-012 deployed
- Run `20260310183101`: still generating (284 queue items, ~177/284 at last check)
- Run `20260310183100`: `pending_review` — 9 sources only (first run fired simultaneously,
  also pre-seed, small run)
- DB: `raris-db-1` running, all tables intact
- Git: clean, pushed to `origin/main`
