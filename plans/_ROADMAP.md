---
type: roadmap
project: raris
created: 2026-02-25
sessionId: S20260225_0002
source: cursor
updated: 2026-02-26
tags: [raris, roadmap]
---

# RARIS Roadmap

> Source of truth: [RARI Macro Development Plan v2.0](../research/001-research-macro-dev-plan-v2.md)

---

## Delivery Status Snapshot

| Phase | Name | Status | Commit |
|------|------|--------|--------|
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

---

## Current Wave — Hardening and Reliability `#status/active`

**Goal:** Close post-implementation gaps surfaced by smoke tests and deep discovery runs.

**Hardening Priorities:**
- [ ] Implement RSS + Federal Register monitoring alongside hash polling `#status/active #priority/critical #source/session`
- [ ] Add embedding provider abstraction and registry-backed selection `#status/backlog #priority/critical #source/session`
- [ ] Add batching to relationship mapper for deep manifests `#status/backlog #priority/critical #source/session`
- [ ] Gate production startup on Alembic migration state and config validation `#status/backlog #priority/important #source/session`
- [ ] Expand evaluation artifacts (insurance ground-truth set, precision@k regression checks) `#status/backlog #priority/important #source/session`
