# Active Context

- Updated: 2026-03-02
- Current focus: DPA V4 Prompt-Driven Discovery — **BUILD COMPLETE** (306 tests passing)
- Agent constitution: [CLAUDE.md](../CLAUDE.md)
- Operating manual: [docs/DFW-OPERATING-MANUAL.md](../docs/DFW-OPERATING-MANUAL.md)

## Phase Status

| Phase | Name | Status | Commit |
|-------|------|--------|--------|
| 0 | Project Foundation | `#status/done` | `a633159` |
| 1 | Domain Discovery & Analysis | `#status/done` | `a633159` |
| 2 | Data Acquisition Pipeline | `#status/done` | `b73d20c` |
| 3 | Ingestion & Curation Engine | `#status/done` | `0975e8f` |
| 4 | Retrieval & Agent Layer | `#status/done` | `7d40fee` |
| 5 | Vertical Expansion & Onboarding | `#status/done` | `7dd3a8f` |
| 6 | Feedback & Continuous Curation | `#status/done` | `2f04090` |
| 7 | Production Readiness & Integration | `#status/done` | `cdc2b85` |
| 8 | Auth, Scheduling & Observability | `#status/done` | `2c5597a` |
| 9 | DB Migrations, Rate Limiting & Gaps | `#status/done` | `1682179` |
| 10 | Scraper Rate, Export, Embedding Cache, FE Resilience | `#status/done` | `21445e9` |
| 11 | Retrieval Quality, Docker Hardening & CI | `#status/done` | `df02b34` |

## DPA V3 Hierarchical Discovery — Build Complete

All 6 phases implemented by Claude Code agent:

| Step | Description | Commit | Tests |
|------|-------------|--------|-------|
| Prereq | Fix model IDs (gemini-3-flash-preview, gpt-5.2-pro) | `f1cf512` | 237 |
| Phase A | `complete_grounded()` on all 3 LLM providers + Citation dataclass | `eb17f39` | 246 |
| Phase B | `_infer_program_type()` + `_index_seeds_by_type()` seed parser | `2bc95f7` | 279 |
| Phase C | `DiscoveryGraph` engine (L0-L3) + 4 grounded prompts | `59dfa13` | 293 |
| Phase D | `discovery_mode` schema/routing (flat vs hierarchical) | `896fe3a` | 295 |
| Phase E | Level-aware metrics (`cumulative_programs`, `nodes_at_level`) | `472da4d` | 298 |

### Key Files Added/Modified

- `backend/app/llm/base.py` — `Citation` dataclass, `complete_grounded()` default
- `backend/app/llm/gemini_provider.py` — Grounded search via `types.Tool(google_search=...)`, citation extraction from `grounding_metadata`
- `backend/app/llm/anthropic_provider.py` — Web search via `web_search_20250305` tool, annotation parsing
- `backend/app/llm/openai_provider.py` — Responses API web search, `url_citation` parsing
- `backend/app/agent/graph_discovery.py` — **NEW** — L0-L3 hierarchical discovery with web grounding
- `backend/app/agent/prompts.py` — 4 new grounded prompts (landscape mapper, source hunter, L1 expansion, L3 gap fill)
- `backend/app/routers/manifests.py` — `_infer_program_type()`, `_index_seeds_by_type()`, `discovery_mode` routing
- `backend/app/schemas/manifest.py` — `discovery_mode: Literal["flat", "hierarchical"]`

### Architecture

```
POST /api/manifests/generate  (discovery_mode=hierarchical)
  → _run_agent() branches on discovery_mode
  → DiscoveryGraph.run() yields SSE events:
      L0: grounded landscape mapper → regulatory bodies
      L0: grounded source hunter → verified sources with real URLs
      L1: entity expansion by type (cdfi→nonprofit, veteran→federal, etc.)
          + topic-matched seed injection from _index_seeds_by_type()
      L2: program dedup by canonical ID (highest confidence wins)
      L3: gap fill for unmatched seeds + underrepresented categories
  → All LLM calls use complete_grounded() (web search enabled)
  → SSE events include: discovery_level, nodes_at_level, cumulative_programs,
    seed_match_rate_by_topic, seed_recovery_rate
```

## Test Counts

- **Backend**: 306 tests across 25 test files — all passing
- **Frontend**: 16 tests across 8 test files — all passing
- **Linting**: Ruff clean, TypeScript clean, ESLint clean

## Tech Stack

