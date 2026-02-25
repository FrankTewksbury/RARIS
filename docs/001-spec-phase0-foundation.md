---
type: spec
created: 2026-02-25
sessionId: S20260225_0002
source: cursor
description: Phase 0 — Project Foundation spec (Docker, CI/CD, evaluation framework)
tags: [raris, phase0, spec, "#status/active", "#priority/critical"]
---

# Phase 0 — Project Foundation Specification

## Overview

Phase 0 delivers the scaffolding and governance layer for RARIS. No application logic —
just the skeleton that everything else builds on. A contributor should be able to clone
the repo, run one command, and have a working dev environment.

---

## Docker Compose Specification

### Services

| Service | Image / Build | Port | Purpose |
|---------|--------------|------|---------|
| `backend` | `./backend` (Dockerfile) | 8000 | FastAPI application server |
| `frontend` | `./frontend` (Dockerfile) | 5173 | Vite dev server (React + TypeScript) |
| `db` | `postgres:16` | 5432 | Primary database |
| `redis` | `redis:7` | 6379 | Job queue for Phase 2 acquisition orchestration |

### Volume Mounts

| Service | Host Path | Container Path | Purpose |
|---------|-----------|---------------|---------|
| `backend` | `./backend` | `/app` | Live reload during development |
| `frontend` | `./frontend` | `/app` | Live reload during development |
| `db` | `pgdata` (named volume) | `/var/lib/postgresql/data` | Persistent database storage |

### Environment Configuration

Environment variables are loaded from `.env` (not committed) with `.env.example` as template.

```env
# .env.example
POSTGRES_DB=raris
POSTGRES_USER=raris
POSTGRES_PASSWORD=changeme
DATABASE_URL=postgresql://raris:changeme@db:5432/raris

REDIS_URL=redis://redis:6379/0

LLM_PROVIDER=openai
OPENAI_API_KEY=
ANTHROPIC_API_KEY=
GEMINI_API_KEY=

BACKEND_HOST=0.0.0.0
BACKEND_PORT=8000
```

### Health Checks

| Service | Health Check | Interval | Retries |
|---------|-------------|----------|---------|
| `db` | `pg_isready -U raris` | 5s | 5 |
| `redis` | `redis-cli ping` | 5s | 5 |
| `backend` | `curl -f http://localhost:8000/health` | 10s | 3 |

### Service Dependencies

- `backend` depends on `db` (healthy) and `redis` (healthy)
- `frontend` depends on `backend` (started)

---

## GitHub Actions CI Pipeline

### Trigger

Every PR targeting `main`.

### Jobs

#### `lint`
```yaml
steps:
  - Backend: ruff check backend/ && ruff format --check backend/
  - Frontend: cd frontend && npm run lint
```

#### `test-backend`
```yaml
steps:
  - Set up Python 3.12
  - Install dependencies via uv
  - Run: pytest backend/tests/ -v --tb=short
```
Requires: PostgreSQL service container for integration tests.

#### `test-frontend`
```yaml
steps:
  - Set up Node 20
  - Install: npm ci
  - Run: npx vitest run
```

#### `build`
```yaml
steps:
  - Run: docker compose build
```
Validates all Dockerfiles and build contexts.

### Branch Protection

- All 4 jobs must pass before PR merge is allowed
- At least 1 approving review required
- No direct pushes to `main` (enforce via GitHub settings)

---

## Evaluation Framework Skeleton

### Defined Metrics

| Metric | Description | Target | Phase |
|--------|-------------|--------|-------|
| **Manifest Accuracy** | % of regulatory bodies and key sources correctly identified | ≥95% | Phase 1 |
| **Source Recall** | % of known sources present in agent-produced manifest | ≥90% | Phase 1 |
| **Scrape Completion Rate** | % of manifest sources successfully acquired | ≥90% | Phase 2 |
| **Ingestion Success Rate** | % of staged documents successfully ingested and curated | ≥95% | Phase 3 |
| **Retrieval Precision@k** | Precision of top-k retrieval results | Defined in Phase 4 | Phase 4 |
| **Retrieval Recall@k** | Recall of top-k retrieval results | Defined in Phase 4 | Phase 4 |

### Test Harness

- **Framework:** pytest with custom fixtures for manifest validation
- **Benchmark datasets:** Ground truth lists of regulatory bodies and sources per domain
  - Insurance domain: manually curated list of federal agencies, NAIC, all 50 state
    insurance commissioners, and key source documents per body
- **Scoring:** Each metric has a defined passing threshold (see table above)
- **CI integration:** Evaluation tests run as part of `test-backend` job

### Fixtures

```python
# tests/conftest.py (skeleton)
@pytest.fixture
def insurance_ground_truth():
    """Ground truth regulatory bodies and sources for US Insurance domain."""
    return load_yaml("tests/fixtures/insurance_ground_truth.yaml")

@pytest.fixture
def manifest_validator():
    """YAML manifest schema validator."""
    return ManifestValidator(schema_path="schemas/manifest.yaml")
```

---

## Branch Convention

```
phase{N}/{component-name}
```

Examples:
- `phase0/docker-compose`
- `phase0/ci-pipeline`
- `phase1/domain-discovery-agent`
- `phase2/web-scraping-engine`

---

## Contributing Guide

### Commit Message Format

```
type: short description

Optional longer description.
```

Types: `feat`, `fix`, `docs`, `test`, `refactor`, `ci`, `chore`

### PR Description Template

```markdown
## What
[One-line summary of the change]

## Why
[Motivation and context]

## How
[Technical approach — what changed and why this approach]

## Testing
[How was this tested? What test cases cover it?]

## Checklist
- [ ] Tests pass locally
- [ ] Linting passes
- [ ] Docs updated if needed
```

---

## Exit Criteria

- [ ] `docker compose up` starts all 4 services (backend, frontend, db, redis) with no errors
- [ ] CI pipeline runs on every PR and blocks merge on failure
- [ ] Evaluation framework has passing metric definitions and test harness skeleton
- [ ] Phase 1 spec reviewed and approved
