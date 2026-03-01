# Active Context

- Updated: 2026-03-01
- Current focus: P0 Gemini resilience complete — next is DPA V2 item 6 (evidence hard gates)
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

## What Was Done This Session (2026-03-01)

- **P0 Gemini resilience — complete** (ref: handoff `prompts/002-handoff-p0-gemini-resilience-build-agent.md`)
  - `backend/app/llm/gemini_provider.py` — full retry/backoff/fallback rewrite:
    - `_call_with_resilience()` with exponential backoff + jitter, max 4 attempts
    - Retryable codes `{429, 500, 502, 503, 504}` + transient transport errors
    - Downgrade codes `{429, 503, 504}` advance to next model in fallback chain
    - Fail-fast codes `{400, 401, 403, 404}` raise immediately
    - Fallback chain driven by `GEMINI_FALLBACK_MODELS` env var (default: pro→flash→2.5-flash)
  - `backend/app/agent/discovery.py` — batch isolation + partial persistence:
    - Each `program_enumerator` batch wrapped in try/except — failure logs + skips, run continues
    - `skipped_batches` metric threaded through to SSE events and debug log
    - Source-stage `commit()` before program enumeration begins — late failures cannot zero out sources
  - `backend/app/config.py` — added `gemini_fallback_models` setting
  - `.cursor/rules/gemini-model-rules.mdc` — full error matrix, python-genai SDK pattern, fallback policy, telemetry fields
  - `.cursor/rules/log-file-rule.mdc` — Docker observability section (Track A): operator commands, required fields, summary line format, heartbeat standard
  - `X:\DFW\Tools\rules\docker-observability.mdc` — global reusable Docker rule (Track B)
  - All 237 backend tests passing

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
1. **Evidence hard gates (DPA V2 item 6)** — enforce required evidence URL/snippet and stronger acceptance quarantine paths
2. **Coverage metrics (DPA V2 item 7)** — expose municipal-tier and seed-contribution metrics in manifest output
3. **Benchmarking (DPA V2 item 8)** — compare against DPA export baseline for overlap/net-new precision
4. **RSS / Federal Register monitoring** — Change monitor only does hash-check; RSS and Federal Register API modeled but not implemented
5. **Embedding provider abstraction** — Hardcoded to OpenAI; fails silently if only Anthropic/Gemini key set
6. **Relationship mapper batching** — With 100+ sources, may exceed input token limits

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

None — all 11 phases committed and process files are now aligned to current state.
