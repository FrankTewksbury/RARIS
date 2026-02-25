---
type: roadmap
project: raris
created: 2026-02-25
sessionId: S20260225_0002
source: cursor
updated: 2026-02-25
tags: [raris, roadmap]
---

# RARIS Roadmap

> Source of truth: [RARI Macro Development Plan v2.0](../research/001-research-macro-dev-plan-v2.md)

---

## Phase 0: Project Foundation `#status/active`

**Goal:** Scaffolding and governance layer — dev environment, CI/CD, evaluation framework.

**React UI Deliverable:** None (infrastructure only). Verify with `docker compose up`.

**Exit Criteria:**
- [ ] `docker compose up` starts all 4 services (backend, frontend, db, redis) with no errors
- [ ] CI pipeline runs on every PR and blocks merge on failure
- [ ] Evaluation framework has defined metrics and test harness skeleton
- [ ] Phase 1 spec reviewed and approved

---

## Phase 1: Domain Discovery & Analysis `#status/backlog`

**Goal:** AI agent maps regulatory domains and produces structured YAML manifests.

**React UI Deliverable:** Manifest Review Dashboard — domain input, agent progress stream,
source table with edit/approve/reject, coverage summary, manifest approval workflow.

**Exit Criteria:**
- [ ] Domain Discovery Agent accepts natural language domain description and produces valid YAML manifest
- [ ] Manifest schema defined, documented, and has a working validator
- [ ] Review UI allows full human approval workflow
- [ ] Insurance domain manifest produced, reviewed, and approved
- [ ] Phase 2 spec reviewed and approved

---

## Phase 2: Data Acquisition `#status/backlog`

**Goal:** Consume approved manifests and acquire actual regulatory content via scraping, download, and API adapters.

**React UI Deliverable:** Acquisition Monitor — run selector, per-source status table with
color-coded badges, error log panel, retry button, raw content preview modal.

**Exit Criteria:**
- [ ] All acquisition adapters functional and tested against real sources
- [ ] Insurance manifest sources successfully acquired and staged
- [ ] Monitoring dashboard operational with SSE progress stream
- [ ] Raw staging layer populated with validated content and provenance
- [ ] Phase 3 spec reviewed and approved

---

## Phase 3: Ingestion & Curation Engine `#status/backlog`

**Goal:** Transform raw acquired content into structured, enriched, queryable knowledge.

**React UI Deliverable:** Curation Dashboard — document status pipeline view, quality gate
results, curation approval workflow, index health metrics.

**Exit Criteria:**
- [ ] All ingestion adapters (PDF, HTML, legal XML, guide, plaintext) implemented and tested
- [ ] Curation pipeline enriches and validates documents end-to-end
- [ ] Quality gates catch known failure modes
- [ ] Semantic chunking preserves regulatory text integrity
- [ ] Hybrid index supports retrieval queries
- [ ] Insurance corpus fully ingested, curated, and indexed
- [ ] Phase 4 spec reviewed and approved

---

## Phase 4: Retrieval & Agent Layer `#status/backlog`

**Goal:** Agent-based retrieval with tunable depth, citation provenance, and cross-corpus analysis.

**React UI Deliverable:** Query Interface — natural language input, tunable depth selector,
results with citation chains, cross-corpus comparison view, developer API docs.

**Exit Criteria:**
- [ ] Retrieval engine returns accurate results with measurable precision/recall
- [ ] Agent produces tunable-depth responses with full citation chains
- [ ] Cross-corpus analysis functional for document comparison
- [ ] Developer API serves retrieval and analysis endpoints
- [ ] Evaluation framework scores meet defined accuracy thresholds
- [ ] Phase 5 spec reviewed and approved

---

## Phase 5: Vertical Expansion & Packaging `#status/backlog`

**Goal:** Onboard additional regulatory verticals and package the agent for specific use cases.

**React UI Deliverable:** Vertical Onboarding Wizard — domain selector, pipeline progress
tracker, packaged application launchers.

**Exit Criteria:**
- [ ] At least two additional verticals onboarded end-to-end
- [ ] Packaged applications functional for defined use cases
- [ ] Vertical onboarding playbook documented and validated

---

## Phase 6: Feedback & Continuous Curation `#status/backlog`

**Goal:** Closed-loop system for accuracy improvement — feedback capture, change monitoring, re-curation.

**React UI Deliverable:** Accuracy Dashboard — feedback volume, resolution rate, accuracy
trends, curation health metrics, regulatory change alerts.

**Exit Criteria:**
- [ ] Feedback from retrieval propagates back to curation with no manual intervention
- [ ] Change monitoring detects real regulatory updates
- [ ] Re-curation pipeline handles flagged and changed sources end-to-end
- [ ] Accuracy trends measurable and visible
