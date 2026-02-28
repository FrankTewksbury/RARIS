# RARIS

Regulatory Analysis & Research Intelligence System. AI-assisted regulatory discovery, acquisition, ingestion, and retrieval platform.

## Current Status
- Core delivery through Phase 11 is complete and committed on `main`
- Docker smoke test passed for backend, frontend, db, and redis
- Current work is hardening: monitoring depth, embedding provider flexibility, and large-run reliability

## Key Directories
- `backend/` - FastAPI application and backend tests
- `frontend/` - React/TypeScript app and frontend tests
- `docs/` - specifications, architecture, DFW methodology docs
- `plans/` - active TODO and roadmap
- `context/` - active context and decisions log
- `prompts/handoffs/` - session and tool handoffs
- `.dfw/` - project metadata and local state files

## Where to Start
- Read `context/_ACTIVE_CONTEXT.md` for current status and priorities
- Read `plans/_TODO.md` for the active implementation queue
- Read `plans/_ROADMAP.md` for phase history and current hardening wave
