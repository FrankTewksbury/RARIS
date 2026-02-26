# Active Context

- Updated: 2026-02-26
- Current focus: Post-smoke-test — all containers healthy, discovery depth improved, remaining hardening
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

## What Was Done This Session

- Docker smoke test: all 4 containers built and healthy
- Fixed 5 integration bugs (Dockerfile, lazy-load, domain newline, JSX type, apt-get)
- Overhauled discovery agent for full 50-state depth (batched source hunting)
- Rebuilt Dashboard with sidebar layout + auto-display manifest results
- Wrote Cursor handoff and session journal

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

## What's Next — Remaining Gaps

### High Priority
1. **Commit this session's changes** — 9 files modified, unstaged
2. **RSS / Federal Register monitoring** — Change monitor only does hash-check; RSS and Federal Register API modeled but not implemented
3. **Embedding provider abstraction** — Hardcoded to OpenAI; fails silently if only Anthropic/Gemini key set
4. **Relationship mapper batching** — With 100+ sources, may exceed input token limits

### Medium Priority
5. **Alembic in production lifespan** — Currently `create_all` in dev; prod should run `alembic upgrade head`
6. **Config security** — CORS origins hardcoded, no SECRET_KEY, no API key validation on startup
7. **Ground truth eval datasets** — Insurance domain query-answer pairs for precision@k benchmarking

### Low Priority
8. **Frontend code splitting** — React.lazy + Suspense on page routes
9. **Frontend polish** — Loading states, page title, empty states
10. **CI improvements** — mypy/pyright, Docker build smoke test, integration test
11. **State body URL verification** — LLM-generated state department URLs need validation

## Active Branch

`main`

## Blockers

None — all 11 phases committed. Session changes need committing. Ready for hardening work.
