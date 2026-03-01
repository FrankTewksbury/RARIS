---
type: task-list
project: raris
updated: 2026-03-01
---

# Active Tasks

## In Progress

- [ ] DPA V2 Recall Fix: Items 0-5b (anthropic config, seed hint budget, seed batch pass, two-tier gate, seed prompt, seed metrics, Gemini 3.1 migration) `#status/active #priority/critical #source/session`

## Up Next — Hardening Backlog

- [ ] Implement RSS and Federal Register monitoring in change monitor `#status/backlog #priority/critical #source/session`
- [ ] Implement embedding provider abstraction (OpenAI + Gemini) and wire retrieval/cache to registry `#status/backlog #priority/critical #source/session`
- [ ] Batch relationship mapper input to avoid token overflow on deep manifests `#status/backlog #priority/critical #source/session`

## Deferred — Gemini 3.1 Rule Items (Not Applicable / Future)

- [ ] Per-model thinking budget awareness in fallback chain (Flash should get 4096, not 32768) `#status/deferred #priority/important #source/session`
- [ ] Gemini Files API integration for documents > 1MB (not applicable until PDF ingestion via Gemini) `#status/deferred #priority/normal #source/session`
- [ ] Gemini session resumption for long-horizon multi-turn tasks (not applicable — pipeline is stateless) `#status/deferred #priority/low #source/session`
- [ ] Gemini `customtools` model for agentic tool-calling workflows (not applicable — pipeline is prompt-in/JSON-out) `#status/deferred #priority/low #source/session`
- [ ] Gemini `flash-image-preview` for vision/OCR document layout analysis (not applicable — pipeline processes text only) `#status/deferred #priority/low #source/session`
- [ ] Run Alembic migrations in production lifespan instead of `create_all` `#status/backlog #priority/important #source/session`
- [ ] Move CORS and SECRET_KEY to env config and validate LLM keys on startup `#status/backlog #priority/important #source/session`
- [ ] Create insurance ground-truth evaluation dataset for precision@k benchmarking `#status/backlog #priority/important #source/session`
- [ ] Add frontend route code-splitting and improve loading/empty states `#status/backlog #priority/normal #source/session`
- [ ] Add mypy/pyright and Docker build smoke checks to CI `#status/backlog #priority/normal #source/session`
- [ ] Add state body URL verification for generated department links `#status/backlog #priority/normal #source/session`
- [ ] DPA Discovery V2 item 7: add municipal coverage and seed contribution metrics output `#status/backlog #priority/important #source/session`

## Recently Completed

- [x] P0 Gemini resilience: retry/backoff/fallback in `gemini_provider.py` `#status/done #priority/critical #source/session` @completed(2026-03-01T09:30:00-05:00)
- [x] P0 batch isolation: program_enumerator batch failures no longer abort full run `#status/done #priority/critical #source/session` @completed(2026-03-01T09:30:00-05:00)
- [x] P0 partial persistence: source commit before enumeration prevents zero-output on late failure `#status/done #priority/critical #source/session` @completed(2026-03-01T09:30:00-05:00)
- [x] Rules: gemini-model-rules.mdc updated with error matrix + python-genai SDK pattern `#status/done #priority/important #source/session` @completed(2026-03-01T09:30:00-05:00)
- [x] Rules: log-file-rule.mdc extended with Docker observability Track A `#status/done #priority/important #source/session` @completed(2026-03-01T09:30:00-05:00)
- [x] Global Docker rule artifact created at X:\DFW\Tools\rules\docker-observability.mdc (Track B) `#status/done #priority/normal #source/session` @completed(2026-03-01T09:30:00-05:00)

- [x] Deliver Phases 0-11 implementation baseline `#status/done #priority/critical #source/session` @completed(2026-02-26T12:00:00-05:00)
- [x] Pass Docker smoke test across backend/frontend/db/redis `#status/done #priority/critical #source/session` @completed(2026-02-26T12:00:00-05:00)
- [x] Fix integration regressions from smoke test (Dockerfile, async loading, prompt depth, UI results flow) `#status/done #priority/critical #source/session` @completed(2026-02-26T12:00:00-05:00)
- [x] DPA Discovery V2 item 1: add first-class `programs` model/schema/service response path `#status/done #priority/critical #source/session` @completed(2026-02-28T18:37:00-05:00)
- [x] DPA Discovery V2 item 2: add `k_depth` and `geo_scope` controls across UI/API/agent path `#status/done #priority/critical #source/session` @completed(2026-02-28T18:37:00-05:00)
- [x] DPA Discovery V2 item 3: add program enumerator stage and persistence in discovery pipeline `#status/done #priority/critical #source/session` @completed(2026-02-28T19:29:00-05:00)
- [x] DPA Discovery V2 item 4: add program extraction prompt and normalized dedupe path `#status/done #priority/critical #source/session` @completed(2026-02-28T19:29:00-05:00)
- [x] DPA Discovery V2 item 5: activate Seeding control with multi-file upload and backend seed parser/classifier path `#status/done #priority/critical #source/session` @completed(2026-02-28T19:29:00-05:00)

## Blocked

- None
