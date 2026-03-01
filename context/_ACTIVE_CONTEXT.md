# Active Context

- Updated: 2026-03-01
- Current focus: DPA V3 Hierarchical Discovery — build complete
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

- **Backend**: 298 tests across 23 test files — all passing
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

## What's Next

- Live integration test: run `discovery_mode=hierarchical` against Gemini with real seed file
- Evaluate seed recovery rate (target: 50%+ vs 2% in V2 flat mode)
- Frontend: surface `discovery_level` and per-topic match rates in results panel

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
