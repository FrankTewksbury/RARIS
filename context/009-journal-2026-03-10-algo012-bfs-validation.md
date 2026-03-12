---
type: journal
created: 2026-03-10T19:30:00
sessionId: S20260310_1831
source: cursor-agent
description: Session journal — ALGO-012 implementation, first validation run, L1 coverage gap analysis, hard cap discovery
---

# Journal — 2026-03-10 — ALGO-012 Fine-Grain BFS: Build, Run, Validate

## What Happened

This session was a major architectural shift. After the previous session diagnosed that the
monolithic exhaustive-enumeration prompt was pushing recursion burden onto the LLM (violating the
core DFW principle that framework drives traversal, model answers one bounded question), we
implemented **ALGO-012: Fine-Grain BFS Recursion**.

### The Build

Replaced a single 6-rule monolithic template with 13 node-type-keyed single-question templates.
Every prompt now asks exactly one question:
- `node:entity:regulator` → "List the top-level statute titles and administrative code titles"
- `node:source_title` → "List the direct child chapters of this title"
- `node:source_chapter` → "List the sections within this chapter"
- etc.

Added `depth_hint` and `citation` fields to the source schema so the engine — not the LLM —
decides what to re-enqueue. Removed `expansion_prompt` from entity schema entirely. Added
`[RUN-{timestamp}]` run tag to all log output for correlation.

### The Run

Fired a k=3 run on Gemini Flash **without the seed file** (deliberate — wanted to measure
baseline LLM parametric recall).

**What worked:**
- BFS source traversal is real: saw `NODE EXPANSION — DEPTH L3 [source_title]` firing for
  NAIC Model Law Series, 31 U.S.C., 42 U.S.C., IIPRC Compact Statute
- 284 queue items (entities + source nodes) vs ~150 pure-entity runs before ALGO-012
- Federal/national entity coverage: 100% (11/11)
- Auto-approve working — manifests flipping to approved without manual intervention

**What revealed gaps:**
1. NJ DOBI called at L2 but returned zero sources — `node:entity:regulator` template too strict
   ("titles only") caused Gemini Flash to fail the mapping
2. 11 states missing from L1 (79% coverage) — Gemini Flash recall bias + entity cap

### The Cap Discovery

User asked "why is there a hard cap?" Cap was traced to `backend/app/config.py`:
`max_entities_per_sector: int = 50`. Legacy safety guardrail from the early engine — designed
to prevent junk flooding the queue. In a bounded domain like insurance (52 states = one sector),
it silently truncates valid results. Fix: raise to 200.

---

## Decisions Made

- ALGO-012 is the right architecture. BFS source traversal is confirmed working.
- `node:entity:regulator` template needs loosening — allow titles AND chapters, let `depth_hint`
  classify. Don't fight Gemini Flash's recall; let it be useful.
- Seed file is mandatory for any quality run. Without it, L1 coverage is ~79% states, 29%
  industry bodies.
- `max_entities_per_sector` must be raised. 50 is wrong for insurance.

---

## Open Questions Going Into Next Session

- Does the NJ DOBI issue reproduce with the loosened template + seed file?
- How many NJ statutes does k=3 retrieve with complete L1 coverage?
- Is `depth_hint` being persisted correctly on the source rows, or is it being dropped?
- At what k-depth does the NJ baseline reach 70%+ coverage?

---

## Commits This Session

- `27f02ea` — checkpoint before ALGO-012
- `b7ef7c3` — ALGO-012 fine-grain BFS implementation

## Files Touched

`prompts.py`, `graph_discovery.py`, `call_logger.py`, `014-doc-algo-history.md`,
Obsidian algo-history, `Insurance_Prompt_v4.md`
