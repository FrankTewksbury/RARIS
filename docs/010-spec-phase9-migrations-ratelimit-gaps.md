# Phase 9: Database Migrations, Rate Limiting & Gap Closure

**Status**: Implementing
**Phase**: 9 of N
**Date**: 2026-02-25

---

## Objective

Close the remaining critical gaps from Phases 0–8: Alembic database migrations
(production blocker), per-key API rate limiting, and frontend test coverage for the
three untested pages.

---

## Deliverables

### 9A — Alembic Initial Migration
- Hand-written initial migration covering all 21 tables
- pgvector extension creation in migration
- Indexes on key lookup columns (key_hash, manifest_id, etc.)
- `main.py` updated to run Alembic in dev mode with `create_all` fallback

### 9B — API Rate Limiting
- Redis-based sliding window rate limiter
- Per-API-key limits when auth is enabled, per-IP when disabled
- Default: 60 requests/minute, configurable via `RATE_LIMIT_RPM`
- 429 response with `Retry-After` header when exceeded
- Rate limit headers on every response (`X-RateLimit-Limit`, `X-RateLimit-Remaining`)

### 9C — Frontend Test Coverage
- `Dashboard.test.tsx` — Domain Discovery page
- `AcquisitionMonitor.test.tsx` — Acquisition page
- `CurationDashboard.test.tsx` — Ingestion & Curation page

### 9D — Backend Rate Limit Tests
- Unit tests for sliding window logic
- Integration tests for 429 responses and rate limit headers

---

## Acceptance Criteria

1. `alembic upgrade head` against an empty database creates all 21 tables
2. `alembic downgrade base` drops all tables cleanly
3. Rate-limited endpoints return 429 after exceeding threshold
4. Rate limit response headers present on all API responses
5. All 6 frontend pages have at least one rendering test
6. All existing tests continue to pass
