# Active Context

- Updated: 2026-03-12
- Current focus: **Insurance Domain V7.2 / ALGO-014** — validated 90% NJ recall; ready for full run with dynamic context injection
- Agent constitution: [CLAUDE.md](../CLAUDE.md)
- Operating manual: [docs/DFW-OPERATING-MANUAL.md](../docs/DFW-OPERATING-MANUAL.md)

## Current State

ALGO-014 validated. Dynamic sibling context injection confirmed working — N.J.A.C. 11:2 (Claims),
11:17 (Producer Licensing), 11:17A/B/C/D (Producer Conduct) all found in targeted single-call test.
NJ recall: **90% (27/30)**. Remaining 3 misses are cross-title statutes outside NJDOBI scope.

### NJ Recall History
| Version | Recall | Notes |
|---------|--------|-------|
| Pre-ALGO-013 | 40% (12/30) | depth_hint NULL on all L1 sources |
| Post-ALGO-013 | 77% (23/30) | depth_hint repair + chapter expansion |
| Post-ALGO-014 | **90% (27/30)** | dynamic sibling context injection |

### Session Changes (2026-03-12 continued)

#### ALGO-014 — Dynamic Context Injection (this commit)
- `DOMAIN_CHAPTER_HINTS` lookup table in `prompts.py` — keyed by `(domain_key, source_type)`
- `build_sibling_context()` — assembles "already found / watch for" injection block
- `build_expansion_prompt()` — gains `sibling_context` param; appended to source node prompts
- `_expand_node()` — queries DB siblings + domain hints before each `source_title`/`source_chapter` call
- `src_meta` — gains `id` and `type` fields for domain hint lookup
- All 4 L1 insurance prompts — `depth_hint` field added to sources[] schema
- UI API cap fixed: 1500 → 3000 in Dashboard.tsx and AgentProgressPanel.tsx
- Session journal: `context/013-journal-2026-03-12-crash-fixes-depth-hint-repair.md`

## What's Next

### Immediate
- [ ] Full insurance run with ALGO-014 active — all 391 title sources expanded with sibling context
- [ ] Add `scripts/` to backend Dockerfile COPY list
- [ ] Build cancel/stop API route (fix 409 loop permanently)
- [ ] Citation normalization batch pass (see `context/012-note-citation-normalization-cleanup.md`)
- [ ] EXP-001: restore `complete_grounded()` for L2+ to improve recall on obscure statutes

## Current State

Resumed run active. 391 undrilled title-level sources (all 50 states + territories + federal) now
queued for BFS chapter expansion after depth_hint repair. Checkpoints confirmed firing correctly
(fresh session pattern). Backend stable on commit `e3f6c87` (main).

### Run in Progress

- Manifest: `raris-manifest-insurance---domain-regulations-20260311023257`
- Status: `generating`
- Queue: 391 title sources → chapter expansion
- Model: Gemini 3 Flash (gemini-3-flash-preview)
- k_depth: 3
- Checkpoints: every 50 items, fresh session write (ALGO-013 fix confirmed working)

### NJ Baseline Analysis (pre-repair)

- Sources found: 13 NJ sources
- Recall: ~12/30 baseline (40%)
- Root cause: `depth_hint = NULL` on all 499 L1-seeded sources → treated as leaves, never expanded
- After repair: 391 title sources now queued; NJ chapter sources (17:27A, 17B:25, 17B:26...) expected

### Session Changes (2026-03-12)

#### ALGO-013 — Crash Fixes + depth_hint Repair (commit `e3f6c87`)
- Widened VARCHAR(100) → VARCHAR(255) for sources.id, regulatory_bodies.id (migration 009)
- Added session rollback to both outer except handlers in run() and run_resumed()
- Fixed _write_checkpoint() to use fresh DB session (was silently failing with stale self.db)
- Raised max_api_calls 1500 → 3000
- Fixed broken program count query at run_resumed() completion
- Added depth_hint field + classification rule to all 4 L1 insurance prompt files
- Repaired 499 NULL depth_hint rows in DB; wrote corrected 391-item checkpoint
- Fixed UI API cap indicator (hardcoded 1500 → 3000 in Dashboard.tsx + AgentProgressPanel.tsx)

