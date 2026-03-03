# Handoff: V6 RLM Queue-Driven BFS Engine Rewrite

**Date:** 2026-03-03
**Session:** S20260303_v6_rlm
**Agent:** Claude Code (Opus 4.6)
**Status:** BUILD COMPLETE — 311 tests passing

---

## What Was Done

V6 rewrites the discovery engine from a static 2-level BFS (V5: hardcoded L1→L2) to a
queue-driven recursive BFS (RLM pattern). Patterns ported from
`X:\VibeRepo\ZaroRepo\backend\Tests\prepop1\ontology_engine.py`.

### Files Created

| File | Purpose |
|------|---------|
| `backend/app/agent/discovery_queue.py` | Priority BFS queue with visited-set dedup, max_depth/max_size enforcement |
| `backend/app/llm/call_logger.py` | Structured LLM call logging (Track A fields), [STAGE]/[HEARTBEAT] formatters |
| `prompts/DPA_Prompt_v9.md` | Fixed instruction file — typo corrections, "RLM Queue Engine" title |
| `prompts/DPA_Sectors_v3.json` | Extended sector config — added `sector_prompt` and `expected_entity_types` per sector |

### Files Modified

| File | Changes |
|------|---------|
| `backend/app/config.py` | Added safety caps (`max_api_calls`, `max_discovery_depth`, `max_entities_per_sector`) and LLM logging toggles (`llm_logging`, `llm_log_prompts`) |
| `backend/app/agent/graph_discovery.py` | **Full V6 rewrite** — queue-driven BFS loop, sector prompt injection, safety caps, [STAGE]/[HEARTBEAT] emissions |
| `backend/app/routers/manifests.py` | Fixed `_parse_sector_upload()` to pass through `completeness_requirements`, `sector_prompt`, `expected_entity_types` |
| `backend/app/llm/gemini_provider.py` | Added structured call logging around `complete()`, `stream()`, `complete_grounded()` |
| `backend/app/llm/anthropic_provider.py` | Added structured call logging around all 3 methods |
| `backend/app/llm/openai_provider.py` | Added structured call logging around all 3 methods |

---

## Architecture: V5 → V6 Delta

### V5 (what it was)
- L1: 6 parallel sector calls → entities
- L2: `_run_l2_entity_expansion()` loops over entities sequentially
- Two hardcoded levels, no recursion, no queue, no depth tracking

### V6 (what it is now)
- L1: N parallel sector calls → entities seeded into `DiscoveryQueue` at depth=1
- L2+: `while not queue.is_empty()` loop pops entities, expands them, enqueues sub-entities at depth+1
- `DiscoveryQueue`: priority heap with visited-set dedup, ordered by (priority, depth, _seq)
- `k_depth` maps to queue max_depth: `k_depth=1` → L1 only, `k_depth=2` → L1+L2, `k_depth=3` → L1+L2+L3
- Safety caps enforced from config: `max_api_calls=200`, `max_discovery_depth=3`, `max_entities_per_sector=50`

### Sector Prompt Injection
- `DPA_Prompt_v9.md` contains `[INJECT SECTOR PROMPT HERE]` placeholder
- `DPA_Sectors_v3.json` defines `sector_prompt` per sector
- `_inject_sector_prompt()` replaces the placeholder before building the full prompt
- Previously: sector files only had `key`, `label`, `priority`, `search_hints`
- Now: also carry `completeness_requirements`, `sector_prompt`, `expected_entity_types`

### LLM Call Logging
- `call_logger.py`: `LLMCallRecord` dataclass + `log_llm_call_start/success/error` functions
- Track A fields: provider, model, method, stage, run_id, manifest_id, prompt_chars, response_chars, duration_ms, error_code, retry_attempt, fallback_model
- `log_stage()` emits `[STAGE] <name> status=<status> model=<model> sources=<N> programs=<N>`
- `log_heartbeat()` emits `[HEARTBEAT] stage=<name> batch=<n/total> items_so_far=<N> elapsed_s=<N>`
- All 3 providers (Gemini, Anthropic, OpenAI) instrumented with before/after/error logging
- Controlled by `settings.llm_logging` (ON|OFF) and `settings.llm_log_prompts` (ON|OFF)

### SSE Events (unchanged for frontend compatibility)
- `sector_start`, `sector_complete` — per L1 sector
- `l1_assembly_complete` — after all sectors merged
- `entity_expansion_start`, `entity_expansion_complete` — per queue item
- `complete` — final with coverage_summary + queue_stats + seed metrics

New data fields in events: `queue_stats`, `api_calls`, `depth`, `queue_pending`, `children_enqueued`

---

## Bug Fixes in This Session

1. **Sector parser dropping fields** — `_parse_sector_upload()` only kept 4 fields, silently dropping `completeness_requirements`. Fixed to pass through all fields.
2. **Prompt placeholder typo** — v8 had `[INJECT SECTOR PRROMPT HERE]` (double R) and `FERERAL` typo. Fixed in v9.
3. **Sector config typos** — v2 had "Home Load" → "Home Loan", "FreddieNAc and FannieNae" → "Freddie Mac and Fannie Mae". Fixed in v3.

---

## What's Next

- [ ] Live test run with k_depth=1 — verify all sectors return entities > 0
- [ ] Live test run with k_depth=2 — confirm queue expansion discovers programs
- [ ] AuthorityType DB migration (state_hfa, municipal, pha, nonprofit, cdfi, employer, tribal)
- [ ] Frontend: surface queue stats (depth, pending, api_calls) in AgentProgressPanel
- [ ] Evaluate [HEARTBEAT] timing — currently emits every 3rd entity if >30s elapsed

---

## Test Results

```
311 passed, 1 warning in 57.14s
```

All existing tests pass unchanged. No new test files added (engine rewrite is
structurally compatible with existing V5 test mocks).
