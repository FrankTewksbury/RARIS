# Phase 10: Scraper Rate Enforcement, Export API, Embedding Cache & Frontend Resilience

**Status**: Implementing
**Phase**: 10 of N
**Date**: 2026-02-26

---

## Objective

Enforce inter-request rate limiting in the scraper to prevent IP bans from government
sites, add data export endpoints for researcher usability, cache embeddings in Redis
to cut repeat API costs, and harden the frontend with error boundaries, 404 handling,
auth header injection, and loading/empty states.

---

## Deliverables

### 10A — Scraper Rate Enforcement
- `asyncio.sleep(rate_limit_ms / 1000)` between requests in the orchestrator
- `rate_limit_ms` propagated from vertical config through orchestrator to scraper
- Domain-aware throttling: per-domain last-request timestamps

### 10B — Export API
- `GET /api/export/manifest/{id}` — Full manifest + sources as JSON download
- `GET /api/export/queries` — Query history as CSV
- `GET /api/export/corpus/summary` — Corpus statistics snapshot as JSON

### 10C — Embedding Cache
- Redis-based cache for query embeddings (hash of query text → embedding vector)
- TTL: 24 hours (configurable)
- Cache hit avoids OpenAI API call entirely
- Applied to both search.py `_embed_query` and indexer.py (document embeddings not cached — they're one-time)

### 10D — Frontend Resilience
- `ErrorBoundary` component wrapping the app
- `NotFound` page on `path="*"` catch-all route
- API client: `delete` method, `X-API-Key` header injection, 429 retry-after
- Reusable `LoadingSpinner` and `EmptyState` components

---

## Acceptance Criteria

1. Scraper waits `rate_limit_ms` between requests to the same domain
2. Export endpoints return downloadable files with proper Content-Disposition headers
3. Repeated identical queries hit Redis cache instead of OpenAI embedding API
4. Invalid frontend routes show a "Page Not Found" screen
5. Component errors are caught by error boundary instead of white-screening
6. All existing tests continue to pass