| Layer | Technology |
|-------|-----------|
| Backend | Python 3.12, FastAPI, SQLAlchemy 2.0 (async), asyncpg |
| Frontend | React 18, TypeScript, TanStack Query, Recharts, React Router |
| Database | PostgreSQL 16 + pgvector (hybrid search: dense + sparse + RRF) |
| Cache | Redis 7 (rate limiting, embedding cache) |
| LLM | OpenAI / Anthropic / Gemini (provider registry) |
| Embeddings | OpenAI text-embedding-3-large (3072-dim), Redis-cached |
| Scheduler | APScheduler (change monitor, accuracy snapshots) |
| CI | GitHub Actions (lint, format, typecheck, test, Docker build) |
| Containers | Docker multi-stage builds, docker-compose + prod overlay |

## DPA V4 Prompt-Driven Discovery — BUILD COMPLETE

V3 hierarchical discovery had a fundamental **prompt-algorithm mismatch**: the engine used generic prompts while `DPA_Prompt_v4.md` contained rich domain methodology buried as passive context. Result: 15 programs with 0 sources.

**V4 architecture** (built in session S20260302_1400):
- `domain_description` renamed to `manifest_name` (just a label)
- Uploaded instruction prompt drives L0 discovery directly (full text, not truncated)
- L1-L3 recursion is data-driven (from L0 output, not from original prompt)
- Low-confidence items preserved with `needs_human_review: true` flag
- Base instruction template created (`docs/005-doc-base-instruction-template.md`)
- DPA_Prompt_v5 rewritten from v4 following the template

**Key fix:** `MockLLM` in tests was routing L0 to the L2 verification branch because the L0 execution instructions contain "verify". Fixed by narrowing the routing condition to `"programs to verify"` (unique to the L2 prompt).

**Final state:** 306 tests across 25 test files — all passing.

## V5 Graph BFS Engine — BUILD COMPLETE

V5 domain-agnostic BFS engine built in session S20260302_1430:

**Architecture:** 6 parallel sector calls (default, configurable via uploaded JSON) each receiving full instruction_text prefixed by a 3-line SECTOR SCOPE header. All domain expertise lives in the uploaded instruction file — zero domain content in engine code.

**Key changes:**
- `discovery_mode` (`flat`/`hierarchical`) removed entirely — always hierarchical BFS
- `geo_target` removed — engine is domain-agnostic; geo placeholders filled by user in instruction file
- Sector file upload slot added to UI and router (`_parse_sector_upload()`)
- `SECTOR_SCOPE_HEADER` + `DEFAULT_SECTORS` added to `prompts.py` (domain-agnostic only)
- `graph_discovery.py` fully rewritten: `_run_l1_sectors`, `_expand_entity`, `_run_l2_entity_expansion`
- New SSE events: `sector_start`, `sector_complete`, `l1_assembly_complete`, `entity_expansion_start`, `entity_expansion_complete`
- `DPA_Prompt_v7.md` (instruction file) + `DPA_Sectors_v1.json` (sector config) created
- All tests updated to V5 event shape — 311 tests passing

**Files modified:**
- `backend/app/schemas/manifest.py` — removed `discovery_mode` + `geo_target`
- `backend/app/routers/manifests.py` — removed discovery_mode branch, added `_parse_sector_upload()`
- `backend/app/agent/prompts.py` — added `SECTOR_SCOPE_HEADER` + `DEFAULT_SECTORS`
- `backend/app/agent/graph_discovery.py` — full V5 rewrite
- `frontend/src/components/DomainInputPanel.tsx` — removed discovery_mode, added sector file upload
- `backend/tests/test_graph_discovery.py` — rewritten for V5 event shapes
- `backend/tests/test_graph_discovery_v4.py` — updated to V5 mock format + event names
- `backend/tests/test_manifest_schema.py` — removed discovery_mode assertions
- `prompts/DPA_Prompt_v7.md` — new instruction file
- `prompts/DPA_Sectors_v1.json` — new sector config

## What's Next

- [ ] First live test run with k_depth=1 (6 sector_start/sector_complete SSE events visible)
- [ ] First live test run with k_depth=2 (entity expansion + programs populated)
- [ ] Upload `DPA_Sectors_v1.json` + `DPA_Prompt_v7.md` via UI and validate end-to-end
- [ ] AuthorityType DB migration (new enum values: state_hfa, municipal, pha, nonprofit, cdfi, employer, tribal)

### Remaining Gaps (Deferred)

- RSS / Federal Register monitoring
- Embedding provider abstraction
- Relationship mapper batching
- Alembic in production lifespan
- Config security (CORS, SECRET_KEY)
- Ground truth eval datasets
- Frontend code splitting and polish
- CI improvements (mypy, Docker smoke test)

## Active Branch

`main`

## Blockers

None.
