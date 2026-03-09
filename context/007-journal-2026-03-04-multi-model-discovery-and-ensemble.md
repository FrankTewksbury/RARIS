# Journal 007 — Multi-Model Discovery & Ensemble Validation

- **Date**: 2026-03-03 → 2026-03-04
- **Session**: Extended build + live testing marathon
- **Agent**: Claude Code (Opus 4.6)
- **Focus**: Fix V6 engine for live runs, add multi-model support, benchmark 6 models, prove ensemble strategy

---

## What Happened

### Starting Point

V6 RLM Queue-Driven BFS engine was code-complete (311 tests) but producing **0 results** in live testing. The engine was calling `complete_grounded()` which caused Gemini to enter tool-use mode and return `function_call` parts instead of JSON.

### The Debugging Gauntlet

Five cascading issues were diagnosed and fixed in sequence:

1. **Gemini function_call confusion** — `complete_grounded()` adds Google Search as a tool, causing Gemini to produce `function_call` parts instead of structured JSON. Fix: switched to `complete()` with `response_mime_type="application/json"`.

2. **Gemini thinking mode leak** — even without grounding, the thinking budget caused reasoning text to leak into the response instead of JSON. Fix: `response_mime_type="application/json"` forces pure JSON output.

3. **Entity dedup across sectors** — `fannie-mae` appeared in both federal and employer sectors, causing DB unique constraint violations. Fix: `seen_entity_ids` set before persist.

4. **L1 programs discarded** — the engine collected entities and sources from L1 sector results but silently dropped the `programs` array. Fix: added program harvesting with provenance tagging.

5. **State HFA scope too narrow** — prompt used unfilled `{STATE}` placeholder and singular "the STATE HFA". Fix: rewrote sector prompt with explicit list of all 50 states + DC + 5 territories.

### OpenAI Provider Rewrite

OpenAI's `gpt-5.2-pro` is a Responses API model, not Chat Completions. The entire provider was rewritten:
- `client.chat.completions.create()` → `client.responses.create()`
- `system` role → `developer` role
- `max_tokens` → `max_output_tokens`
- `response_format` → `text.format`
- Reasoning model detection to skip `temperature` for `gpt-5.2-pro`, `o1`, `o3`, `o4`

### Anthropic Streaming Fix

Anthropic SDK requires streaming for requests >10 minutes. With 32K max tokens and large prompts, every sector call hit this. Fix: `complete()` now uses streaming internally, collecting chunks into a string.

### Model Selection UI

Added per-request model selection — `PROVIDER_MODELS` map with 2 models per provider, dynamic dropdown that auto-resets on provider change, threaded through schema → registry → router → provider constructor.

---

## The Benchmark

Six models tested at k_depth=1 on identical DPA domain:

| Rank | Model | Programs | Notes |
|------|-------|----------|-------|
| 1 | **Claude Sonnet 4** | **227** | Best single model by far |
| 2 | GPT-4.1 | 146 | Strong, fast, cheap |
| 3 | Gemini 3.1 Pro | 101 | Solid baseline |
| 4 | GPT-5.2 Pro | 89 | Reasoning model — conservative, slow |
| 5 | Gemini 3 Flash | 56 | Too fast, too shallow |
| — | Claude Haiku 4.5 | (not tested) | — |

### Deep Run (Claude Sonnet 4, k_depth=3)

- L1: 202 entities across 6 sectors
- L2+L3 expansion: **1,105 programs** discovered
- State sector: 574 programs | National: 227 | City: 228 | Tribal: 54 | County: 22

### Ensemble Discovery (3 runs combined)

- **3,616 total** programs across all manifests
- **2,534 unique** (by name dedup)
- ~30% overlap = cross-model validation
- Each model finds things the others miss → ensemble > any single model

---

## Key Insight

**Ensemble multi-model discovery is the optimal strategy.** No single model covers the full landscape. Running 2-3 models and merging results produces 2x the unique findings of any individual run, with the overlap providing built-in confidence scoring.

---

## Files Changed

| File | Change |
|------|--------|
| `backend/app/agent/graph_discovery.py` | Switched to `complete()`, added entity dedup, L1 program harvesting, coverage from programs |
| `backend/app/agent/prompts.py` | Updated L0 system prompt to remove web search references |
| `backend/app/llm/openai_provider.py` | Full rewrite — Responses API, reasoning model detection |
| `backend/app/llm/anthropic_provider.py` | Streaming internally for `complete()` |
| `backend/app/llm/gemini_provider.py` | `response_mime_type` support in `_build_config()` |
| `backend/app/llm/registry.py` | `get_provider()` accepts model param |
| `backend/app/schemas/manifest.py` | Added `llm_model` field |
| `backend/app/routers/manifests.py` | Threaded `llm_model` through full pipeline |
| `frontend/src/components/DomainInputPanel.tsx` | Model dropdown with provider-dependent options |
| `frontend/src/components/ProgramsTable.tsx` | New — paginated table with filters |
| `frontend/src/components/CoverageSummary.tsx` | Labels updated for program-based coverage |
| `frontend/src/hooks/useSSE.ts` | Added `reset()` to clear stale events |
| `frontend/src/pages/Dashboard.tsx` | Wired ProgramsTable, SSE reset, loading state |
| `prompts/DPA_Prompt_v9.md` | All 50 states scope, removed unfilled placeholders |
| `prompts/DPA_Sectors_v3.json` | Explicit state list, broadened completeness requirements |

---

## Next Steps

1. **Ensemble Runs** — Sonnet 4.6 + GPT-4.1 at k_depth=3/4, maximize unique programs
2. **Master Manifest Merge** — combine all runs, cross-model confidence scoring
3. **Program Validation Pipeline** — the big challenge: normalize pages, fuzzy match, validate status/dates, extract properties/qualifications, validate links, discover application forms

---

## Metrics

- **Tests**: 311 passing (unchanged throughout)
- **Live runs**: 6+ successful discovery runs across 3 providers
- **Best single run**: 1,105 programs (Sonnet 4, k_depth=3)
- **Best ensemble**: 2,534 unique programs (3 runs combined)
- **Bugs fixed**: 7 (5 engine, 1 OpenAI API, 1 Anthropic timeout)
- **Session duration**: ~8 hours across 2 days