## What's Next

### Immediate
- [ ] Monitor current run — verify NJ sub-chapter sources appear (17:27A, 17B:25, 17B:26 etc.)
- [ ] Re-run NJ baseline comparison after expansion pass completes — target 70%+
- [ ] Add `scripts/` to backend Dockerfile COPY list
- [ ] Build cancel/stop API route (fix 409 loop permanently — no more manual stop/start)
- [ ] Citation normalization batch pass (see `context/012-note-citation-normalization-cleanup.md`)

### Known Issues
- **409 loop on failed resume** — backend must be fully stopped (`stop` + `up -d`) not restarted;
  `restart` keeps uvicorn background tasks alive, keeping `_event_queues` populated
- **scripts/ not in Dockerfile** — repair scripts must be `docker compose cp`'d into container manually



## Current State

V6 RLM BFS engine is production-ready with multi-provider, multi-model support. Live testing across 6 models complete. Anthropic Claude Sonnet 4 is the clear winner for discovery yield.

### Model Comparison Results (k_depth=1)

| Provider | Model | Programs Found |
|----------|-------|---------------|
| Anthropic | Claude Sonnet 4 | **227** |
| OpenAI | GPT-4.1 (fast) | 146 |
| Gemini | Gemini 3.1 Pro | 101 |
| OpenAI | GPT-5.2 Pro (reasoning) | 89 |
| Gemini | Gemini 3 Flash | 56 |

### Multi-Depth Run (Claude Sonnet 4, k_depth=3)

- **1,105 programs** discovered in single run
- 202 entities across 6 sectors at L1
- L2/L3 expansion yielded 5x program growth

### Cross-Model Ensemble (3 runs combined)

- **3,616 total** programs across all runs
- **2,534 unique** programs (by name dedup)
- ~30% overlap = cross-model validation signal

## Session Changes (2026-03-04)

### Engine Fixes
- Switched discovery from `complete_grounded()` to `complete()` with `response_mime_type="application/json"` — fixed Gemini returning function_call parts instead of JSON
- Added entity dedup (`seen_entity_ids` set) to prevent DB constraint violations
- Added L1 program harvesting — was only collecting entities/sources, discarding programs
- Broadened state_hfa sector to explicitly list all 50 states + DC + 5 territories
- Bumped sector timeout 600s → 900s for reasoning models

### OpenAI Provider Rewrite
- Rewired from Chat Completions API → Responses API (`client.responses.create()`)
- `system` role mapped to `developer` for Responses API
- `max_tokens` → `max_output_tokens`, `response_format` → `text.format`
- Reasoning model detection — skip `temperature` for `gpt-5.2-pro`, `o1`, `o3`, `o4`

### Anthropic Provider Fix
- `complete()` now uses streaming internally to avoid 10-min timeout on long requests

### Model Selection UI
- Added `PROVIDER_MODELS` map with 2 models per provider (6 total)
- Model dropdown auto-resets when provider changes
- `llm_model` threaded through: schema → registry → router → provider constructor

### Coverage Assessment Fix
- Now builds from programs (geo_scope + status) instead of empty sources
- Charts show "By Geo Scope" and "By Status"

### Frontend Fixes
- Added `ProgramsTable` component with filters and pagination
- Added SSE `reset()` — clears stale progress panel when selecting sidebar manifests
- Added loading state for manifest detail fetch

## Session Changes (2026-03-10)

### ALGO-012 — Fine-Grain BFS Recursion (commit `b7ef7c3`)
- Replaced monolithic exhaustive-enumeration prompt with 13 node-type-keyed single-question templates
- Source nodes enter BFS queue via `depth_hint` field (`title|chapter|section|leaf`)
- `_expand_entity()` → `_expand_node()` — dispatches by `node_type`
- `[RUN-{timestamp}]` tag on all log output for run correlation
- Confirmed working: `NODE EXPANSION — DEPTH L3 [source_title]` firing; 284 queue items in live run

