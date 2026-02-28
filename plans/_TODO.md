---
type: task-list
project: raris
updated: 2026-02-26
---

# Active Tasks

## In Progress

- [ ] Implement RSS and Federal Register monitoring in change monitor `#status/active #priority/critical #source/session`

## Up Next — Hardening Backlog

- [ ] Implement embedding provider abstraction (OpenAI + Gemini) and wire retrieval/cache to registry `#status/backlog #priority/critical #source/session`
- [ ] Batch relationship mapper input to avoid token overflow on deep manifests `#status/backlog #priority/critical #source/session`
- [ ] Run Alembic migrations in production lifespan instead of `create_all` `#status/backlog #priority/important #source/session`
- [ ] Move CORS and SECRET_KEY to env config and validate LLM keys on startup `#status/backlog #priority/important #source/session`
- [ ] Create insurance ground-truth evaluation dataset for precision@k benchmarking `#status/backlog #priority/important #source/session`
- [ ] Add frontend route code-splitting and improve loading/empty states `#status/backlog #priority/normal #source/session`
- [ ] Add mypy/pyright and Docker build smoke checks to CI `#status/backlog #priority/normal #source/session`
- [ ] Add state body URL verification for generated department links `#status/backlog #priority/normal #source/session`

## Recently Completed

- [x] Deliver Phases 0-11 implementation baseline `#status/done #priority/critical #source/session` @completed(2026-02-26T12:00:00-05:00)
- [x] Pass Docker smoke test across backend/frontend/db/redis `#status/done #priority/critical #source/session` @completed(2026-02-26T12:00:00-05:00)
- [x] Fix integration regressions from smoke test (Dockerfile, async loading, prompt depth, UI results flow) `#status/done #priority/critical #source/session` @completed(2026-02-26T12:00:00-05:00)

## Blocked

- None
