---
type: project-overview
created: 2026-02-25
sessionId: S20260225_0002
source: cursor
status: active
tags: [raris, overview]
---

# RARIS — Project Overview

> **Research and Analysis of Regulatory Information System**

## Mission

RARIS is an AI-agent-driven platform that maps regulatory domains, discovers source
documents, and produces structured YAML manifests that drive automated web scraping
and content acquisition pipelines. It transforms fragmented, manual regulatory research
into a systematic, repeatable, and auditable process.

## Problem Statement

Regulatory research is manual, fragmented, and slow. Compliance teams, legal researchers,
and policy analysts spend hundreds of hours locating, organizing, and cross-referencing
regulatory materials across dozens of federal agencies, 50 state regulators, and hundreds
of municipal authorities — per domain.

RARIS automates domain mapping and source discovery using AI agents, producing structured
manifests that drive scraping and ingestion pipelines. The result is a curated, indexed
regulatory corpus with full provenance and citation chains.

## Scope

**Phase 1 first vertical:** All US Insurance regulation — federal agencies (CMS, HHS,
DOL, FIO, CFPB, SEC), national bodies (NAIC, NCOIL, IAIS), and all 50 state insurance
commissioner offices. Lines covered: Health, Property & Casualty, Life & Annuities,
Surplus Lines, Title.

Additional verticals (mortgage, medical/gig, others) are planned for Phase 5 after the
pipeline is proven on Insurance.

## Architecture Overview

RARIS is a full-stack application: Python/FastAPI backend, React/TypeScript frontend,
PostgreSQL database, and Redis job queue. The LLM provider is configurable at runtime
via the `LLM_PROVIDER` environment variable (supports OpenAI, Anthropic, and Gemini).
All services run via Docker Compose. See [ARCHITECTURE.md](ARCHITECTURE.md) for the
full system design, data flow diagrams, and service boundaries.

## Phase Summary

| Phase | Name | Description | Status |
|-------|------|-------------|--------|
| 0 | Project Foundation | Docker Compose, CI/CD, evaluation framework, backend/frontend skeletons | `#status/active` |
| 1 | Domain Discovery & Analysis | AI agent maps regulatory domains and produces YAML manifests; React review UI | `#status/backlog` |
| 2 | Data Acquisition | Web scraping engine, download adapters, acquisition monitor; raw staging layer | `#status/backlog` |
| 3 | Ingestion & Curation Engine | Format adapters, semantic chunking, indexing, quality gates | `#status/backlog` |
| 4 | Retrieval & Agent Layer | Hybrid search, citation provenance, cross-corpus analysis, developer API | `#status/backlog` |
| 5 | Vertical Expansion & Packaging | Additional regulatory domains, packaged applications, onboarding playbook | `#status/backlog` |
| 6 | Feedback & Continuous Curation | Response feedback, change monitoring, re-curation pipeline, accuracy dashboard | `#status/backlog` |

## Success Metrics

| Metric | Target | Phase |
|--------|--------|-------|
| **Manifest accuracy** | ≥95% of regulatory bodies and key sources identified per domain | Phase 1 |
| **Scrape completion rate** | ≥90% of manifest sources successfully acquired | Phase 2 |
| **Retrieval precision/recall** | Defined per Phase 4 evaluation framework | Phase 4 |
| **Time to domain manifest** | <4 hours agent runtime per domain | Phase 1 |

## Links

- [ARCHITECTURE.md](ARCHITECTURE.md) — Full-stack architecture, data flow, service map
- [Roadmap](../plans/_ROADMAP.md) — Phase 0-6 roadmap with exit criteria
- [Phase 0 Spec](001-spec-phase0-foundation.md) — Project Foundation
- [Phase 1 Spec](002-spec-phase1-domain-discovery.md) — Domain Discovery & Analysis
- [Phase 2 Spec](003-spec-phase2-data-acquisition.md) — Data Acquisition
- [TODO](../plans/_TODO.md) — Active task list
- [Decisions Log](../context/_DECISIONS_LOG.md) — Architectural decisions