### ALGO-012 Validation Run (`20260310183101`) Results
- State dept coverage: 41/52 (79%) — 11 states missed (RI, SC, SD, TN, UT, VA, VT, WA, WI, WV, WY + DC)
- Federal/national: 11/11 (100%)
- Industry/trade: 5/17 (29%)
- NJ DOBI L2 expansion returned zero sources — `node:entity:regulator` template too strict

### Cap + Template Fixes Applied (2026-03-10 EOD)
- Raised `max_entities_per_sector` 50 → 200 in `backend/app/config.py` and `graph_discovery.py` default
- Added near-cap proximity warning (>80% of cap) in `_run_l1_sectors()`
- Loosened `node:entity:regulator` template in `prompts.py`: now asks for titles AND immediate chapters, allows `depth_hint='chapter'`, includes fallback guidance for uncertain models

## What's Next

### Immediate — Next Session
- [ ] Rebuild backend container with cap + template fixes
- [ ] Run k=3 with seed file (`Insurance_seed_v1.md`) on Gemini Flash
- [ ] Compare against NJ baseline (`research/NJ-example_statutes.md`) — target 70%+ coverage
- [ ] Verify `depth_hint` persisted on source rows from NJ DOBI expansion
- [ ] Consider EXP-003 (source dedup by `(name, entity_id)`) if 5x duplicates persist



### Insurance V3 Engine Wiring
- Fixed `authority_type` field mapping bug — was reading `entity_type` key, now reads `authority_type` with `entity_type` fallback
- Added 5 new `AuthorityType` enum values: `residual_market_mechanism`, `compact`, `advisory_org`, `actuarial_body`, `trade_association`
- Widened `regulatory_bodies.authority_type` column from `VARCHAR(13)` → `VARCHAR(50)` (migration `004_widen_authority_type.py`)
- Wired `citation_format_hint` + `jurisdiction_code` into `build_expansion_prompt()` and `_expand_entity` prompt header
- Added 5 new `EXPANSION_TEMPLATES` for new authority types in `prompts.py`
- Wired `seed_anchors` into BFS queue — known entities now guaranteed to enter queue at `priority=1` after L1
- Added `citation_format` + `jurisdiction_code` to `entity_expansion_start` SSE event
- UI entity expansion message now shows `[L2][NJ] Entity Name (1/123)` format
- Fixed L2 source dedup — `UniqueViolationError` on `sources_pkey` hitting at entity ~123 due to shared sources (e.g. naic.org) returned by multiple entity expansions; added `l2_seen_source_ids` set

### Validation
- 317 backend tests passing
- Backend container rebuilt and healthy
- `Insurance_Prompt_v3.md` confirmed production-ready for insurance domain

## What's Next

### Immediate
- [ ] Full K=1 insurance run to completion — verify 0 errors
- [ ] Confirm `authority_type` populated in DB (not null)
- [ ] Verify citation hint appears in L2 logs for NJ DOBI
- [ ] Update model defaults: `anthropic_model` and `gemini_model` to latest versions in `config.py`

## Session Changes (2026-03-08)

### Discovery Input Contract Hardening
- `instruction_file` is now required for multipart discovery runs; JSON clients must provide `instruction_text`
- Removed the engine's generic prompt fallback so discovery cannot silently run with stale/default guidance
- Removed the DPA-specific default sector fallback; when `sector_file` is omitted, the engine now builds neutral runtime sectors from `geo_scope`
- Updated the frontend discovery form to enforce required prompt upload and clarify the optional sector-file behavior
- Validation: targeted request-contract tests passed (`49 passed`); frontend build remains blocked by a pre-existing Vite absolute-path emission error

