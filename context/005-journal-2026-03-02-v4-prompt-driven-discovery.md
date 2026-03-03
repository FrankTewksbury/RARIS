---
type: journal
created: 2026-03-02T18:50:00
sessionId: S20260302_1400
source: cursor-agent
description: DPA V4 Prompt-Driven Discovery — full build complete, 306 tests passing
---

# Journal — 2026-03-02 — V4 Prompt-Driven Discovery Build Complete

## What We Built

Completed the DPA V4 Prompt-Driven Discovery engine, a full architectural rewrite of the V3
hierarchical discovery engine (`graph_discovery.py`). Implemented all 9 commits from handoff
`prompts/004-handoff-discovery-v4-prompt-driven.md`.

### Core Architecture Change

- **V3 flaw:** Generic hardcoded prompts drove L0 discovery. The rich domain methodology in
  `DPA_Prompt_v4.md` was passive context, never actually steering the LLM. Result: 15 programs,
  0 sources.
- **V4 fix:** The uploaded instruction prompt IS the L0 user message. L1-L3 prompts are
  dynamically built from L0 output data (bodies, sources, programs discovered). No static
  domain knowledge in engine code.

### Deliverables

1. `docs/005-doc-base-instruction-template.md` — Canonical 7-section template for all V4
   instruction prompts. Enforces domain knowledge over execution logic.
2. `prompts/DPA_Prompt_v5.md` — DPA instruction prompt rewritten (~150 lines) following the
   template contract. No execution logic, pure domain knowledge.
3. `backend/app/agent/prompts.py` — V4 prompt set: `L0_ORCHESTRATOR_SYSTEM`,
   `L0_JSON_SCHEMA_SUFFIX`, `L1_ENTITY_EXPANSION_PROMPT`, `L2_VERIFICATION_PROMPT`,
   `L3_GAP_FILL_PROMPT`. Backward compat: `GUIDANCE_CONTEXT_BLOCK` preserved for V2 flat
   pipeline.
4. `backend/app/schemas/manifest.py` — `domain_description` → `manifest_name` rename.
5. `backend/app/routers/manifests.py` — All `domain_description` → `manifest_name` plumbing.
   Added warning log when `instruction_file` is missing in hierarchical mode.
6. `frontend/src/components/DomainInputPanel.tsx` — Field rename + updated placeholder.
7. `backend/app/agent/graph_discovery.py` — Full V4 rewrite: `_l0_discovery()`,
   `_run_l1_expansion()`, `_run_l2_verification()`, `_l3_gap_fill()`. Timeouts: 300s L0,
   180s L1-L3. All items persisted; low-confidence flagged with `needs_human_review: true`.
8. `backend/tests/` — New `test_graph_discovery_v4.py` (8 tests), updated `test_graph_discovery.py`
   (17 tests), `test_manifest_schema.py`, `test_api_integration.py`.
9. `backend/Dockerfile` + `backend/.dockerignore` — pytest/dev deps in container via
   `uv sync --all-extras`; `tests/` directory added to image.

## Bugs Encountered and Fixed

### Bug 1: `GUIDANCE_CONTEXT_BLOCK` deletion
- Deleted during V4 prompt cleanup; still needed by `discovery.py` (V2 flat pipeline).
- Fix: re-added to `prompts.py` for backward compatibility.

### Bug 2: `SyntaxError` in `L3_GAP_FILL_PROMPT`
- Unterminated triple-quoted string.
- Fix: added missing closing `"""`.

### Bug 3: pytest not in Docker container
- `uv sync --no-dev` doesn't install pytest; `tests/` not in Dockerfile COPY.
- Fix: `uv sync --all-extras --no-install-project` + `COPY tests/ tests/`.

### Bug 4: `COPY tests/ tests/` blocked by `.dockerignore`
- `tests/` was listed in `backend/.dockerignore`.
- Fix: removed the `tests/` line from `.dockerignore`.

### Bug 5: `ImportError` in `test_graph_discovery.py`
- V3 test imported `_ENTITY_SEARCH_QUERIES`, removed in V4.
- Fix: removed import, updated MockLLM to return V4-compatible responses, updated assertions.

### Bug 6 (Root Cause): `MockLLM` routing L0 → L2 branch
- The L0 execution instructions contain "verify" (e.g., "verify all entities via web search").
- `MockLLM.complete_grounded` routed on `"verify" in prompt.lower()` → returned
  `'{"verifications": []}'` instead of the L0 regulatory bodies response.
- `bodies = l0_result.get("regulatory_bodies", [])` → `[]` → `if k_depth >= 2 and bodies:`
  evaluated `False` → L1 skipped → levels seen `{0, 2, 3}` not `{0, 1, 2, 3}`.
- Root cause identified by: running `_l0_discovery` in isolation (works), running the full
  `run()` generator in isolation (works), then checking L0 prompt text against all routing
  conditions (found "verify" match).
- Fix: changed routing condition from `"verify"` to `"programs to verify"` (unique to the L2
  verification prompt, not present in L0 execution instructions).

## Final Test Count

**306 tests across 25 test files — all passing.**

## Lessons Learned

1. **Mock routing must be specific.** Any mock that routes on generic English words found in
   many prompt templates will break. Routing conditions should match phrases unique to the
   specific prompt branch (e.g., "programs to verify" not "verify").

2. **Isolate before integrating.** Running `_l0_discovery()` in isolation proved it worked.
   Running the full `run()` generator in isolation also proved it worked. The failure was
   therefore in the test mock, not the engine. This narrowed the search dramatically.

3. **asyncio.wait_for wrapping a generator requires care.** The L0 timeout wraps
   `_l0_discovery()` which is a coroutine (not an async generator), so `wait_for` works
   correctly here. Wrapping async generators with `wait_for` doesn't work the same way.

4. **Backward compat checks matter.** Deleting `GUIDANCE_CONTEXT_BLOCK` seemed safe (not
   referenced in the V4 engine) but broke the V2 flat pipeline. Always grep for usages
   before deleting shared constants.

## What's Next

- V4 baseline validation run: DPA_Prompt_v5 + hierarchical mode + no seed file → target 200+
  programs with real sources.
- Seed file validation: after baseline confirmed, run with seed file → target 50%+ seed
  recovery rate.
- Frontend: surface `discovery_level`, per-topic match rates, and cumulative progress in
  results panel.
