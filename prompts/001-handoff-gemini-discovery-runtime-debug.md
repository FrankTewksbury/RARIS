---
type: handoff
created: 2026-03-01T08:21:04
sessionId: S20260301_0821
source: cursor-agent
description: Runtime debug handoff for Gemini-backed DPA discovery and municipal coverage gaps.
---

## Goal
Stabilize Gemini-backed DPA discovery runs (avoid zero-result failures), then improve municipal/local program recall and source verification yield for Stage-2 scraping readiness.

## Current runtime status (verified)
- Backend service is up and healthy on `:8000`.
- Gemini auth is working (`GEMINI_API_KEY` present in container).
- Gemini model default was updated to `gemini-3-pro-preview` (rule-aligned).
- One strong run completed with materially better breadth (`~166 sources`, active program extraction in batches).
- A later run failed mid-program enumeration due transient provider overload (`503 UNAVAILABLE`), leaving the manifest with zero persisted entities.

## Confirmed findings from logs
1. **Gemini significantly improves recall vs prior OpenAI runs**
   - Sources/programs increased by ~2x+ on successful runs.
2. **Municipal coverage remains under target**
   - Even improved runs can still over-index on state-level sources.
3. **Critical reliability bug**
   - Transient `503 UNAVAILABLE` from Gemini during `program_enumerator` currently aborts the run transaction.
   - Result: manifest ends in `pending_review` with `0` counts for that failed run.
4. **Runtime logging now works from Docker**
   - Backend debug writes to mounted host path `.cursor/debug-2fe1ec.log`.
   - This enables deterministic evidence for batch-level failure and municipal drop-off analysis.

## Root-cause summary
- **Primary immediate blocker:** missing resilient handling for transient Gemini `503` at program batch execution time.
- **Secondary quality gap:** municipal discovery/classification strategy still not strong enough relative to seed volume (local bodies/pages under-targeted or under-accepted).

## Code changes completed in this debug cycle
- `backend/app/llm/gemini_provider.py`
  - Default model moved to Gemini 3 series (`gemini-3-pro-preview` via config).
  - Added Gemini thinking budget config wiring.
- `backend/app/config.py`
  - Added `gemini_model` and `gemini_thinking_budget` settings.
- `.env.example`
  - Added `GEMINI_MODEL` and `GEMINI_THINKING_BUDGET`.
- `backend/app/agent/discovery.py`
  - Added/kept runtime instrumentation for landscape/source/program stages.
  - Added host-mounted NDJSON debug log write to `/workspace/.cursor/debug-2fe1ec.log`.
- `docker-compose.yml`
  - Added backend volume mount `./.cursor:/workspace/.cursor` to persist runtime debug logs to host.

## Priority work for planning mode
1. **Reliability first (P0): Gemini transient failure handling**
   - Catch `google.genai.errors.ServerError` / 503 in provider calls.
   - Add bounded retry with exponential backoff + jitter.
   - Add per-batch fallback model option (pro -> flash) for enumeration.
   - Prevent full-run rollback on single batch failure (batch isolation + partial persistence strategy).
2. **Municipal coverage lift (P1)**
   - Enforce a dedicated municipal expansion pass (Layer-2) across major city/county housing entities.
   - Relax source acceptance to include valid local program landing pages when regulator-document style pages are absent.
   - Add explicit tribal/NAHASDA and local housing authority targeting prompts.
3. **Verification diagnostics (P1)**
   - Emit counters for seeded -> source-verified attrition by geo scope.
   - Persist drop reasons (no source URL, no source_id, no evidence snippet).

## Suggested first implementation slice
- Implement P0 only first:
  - Retry/fallback in Gemini provider + per-batch guard in `program_enumerator`.
  - Re-run same scenario to confirm no more zero-result manifests from transient 503.
  - Keep instrumentation active through validation.

## Validation checklist for next executor
- Trigger one Gemini run with the same seed file and controls.
- Confirm no `Agent run failed` due to 503.
- Confirm manifest has non-zero `sources_count`/`programs_count` at completion.
- Review `.cursor/debug-2fe1ec.log` for:
  - source jurisdiction distribution
  - program batch timings/counts
  - any retry/fallback activation markers

## Files of interest for immediate planning
- `backend/app/llm/gemini_provider.py`
- `backend/app/agent/discovery.py`
- `backend/app/agent/prompts.py`
- `backend/app/routers/manifests.py`
- `docker-compose.yml`
- `.cursor/debug-2fe1ec.log`
