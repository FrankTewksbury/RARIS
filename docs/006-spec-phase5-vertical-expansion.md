---
type: spec
created: 2026-02-25
source: claude-code
description: Phase 5 — Vertical Expansion, packaged applications, onboarding playbook
tags: [raris, phase5, spec, "#status/backlog", "#priority/normal"]
---

# Phase 5 — Vertical Expansion & Packaging Specification

## Overview

Phase 5 proves that the RARIS pipeline generalizes beyond Insurance. It onboards
at least two additional regulatory verticals end-to-end (discovery → acquisition →
ingestion → retrieval) and packages the system into domain-specific applications
with preconfigured UIs.

---

## A. Vertical Onboarding Framework

### Onboarding Pipeline

Each new vertical follows a standardized process:

```
1. Domain Definition        → Natural language description + scope constraints
2. Domain Discovery         → Phase 1 agent produces manifest
3. Manifest Review          → Human validates and approves
4. Acquisition              → Phase 2 acquires sources
5. Ingestion & Curation     → Phase 3 processes into indexed corpus
6. Validation               → Retrieval quality tested against domain-specific queries
7. Packaging                → Domain-specific UI and API configuration
```

### Vertical Configuration

Each vertical is defined by a configuration file:

```yaml
vertical:
  id: "mortgage-fthb"
  name: "Mortgage — First-Time Homebuyers"
  domain_description: >
    All US mortgage regulations impacting first-time homebuyers, including
    federal lending laws, GSE guidelines, state-specific programs, and
    consumer protection regulations.

  scope:
    jurisdictions: ["federal", "state"]
    regulatory_bodies: []               # empty = discover all
    lines_of_business:
      - "mortgage origination"
      - "mortgage servicing"
      - "consumer lending"
      - "fair housing"
    exclusions:
      - "commercial real estate"
      - "agricultural lending"

  discovery:
    llm_provider: "openai"
    expected_source_count: 150-300
    coverage_target: 0.85

  acquisition:
    rate_limit_ms: 2000
    max_concurrent: 5
    timeout_seconds: 120

  evaluation:
    ground_truth_queries: "eval/mortgage-fthb-queries.yaml"
    precision_target: 0.80
    recall_target: 0.90
```

---

## B. Target Verticals

### Vertical 1: Mortgage / First-Time Homebuyers

| Attribute | Value |
|-----------|-------|
| Federal Bodies | CFPB, HUD, FHA, VA, USDA-RD, FHFA |
| GSEs | Fannie Mae, Freddie Mac, Ginnie Mae |
| State Bodies | 50 state banking/financial regulators |
| Key Regulations | TILA, RESPA, ECOA, HMDA, Fair Housing Act, HOEPA |
| Expected Sources | 150-300 |
| Complexity | High — multiple overlapping federal agencies + state variation |

### Vertical 2: Healthcare / Clinical Gig Platforms

| Attribute | Value |
|-----------|-------|
| Federal Bodies | CMS, HHS/OIG, DEA, FTC, DOL |
| State Bodies | 50 state medical boards, nursing boards |
| Professional Bodies | AMA, Joint Commission, NCQA |
| Key Regulations | HIPAA, Stark Law, Anti-Kickback, state licensure, telehealth |
| Expected Sources | 200-400 |
| Complexity | Very high — per-state licensure + federal billing + telehealth variation |

### Vertical 3: Financial Services / Banking (Stretch)

| Attribute | Value |
|-----------|-------|
| Federal Bodies | OCC, FDIC, Federal Reserve, CFPB, FinCEN, SEC |
| SROs | FINRA, MSRB |
| Key Regulations | Dodd-Frank, BSA/AML, CRA, UDAAP, Reg E, Reg DD |
| Expected Sources | 300-500 |
| Complexity | Very high — multiple prudential regulators + consumer protection |

---

## C. Packaged Applications

Thin UI layers over the Phase 4 API, preconfigured for specific use cases.

### Application 1: Regulatory Navigator

- **Purpose:** Interactive regulatory research tool for compliance teams
- **UI:** Query interface + citation explorer + regulatory map
- **Configuration:** Pre-loaded with one vertical's corpus
- **Target User:** Compliance officers, legal researchers

### Application 2: Compliance Checker

- **Purpose:** Gap analysis tool — compare internal policies against regulations
- **UI:** Upload policy document → see gaps, conflicts, coverage score
- **Configuration:** Cross-corpus analysis focused on gap detection
- **Target User:** Compliance managers, internal audit

### Application 3: Regulatory Change Monitor

- **Purpose:** Alert service for regulatory changes affecting a vertical
- **UI:** Dashboard with change feed, impact assessments, affected documents
- **Configuration:** Phase 6 change monitoring focused on one vertical
- **Target User:** Regulatory affairs teams

---

## D. FastAPI Endpoints

| Method | Path | Description |
|--------|------|-------------|
| GET | `/api/verticals` | List all configured verticals |
| POST | `/api/verticals` | Create a new vertical configuration |
| GET | `/api/verticals/{id}` | Get vertical details and pipeline status |
| POST | `/api/verticals/{id}/discover` | Trigger domain discovery for a vertical |
| POST | `/api/verticals/{id}/acquire` | Trigger acquisition for a vertical |
| POST | `/api/verticals/{id}/ingest` | Trigger ingestion for a vertical |
| GET | `/api/verticals/{id}/status` | Full pipeline status (discovery → indexed) |

---

## E. React UI — Vertical Onboarding Wizard

### Components

#### 1. Vertical Registry
- List of all verticals with pipeline status badges
- Status indicators per phase: Discovery / Acquisition / Ingestion / Indexed
- Source count, coverage score, last updated

#### 2. New Vertical Wizard
- Step 1: Domain description + scope constraints
- Step 2: LLM provider selection + discovery parameters
- Step 3: Review discovery results (manifest preview)
- Step 4: Approve and trigger acquisition
- Step 5: Monitor pipeline progress

#### 3. Pipeline Progress Tracker
- Unified view of all pipeline phases for a vertical
- Per-phase progress bars and status
- Error log and retry controls
- Estimated time remaining

#### 4. Cross-Vertical Dashboard
- Comparison table: source count, coverage score, index freshness per vertical
- Combined corpus statistics
- Query distribution across verticals

---

## F. Acceptance Criteria

- [ ] At least two additional verticals onboarded end-to-end (discovery → indexed)
- [ ] Vertical configuration YAML schema defined and validated
- [ ] Each vertical achieves ≥0.80 coverage score on domain discovery
- [ ] Each vertical achieves ≥0.80 Precision@10 on domain-specific queries
- [ ] At least one packaged application functional and usable
- [ ] Vertical Onboarding Wizard allows non-developer users to add a new vertical
- [ ] Onboarding playbook documented with step-by-step instructions
