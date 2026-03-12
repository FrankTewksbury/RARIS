---
type: journal
created: 2026-03-12T12:00:00
sessionId: S20260312_0300
source: cursor-agent
description: Session journal — crash fixes, depth_hint repair, 409 loop root cause, checkpoint validation
---

# Session Journal — 2026-03-12 — Crash Fixes, depth_hint Repair, Checkpoint Validation

## Session Goal

Fix the three compounding issues that crashed the last resumed run, validate checkpoints fire correctly,
then investigate and repair the root cause of low NJ recall.

---

## What Was Done

### 1. Fix Session Crash, ID Truncation, API Cap (Plan implemented)

- **Alembic migration 009** — widened `sources.id`, `sources.regulatory_body_id`, `regulatory_bodies.id`
  from `VARCHAR(100)` → `VARCHAR(255)`. Postgres live-safe ALTER with no table rewrite.
- **Model updates** — `String(100)` → `String(255)` in `Source` and `RegulatoryBody` ORM definitions.
- **Session rollback** — Added `await self.db.rollback()` as first line in both outer `except` handlers
  in `run()` and `run_resumed()`. Clears poisoned session state after any flush error so subsequent
  nodes can proceed independently.
- **API call cap** — Raised `max_api_calls` 1500 → 3000 in `config.py`.
- **UI cap indicator** — Fixed hardcoded `1500` in `Dashboard.tsx` and `AgentProgressPanel.tsx` → `3000`.
- **Commit:** `e3f6c87` — pushed to `main`.

### 2. Checkpoint Bug Fixed

**Root cause:** `_write_checkpoint()` reused `self.db` — the same long-lived SQLAlchemy session shared
across the entire L2 expansion loop. After hundreds of flush/commit cycles writing sources and programs,
the `Manifest` ORM object in that session became stale. `db.get(Manifest, id)` returned an expired
instance and the subsequent `db.commit()` silently no-ops.

**Fix:** `_write_checkpoint()` now opens a **fresh `async with _async_session_factory() as fresh_db`**
session exclusively for the checkpoint write. Completely isolated from the long-lived loop session.
Wrapped in outer `except` so a bad checkpoint never brings down the run.

**Validation:** Checkpoint batch 20 written at 11:27 UTC with 30 items remaining — confirmed working.

### 3. Run Completed

The run completed for the first time end-to-end after the `__import__("sqlalchemy").table("programs").c.id`
crash was fixed. That broken expression at line 1024 of `run_resumed()` was attempting to count existing
programs via a malformed low-level SQLAlchemy reflection. Fixed with a proper ORM query:
`select(func.count()).select_from(Program).where(Program.manifest_id == self.manifest_id)`.

### 4. NJ Baseline Comparison — Root Cause Found

Compared completed run against `research/NJ-example_statutes.md` (30-item baseline).

**Result: ~12/30 (40%)** — not the 70%+ target.

**Root cause discovered:** All 4 L1 insurance prompts (`1-Insurance_Prompt_v5.md` through `4-Insurance_Prompt_v5.md`)
were missing `depth_hint` from their `sources[]` output schema. The L2 expansion templates in `prompts.py`
instruct the LLM to classify each source with `depth_hint`, but the L1 prompts never asked for it.

As a result:
- **499 of 1,005 sources had `depth_hint = NULL`** across all jurisdictions
- BFS enqueue logic requires `depth_hint IN ('title','chapter','section')` to re-enqueue a source
- Every L1-seeded statute/regulation was treated as a leaf and never expanded
- All 50 states + territories had the same problem — not just NJ

**Fix:**
1. Added `"depth_hint": "title|chapter|section|leaf"` field to `sources[]` schema in all 4 prompt files.
2. Added classification rule to QUALITY RULES section of each prompt.
3. Updated all 499 NULL rows in DB: `statute/regulation` → `title`, `guidance/standard` → `leaf`.
4. Wrote new BFS checkpoint with 391 queue items using correct `target_type`/`target_id` shape.

### 5. 409 Loop / Backend Stop Pattern

Recurring issue: when a run fails mid-execution, the manifest ID stays in the in-memory `_event_queues`
dict. Every subsequent Resume click returns 409 Conflict because the key is still registered.

**Workaround (current):** `docker compose stop backend && docker compose up -d backend` — full process kill
clears `_event_queues`. `docker compose restart` is NOT sufficient because uvicorn waits for background
tasks to complete before exiting, keeping the old task alive.

**Permanent fix needed:** Cancel/stop API route that removes the manifest ID from `_event_queues` and
sets status back to `pending_review`. Added to TODO.

### 6. Repair Script Written

`backend/scripts/repair_depth_hint_checkpoint.py` — one-time repair script for manifests missing
`depth_hint`. Also added `backend/scripts/write_checkpoint.sql` for direct DB checkpoint injection.
`scripts/` directory needs to be added to the backend Dockerfile COPY list.

---

## Decisions

- **depth_hint is mandatory in L1 prompts** — without it the BFS engine treats everything as a leaf.
  All future prompts must include it in the sources schema.
- **`_write_checkpoint` must use a fresh session** — long-lived session pattern is incompatible with
  periodic checkpoint writes. This is now the established pattern.
- **Full stop/start vs restart** — for emergency stops, always use `stop` + `up -d`, never `restart`.

---

## Current State

- Run resumed with 391 title-level sources queued for chapter expansion
- Checkpoints firing correctly (fresh session pattern confirmed working)
- All 4 L1 prompt files patched with `depth_hint` field and classification rule
- `max_api_calls = 3000`, `VARCHAR(255)` IDs, session rollback all live on `main`

---

## Next Actions

- [ ] Monitor run — verify NJ sub-chapter sources appear (17:27A, 17B:25, 17B:26 etc.)
- [ ] Re-run NJ baseline comparison after this expansion pass completes
- [ ] Add `scripts/` to backend Dockerfile COPY list
- [ ] Build cancel/stop API route to fix 409 loop permanently
- [ ] Citation normalization batch pass (see `context/012-note-citation-normalization-cleanup.md`)
