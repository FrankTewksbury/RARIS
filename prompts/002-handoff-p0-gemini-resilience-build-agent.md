---
type: handoff
created: 2026-03-01T08:50:56
sessionId: S20260301_0821
source: cursor-agent
description: Execution handoff aligned to the approved Gemini resilience and Docker observability plan.
---

## Objective
Execute the approved P0 stabilization work first, then proceed to Docker transparency work in the agreed two-track model.

## Authoritative Plan Reference
- Agreed plan file: [c:\Users\frank\.cursor\plans\gemini_resilience_planning_cfdbaf29.plan.md](c:\Users\frank\.cursor\plans\gemini_resilience_planning_cfdbaf29.plan.md)
- This handoff is implementation-focused and must stay aligned to that plan.

## Runtime Evidence Baseline (must preserve)
- Gemini can authenticate and run.
- A successful run shows materially better breadth (high source/program counts).
- Reproduced failure case: `503 UNAVAILABLE` during `program_enumerator` causes run abort and zero persisted results for that manifest.
- Backend debug instrumentation is active and writes to `.cursor/debug-2fe1ec.log` via mounted Docker volume.

## Scope For New Build Agent
### P0 - Execute First (blocking)
1. Add resilient Gemini error handling in provider calls:
   - Retry with bounded exponential backoff + jitter.
   - Retryable: `429`, `500`, `502`, `503`, `504`, and transient transport/timeouts.
   - Non-retryable fail-fast: `400`, `401`, `403`, `404` (except optional one-time alias remap for model-not-found flow if implemented in plan).
2. Add ordered model fallback for retryable overload/availability cases:
   - Start at configured primary model; downgrade by configured chain.
3. Isolate program-enumerator batch failures:
   - A failed batch cannot abort the entire run.
   - Continue remaining batches and log skip/partial metrics.
4. Ensure partial persistence safety:
   - Late-stage Gemini failures must not zero out already discovered sources.

### Rules Alignment
Update Gemini rule content so it matches current `python-genai` behavior and plan intent:
- Replace outdated exception examples with `from google.genai import errors` and `errors.APIError`.
- Include explicit error code matrix and action policy.
- Include downgrade/fallback policy guidance.

### Docker Transparency (agreed two-track)
1. **Track A (project now):** implement project-level near-real-time monitoring and print/logging standards.
2. **Track B (global later):** produce reusable global Docker rule artifact for future projects and phase-2 adoption here.

## Files To Touch (expected)
- `backend/app/llm/gemini_provider.py`
- `backend/app/agent/discovery.py`
- `backend/app/routers/manifests.py` (only if needed for status semantics)
- `.cursor/rules/gemini-model-rules.mdc`
- `.cursor/rules/log-file-rule.mdc` (project-level Docker observability section)
- New global Docker rule artifact path (to be defined in execution phase)

## Validation Gates (must pass before close)
1. Reproduce the prior failing run profile.
2. Confirm no full-run abort on transient Gemini `503`.
3. Confirm non-zero persisted output even if a program batch is skipped/fails.
4. Confirm retry/fallback telemetry appears in `.cursor/debug-2fe1ec.log`.
5. Confirm rules documentation reflects implemented runtime behavior.
6. Confirm project-level Docker monitoring workflow works in near real time.

## Execution Notes
- Keep instrumentation active through verification.
- Do not remove debug logs until post-fix validation confirms stability.
- Keep changes minimal and evidence-driven; avoid municipal-expansion prompt work until P0 reliability is complete.
