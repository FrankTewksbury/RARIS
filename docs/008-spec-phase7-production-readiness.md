---
type: spec
created: 2026-02-25
source: claude-code
description: Phase 7 — Docker containerization, Alembic migration, API integration tests, frontend tests
tags: [raris, phase7, spec, "#status/active", "#priority/high"]
---

# Phase 7 — Production Readiness & Integration

## Overview

Phase 7 closes the infrastructure gaps deferred during Phases 1–6. It delivers
Docker containerization (backend + frontend Dockerfiles, full 4-service Compose),
the initial Alembic database migration, backend API integration tests, frontend
component tests, and a standardized error handling layer.

This satisfies the Phase 0 exit criterion: `docker compose up` starts all 4
services (backend, frontend, db, redis) with no errors.

---

## Deliverables

### A. Docker Containerization
- Backend Dockerfile (Python 3.12 + uv + FastAPI)
- Frontend Dockerfile (multi-stage: Node build + nginx serve)
- Expanded docker-compose.yml with all 4 services + dependency ordering

### B. Alembic Initial Migration
- Auto-generated migration for all existing models (13 tables)

### C. Backend API Integration Tests
- Tests hitting actual FastAPI routes via ASGI transport
- Covering all 7 routers: health, manifests, acquisitions, ingestion,
  retrieval, verticals, feedback

### D. Frontend Component Tests
- Vitest tests for key pages and components
- Tests for rendering, routing, and data display

### E. Error Handling
- Standardized error response format
- Global exception handler for unhandled errors
- Validation error formatting

### F. CI Pipeline Update
- Add TypeScript type-check step
- Add Docker build validation job

---

## Acceptance Criteria

- [ ] `docker compose up` starts backend, frontend, db, redis with no errors
- [ ] Backend Dockerfile builds and serves the API
- [ ] Frontend Dockerfile builds static assets and serves via nginx
- [ ] Alembic migration creates all tables when run against empty database
- [ ] API integration tests cover all major endpoint groups
- [ ] Frontend tests cover all pages with rendering checks
- [ ] CI pipeline includes type checking and Docker build validation
