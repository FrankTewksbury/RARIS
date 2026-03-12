---
type: journal
created: 2026-03-11T02:30:00
sessionId: S20260311_0000
source: cursor-agent
description: Session implementing cap raise, live API counter, checkpoint/resume system
---

# Session Journal — Cap Raise, API Counter, Checkpoint/Resume

## What Was Built

Full implementation of the "Cap Raise, API Counter UI, and Checkpoint Resume" plan (9 items, all completed).

### 1. Cap Raise
- `backend/app/config.py`: `max_api_calls` raised from 500 → 1500

### 2. Live API Call Counter (Backend)
- `backend/app/agent/graph_discovery.py`: Added `api_calls=self._api_calls` to:
  - `entity_expansion_complete` (success + failure paths)
  - `l1_assembly_complete`

### 3. Live API Call Counter (Frontend)
- `frontend/src/types/manifest.ts`: Extended `AgentStepEvent` with `api_calls`, `type`, `batch_n`, `items_remaining`. Added `checkpoint_data` to `ManifestDetail`.
- `frontend/src/hooks/useSSE.ts`: Added `apiCalls` and `lastCheckpoint` state; tracks `api_calls` from SSE events; added `checkpoint_written` listener.
- `frontend/src/components/AgentProgressPanel.tsx`: Added `apiCalls`, `maxApiCalls`, `lastCheckpoint`, `hasCheckpoint`, `onResume` props. Displays `API calls: N / 1500` badge, checkpoint events with `⊙` marker, and Resume button when checkpoint exists.
- `frontend/src/pages/Dashboard.tsx`: Wired `handleResume` that calls `POST /api/manifests/{id}/resume`; passes new props to `AgentProgressPanel`.

### 4. DB Schema
- `backend/app/models/manifest.py`: Added `checkpoint_data: Mapped[dict | None] = mapped_column(JSONB, nullable=True)`
- `backend/alembic/versions/006_add_checkpoint_data.py`: New migration `006`
- `backend/alembic/env.py`: Updated to read `DATABASE_URL` env var (was hardcoded to localhost — broke container-based migration)
- Migration applied to live Postgres DB (stamped at `005_jurisdiction_code`, upgraded to `006`)

### 5. DiscoveryQueue Snapshot
- `backend/app/agent/discovery_queue.py`:
  - `to_snapshot()` — serializes `_heap` items + `_visited` set to JSON-safe dict
  - `from_snapshot(cls, snapshot)` — class method; rehydrates queue restoring heap order + visited set

### 6. Checkpoint Engine
- `backend/app/agent/graph_discovery.py`:
  - `_write_checkpoint(queue, type, batch_n, api_calls_used)` — async method; persists snapshot to `manifest.checkpoint_data`, commits, returns `checkpoint_written` SSE event dict
  - L1 boundary call: after `l1_assembly_complete` is yielded
  - L2 periodic call: every 50 items (`entity_n % 50 == 0`)
  - `run_resumed(manifest_name, *, checkpoint, k_depth)` — new async generator; skips L1, restores queue from snapshot, runs L2 expansion, persists new programs, commits

### 7. Resume Route
- `backend/app/routers/manifests.py`:
  - `_run_agent_resumed()` — background task wrapper for `run_resumed()`
  - `POST /api/manifests/{id}/resume` — 404 if not found, 409 if no checkpoint or active queue, 202 with stream_url if checkpoint present
- `backend/app/schemas/manifest.py`: Added `checkpoint_data: dict | None` to `ManifestDetail` Pydantic schema
- `backend/app/services/manifest_service.py`: Passes `checkpoint_data` through in `get_manifest()` → `ManifestDetail`

### 8. Tests Added
- `test_graph_discovery.py::TestCheckpointQueue` — 5 tests: snapshot round-trip, priority order, visited set, plan-spec shape
- `test_graph_discovery.py::TestResumeRoute` — 3 tests: resume_start/complete events, queue item processing, visited set restoration
- `test_api_integration.py` — 3 new tests: 404, 409, 202 for resume route; fixed import issues using `TestSession` for proper SQLite test isolation

**Total: 89 graph/engine tests + 47 integration tests = 136 tests, all passing**

## Decisions
- `run_resumed()` is a separate method (not a flag on `run()`). Clean separation avoids bloating the L1 path and makes testing simpler.
- Alembic `env.py` updated to honour `DATABASE_URL` env var — this was a latent bug that would have broken any future migrations run from inside Docker containers.
- Resume test uses `TestSession` directly (not `get_db()`) to avoid writing to Postgres while route reads from SQLite override.

## Files Changed
- `backend/app/config.py`
- `backend/app/agent/graph_discovery.py`
- `backend/app/agent/discovery_queue.py`
- `backend/app/models/manifest.py`
- `backend/app/schemas/manifest.py`
- `backend/app/services/manifest_service.py`
- `backend/app/routers/manifests.py`
- `backend/alembic/versions/006_add_checkpoint_data.py` (NEW)
- `backend/alembic/env.py`
- `backend/tests/test_graph_discovery.py`
- `backend/tests/test_api_integration.py`
- `frontend/src/types/manifest.ts`
- `frontend/src/hooks/useSSE.ts`
- `frontend/src/components/AgentProgressPanel.tsx`
- `frontend/src/pages/Dashboard.tsx`

## Next Steps
- Run a real multi-prompt insurance discovery with the new 1500 cap
- Observe checkpoint events in the UI
- If run hits cap again, test the Resume button
- Consider adding `instruction_texts` persistence to the manifest so the resume route can re-use them (currently resume relies on existing entities in DB, which is correct for L2-only resume)