### Golden Run Separation
- Added DB-backed logical/golden separation: `logical_runs`, `golden_runs`, `golden_run_items`, `domain_current_golden`
- Added explicit promotion workflow with immutable snapshot recall and current-domain pointer
- Added API surface for logical run history, golden version history, current golden lookup, and historical snapshot recall
- Preserved existing `golden_programs` consumers through snapshot-backed compatibility mapping
- Added regression coverage for snapshot immutability, pointer switching, and historical recall

### Validation
- Targeted golden-run tests passed: `tests/test_golden_runs.py`
- Full backend suite passed: **313 tests**
- Backend container rebuilt successfully and health endpoint returned OK
- Smoke checks confirmed `GET /api/golden-runs/runs` and `GET /api/manifests/logical-runs` are live

## What's Next

### Phase 0: First Real Golden Promotion
- [ ] Promote one real domain run group into the first accepted golden snapshot
- [ ] Validate historical recall and current-pointer behavior against real manifest data

### Phase 1: Ensemble Discovery Runs
- [ ] Add Sonnet 4.6 (`claude-sonnet-4-6`) to model dropdown
- [ ] Run Sonnet 4.6 at k_depth=3 or 4
- [ ] Run OpenAI competing models (GPT-4.1 at higher k_depth)
- [ ] Goal: maximize unique program count across runs

### Phase 2: Master Manifest Merge
- [ ] Build ensemble merge feature — combine all unique programs into single Master Manifest
- [ ] Cross-model confidence scoring — programs found by multiple models get boosted
- [ ] Dedup by normalized name + entity + geo_scope

### Phase 3: Program Validation Pipeline (HARD)
- [ ] Page data normalization — scrape and clean source URLs
- [ ] Fuzzy matching + inference rules — test relevance to DPA
- [ ] Program status validation — verify active/closed/paused dates
- [ ] Property extraction — eligibility criteria, income limits, benefit amounts
- [ ] Qualification rules — first-time buyer, income thresholds, geography
- [ ] Link validation — verify URLs resolve, follow redirects
- [ ] Form discovery — follow links to find application forms
- [ ] Confidence scoring — composite score from all validation signals

### Remaining Gaps (Deferred)
- RSS / Federal Register monitoring
- Embedding provider abstraction
- Relationship mapper batching
- Alembic in production lifespan
- Config security (CORS, SECRET_KEY)
- Ground truth eval datasets
- Frontend code splitting and polish
- CI improvements (mypy, Docker smoke test)

## Key Files

| File | Purpose |
|------|---------|
| `backend/app/agent/graph_discovery.py` | V6 RLM BFS discovery engine |
| `backend/app/agent/prompts.py` | LLM system prompts |
| `backend/app/llm/openai_provider.py` | OpenAI Responses API provider |
| `backend/app/llm/anthropic_provider.py` | Anthropic streaming provider |
| `backend/app/llm/gemini_provider.py` | Gemini provider with fallback chain |
| `backend/app/llm/registry.py` | Provider factory with model passthrough |
| `backend/app/routers/manifests.py` | API routes + background agent runner |
| `frontend/src/components/DomainInputPanel.tsx` | Discovery form with model selection |
| `frontend/src/components/ProgramsTable.tsx` | Programs display with filters |
| `prompts/DPA_Prompt_v9.md` | Current instruction file |
| `prompts/DPA_Sectors_v3.json` | 6-sector config with all 50 states |

## Tech Stack

| Layer | Technology |
|-------|-----------|
| Backend | Python 3.12, FastAPI, SQLAlchemy 2.0 (async), asyncpg |
| Frontend | React 18, TypeScript, TanStack Query, Recharts |
| Database | PostgreSQL 16 + pgvector |
| Cache | Redis 7 |
| LLM | Anthropic / OpenAI / Gemini (provider registry, per-request model selection) |
| Containers | Docker multi-stage builds, docker-compose |

## Active Branch

`main`

## Blockers

None.

## Tests

- **Backend**: 311 tests — all passing
