# Phase 11: Retrieval Quality, Docker Hardening & CI Improvements

**Status**: Implementing
**Phase**: 11 of N
**Date**: 2026-02-26

---

## Objective

Improve retrieval quality with a batch reranker and precision@k eval metric,
implement the API acquisition adapter, harden Docker images with health checks
and production compose profiles, clean up CSS conflicts, and strengthen the CI
pipeline.

---

## Deliverables

### 11A — Batch LLM Reranker
- Replace serial per-chunk LLM reranking (N calls) with single-prompt batch scoring
- All chunks scored in one LLM call — 20x fewer API roundtrips per query
- Preserves `rerank_method` config: `llm` (now batched), `none`

### 11B — Retrieval Precision@k Metric
- `precision_at_k(ranked_results, relevant_ids, k)` in eval/metrics.py
- `ndcg_at_k(ranked_results, relevant_ids, k)` for ranking quality
- Tests covering edge cases (empty results, perfect ranking, no relevant)

### 11C — API Acquisition Adapter
- Generic HTTP API adapter with configurable auth (header, query param, bearer)
- Pagination support (offset, cursor, link-header)
- Wired into orchestrator to replace the "not implemented" stub

### 11D — Docker Hardening
- Backend Dockerfile: `HEALTHCHECK` instruction
- Frontend Dockerfile: `HEALTHCHECK` instruction
- `docker-compose.prod.yml` — production overrides (no exposed DB/Redis ports,
  auth enabled, no default passwords)

### 11E — CI Improvements
- Re-enable `test_health.py` (it uses the test client, not live services)
- `build-docker` job depends on lint + test jobs
- Add `ruff format --check` step

### 11F — CSS Cleanup
- Strip conflicting Vite scaffold rules from `index.css`

---

## Acceptance Criteria

1. Reranking uses a single LLM call regardless of result count
2. `precision_at_k` and `ndcg_at_k` return correct values for known inputs
3. Sources with `access_method == "api"` are no longer silently skipped
4. `docker build` produces images with embedded HEALTHCHECK
5. `docker-compose -f docker-compose.yml -f docker-compose.prod.yml config` shows
   no exposed DB/Redis ports and auth enabled
6. CI tests cover health endpoints
7. All existing tests continue to pass
