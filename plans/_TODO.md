---
type: task-list
project: raris
updated: 2026-03-02
---

# Active Tasks

## In Progress

- None

## Up Next — V6 Verification & Hardening

- [ ] Promote first real domain golden snapshot and validate recall/current-pointer behavior `#status/backlog #priority/important #source/session`
- [ ] **Live test K=1**: run with `DPA_Sectors_v3.json` + `DPA_Prompt_v9.md`, verify all sectors return entities > 0 `#status/ready #priority/critical #agent/claude-code`
- [ ] **Live test K=2**: confirm queue expansion discovers programs and sub-entities `#status/blocked-by/k1-test #priority/critical #agent/claude-code`
- [ ] **AuthorityType migration**: Expand enum (state_hfa, municipal, pha, nonprofit, cdfi, employer, tribal) + `native_enum=False` + DB reset `#status/ready #priority/critical #agent/cursor`
- [ ] **Frontend queue stats**: surface queue_stats (depth, pending, api_calls) in AgentProgressPanel `#status/backlog #priority/important #agent/cursor`
- [ ] **Seed validation**: run with seed file after K=2 confirmed → target 50%+ seed recovery `#status/blocked-by/k2-test #priority/critical #agent/claude-code`

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

- [x] **Discovery input contract hardening** — prompt upload is now required, JSON callers must supply `instruction_text`, DPA-specific sector fallback removed, neutral runtime sectors added when no sector file is provided, and request-contract regression tests updated/passing `#status/done #priority/critical #agent/cursor` @completed(2026-03-08T17:20:00-05:00)
- [x] **Golden Run Separation** — implemented DB-backed logical/golden separation with immutable snapshots, current-domain pointer, compatibility mapping, regression tests, backend rebuild, and smoke validation (313 tests passing) `#status/done #priority/critical #agent/cursor` @completed(2026-03-08T16:00:00-05:00)
- [x] **DPA V6 RLM Queue-Driven BFS Engine** — full rewrite: discovery_queue.py, graph_discovery.py V6, call_logger.py, DPA_Prompt_v9.md, DPA_Sectors_v3.json, 3-provider LLM logging (311 tests) `#status/done #priority/critical #agent/claude-code` @completed(2026-03-03)
- [x] **DPA V5 BFS Engine** — committed as `752c0b4`, 6 parallel sector calls, per-entity expansion, truncation recovery (311 tests) `#status/done #priority/critical #agent/claude-code` @completed(2026-03-03)
- [x] **DPA V4 Prompt-Driven Discovery** — full build complete (9 commits, 306 tests) `#status/done #priority/critical #agent/cursor` @completed(2026-03-02)
  - [x] Commit 1: `docs/005-doc-base-instruction-template.md` — 7-section instruction template
  - [x] Commit 2: `prompts/DPA_Prompt_v5.md` — DPA prompt rewritten to template contract
  - [x] Commit 3: `prompts.py` — V4 prompts (L0_ORCHESTRATOR_SYSTEM + data-driven L1-L3)
  - [x] Commit 4: `manifest.py` schema/model — `domain_description` → `manifest_name`
  - [x] Commit 5: `manifests.py` router — `manifest_name` wiring + instruction_file warning
  - [x] Commit 6: `DomainInputPanel.tsx` — frontend field rename + placeholder
  - [x] Commit 7: `graph_discovery.py` — full V4 engine rewrite (L0 instruction-driven, L1-L3 data-driven)
  - [x] Commit 8: tests (schema, integration, v4 new, v3 compat) — 306 passing
  - [x] Commit 9: Dockerfile + .dockerignore — pytest in container (all-extras + copy tests)
  - Root cause of final bug: MockLLM routing matched "verify" in L0 prompt → fixed to "programs to verify"
- [x] **DPA V3 Hierarchical Discovery** — full build complete (Phases A-E) `#status/done #priority/critical #agent/claude-code` @completed(2026-03-01)
  - [x] Prereq: fix model IDs (gemini-3-flash-preview, gpt-5.2-pro) → `f1cf512`
  - [x] Phase A: `complete_grounded()` on all 3 LLM providers → `eb17f39`
  - [x] Phase B: topic-indexed seed parser (`program_type` inference) → `2bc95f7`
  - [x] Phase C: discovery graph engine (L0-L3) → `59dfa13`
  - [x] Phase D: route wiring (`discovery_mode: flat | hierarchical`) → `896fe3a`
  - [x] Phase E: level-aware metrics and observability → `472da4d`
- [x] DPA V2 Recall Fix: Items 0-5b complete (anthropic config, seed hint budget, seed batch pass, two-tier gate, seed prompt, seed metrics, Gemini 3.1 migration) `#status/done #priority/critical #source/session` @completed(2026-03-01T18:00:00-05:00)
- [x] LLM rules overhaul: all 3 vendor rules rewritten from March 2026 docs, web grounding sections added, Anthropic rule created `#status/done #priority/critical #source/session` @completed(2026-03-01T17:00:00-05:00)
- [x] DPA program taxonomy: 3-axis classification (funding entity, benefit structure, eligibility persona) `#status/done #priority/important #source/session` @completed(2026-03-01T19:30:00-05:00)
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
