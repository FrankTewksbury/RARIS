# Active Context

- Updated: 2026-02-26
- Current focus: Phases 0-11 fully implemented, all tests passing
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

## Test Counts

- **Backend**: 230 tests across 20 test files — all passing
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

## Architecture Summary

### Backend Routers (9 total)
- `health` — liveness + readiness probes (DB + Redis)
- `manifests` — domain discovery CRUD + SSE streaming
- `acquisitions` — acquisition runs + source retry + SSE
- `ingestion` — ingestion pipeline + document CRUD + index stats
- `retrieval` — hybrid search, query agent (4 depth levels), cross-corpus analysis
- `verticals` — vertical onboarding + pipeline orchestration
- `feedback` — response feedback, re-curation queue, change monitor, accuracy dashboard
- `admin` — API key CRUD, system info, scheduler status
- `export` — manifest JSON, query CSV, corpus summary downloads

### Backend Services & Modules
- `agent/discovery.py` — 5-step LLM domain discovery pipeline
- `acquisition/orchestrator.py` — scrape/download/API acquisition with retries
- `acquisition/scraper.py` — httpx + Firecrawl, per-domain rate limiting
- `acquisition/api_adapter.py` — REST API adapter with auth + pagination
- `ingestion/` — 5 adapters (HTML, PDF, XML, Guide, Plaintext), chunker, indexer, curation
- `retrieval/search.py` — pgvector dense + tsvector sparse + RRF fusion
- `retrieval/agent.py` — query planning, streaming synthesis, citation threading
- `retrieval/reranker.py` — batch LLM reranking (single prompt for all chunks)
- `feedback/tracer.py` — citation chain tracing + auto-actions
- `feedback/monitor.py` — HTTP hash-check change detection
- `auth.py` — API key auth (SHA-256, read/write/admin scopes, optional)
- `middleware.py` — correlation IDs, response timing, Redis rate limiting
- `scheduler.py` — APScheduler cron jobs for monitor + accuracy snapshots
- `embedding_cache.py` — Redis embedding cache (24h TTL)
- `rate_limit.py` — sliding window rate limiter (fail-open)
- `eval/metrics.py` — manifest accuracy, source recall, scrape completion, ingestion success, precision@k, NDCG@k

### Frontend Pages (6 + NotFound)
- `Dashboard` — Domain discovery with SSE progress
- `AcquisitionMonitor` — Acquisition runs, source status, error logs
- `CurationDashboard` — Ingestion pipeline, quality gates, index health
- `QueryInterface` — Query input, response panel, citation explorer
- `VerticalOnboarding` — Vertical registry, wizard, pipeline tracker
- `AccuracyDashboard` — Feedback feed, re-curation queue, change monitor, accuracy trends
- `NotFound` — 404 catch-all

### Frontend Infrastructure
- `ErrorBoundary` — catches component crashes
- `LoadingSpinner`, `EmptyState` — reusable UI primitives
- `api/client.ts` — auth header injection, 429 retry-after, DELETE method

### Database (21 tables)
- Alembic initial migration: `alembic/versions/001_initial_schema.py`
- Tables created via `Base.metadata.create_all` in dev lifespan
- pgvector extension + HNSW/GIN indexes in migration

## Environment Notes

- **Windows subst drive**: X: → C:\DATA\RARIS
- **Frontend builds**: Must run from `C:/DATA/RARIS/frontend` (not X: drive)
- **Python**: `.venv/Scripts/python.exe -m` for ruff, pytest
- **uv**: Not in PATH — pip bootstrapped via `ensurepip`
- **Test DB**: In-memory SQLite via aiosqlite with custom type compiles (JSONB→TEXT, TSVECTOR→TEXT)

## What's Next — Remaining Gaps

### High Priority
1. **End-to-end smoke test** — `docker compose up` and verify full pipeline
2. **Live Insurance domain run** — Real LLM + real scraping to validate the full pipeline
3. **RSS/Federal Register monitoring** — Change monitor only does hash-check; RSS and Federal Register API are modeled but not implemented
4. **Embedding provider abstraction** — Embeddings hardcoded to OpenAI; fails silently if only Anthropic/Gemini key is set

### Medium Priority
5. **Cross-encoder reranker** — Would require `sentence-transformers` (heavy dep); current batch LLM reranker is a good interim
6. **Ground truth eval datasets** — Insurance domain query-answer pairs for precision@k benchmarking
7. **Alembic in production lifespan** — Currently `create_all` in dev; prod should run `alembic upgrade head`
8. **Config security** — No `cors_origins` list, no `secret_key` for future JWT auth

### Low Priority
9. **Frontend code splitting** — All pages eagerly loaded; could use `React.lazy` + `Suspense`
10. **Frontend loading states** — Minimal; some pages have no loading/empty state guidance
11. **Backend type checking** — No mypy/pyright in CI (only ruff lint)
12. **Crawlee integration** — Spec mentions it for multi-page crawls; using httpx instead

## Active Branch

`main`

## Blockers

None — all 11 phases committed and pushed. Ready for smoke testing or Phase 12.
