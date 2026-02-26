---
type: spec
created: 2026-02-25
source: claude-code
description: Phase 8 — API key auth, job scheduling, deep health checks, request logging, config validation
tags: [raris, phase8, spec, "#status/active", "#priority/high"]
---

# Phase 8 — Auth, Scheduling & Observability

## Overview

Phase 8 adds the operational layer: API key authentication, background job
scheduling for the change monitor, deep health checks (DB + Redis), request
logging middleware with correlation IDs, startup config validation, and
admin operations endpoints.

---

## Deliverables

### A. API Key Authentication
- API key model and CRUD
- FastAPI dependency for key validation
- Scoped access (read-only, write, admin)
- Key generation endpoint (admin-only)
- Optional auth (disabled by default via config flag for development)

### B. Background Job Scheduling
- APScheduler integration for periodic tasks
- Change monitor scheduled daily (configurable)
- Accuracy snapshot scheduled daily
- Manual trigger endpoints preserved

### C. Deep Health Checks
- Liveness probe: `/health` (fast, no dependencies)
- Readiness probe: `/health/ready` (checks DB + Redis)
- Dependency status in response

### D. Request Logging Middleware
- Structured JSON logging with correlation IDs
- Request/response timing
- Log level configurable via environment

### E. Config Validation
- Startup validation for required settings
- Warning for missing LLM API keys
- Environment name tracking (dev/staging/prod)

### F. Admin Endpoints
- API key management (create/list/revoke)
- System info (version, uptime, config summary)
- Cache/queue stats

---

## Acceptance Criteria

- [ ] API endpoints require valid API key when auth is enabled
- [ ] Change monitor runs on schedule without manual intervention
- [ ] Health readiness probe verifies DB and Redis connectivity
- [ ] All requests get correlation IDs in response headers
- [ ] App validates config on startup and warns about missing keys
- [ ] Admin endpoints accessible only with admin-scoped API key
