---
type: spec
created: 2026-02-25
sessionId: S20260225_0002
source: cursor
description: Phase 0 — Project Foundation spec (Docker, CI/CD, evaluation framework)
tags: [raris, phase0, spec, "#status/active", "#priority/critical"]
---

# Phase 0 — Project Foundation

Scaffolding and governance. No application logic — just the skeleton.

---

## Dev Environment (Hybrid)

**Docker Compose** runs infrastructure only: `docker compose up`

| Service | Image | Port | Purpose |
|---------|-------|------|---------|
| `db` | `postgres:16` | 5432 | Primary database |
| `redis` | `redis:7` | 6379 | Job queue (Phase 2) |

**Native services** for fast iteration:

| Service | Command | Port |
|---------|---------|------|
| Backend | `uv run uvicorn backend.app.main:app --reload` | 8000 |
| Frontend | `cd frontend && npm run dev` | 5173 |

### `.env.example`

```env
POSTGRES_DB=raris
POSTGRES_USER=raris
POSTGRES_PASSWORD=changeme
DATABASE_URL=postgresql://raris:changeme@localhost:5432/raris
REDIS_URL=redis://localhost:6379/0
LLM_PROVIDER=openai
OPENAI_API_KEY=
ANTHROPIC_API_KEY=
GEMINI_API_KEY=
```

---

## CI Pipeline (GitHub Actions)

Triggers on every PR to `main`. All jobs must pass.

| Job | Tool | Command |
|-----|------|---------|
| `lint` | ruff + eslint | `ruff check backend/` / `npm run lint` |
| `test-backend` | pytest | `pytest backend/tests/ -v` |
| `test-frontend` | vitest | `npx vitest run` |

Branch protection: passing CI required, no direct pushes to `main`.

---

## Evaluation Framework

| Metric | Target | Phase |
|--------|--------|-------|
| Manifest Accuracy | ≥95% | 1 |
| Source Recall | ≥90% | 1 |
| Scrape Completion | ≥90% | 2 |
| Ingestion Success | ≥95% | 3 |
| Retrieval Precision@k | TBD | 4 |

Test harness: pytest fixtures with ground truth YAML for Insurance domain.

---

## Conventions

**Branches:** `phase{N}/{component-name}`
**Commits:** `type: short description` (feat, fix, docs, test, refactor, ci, chore)

---

## Exit Criteria

- [ ] `docker compose up` starts db + redis; backend and frontend start natively
- [ ] CI pipeline runs on PRs and blocks merge on failure
- [ ] Evaluation framework has metric definitions and test harness skeleton
- [ ] Phase 1 spec reviewed and approved
