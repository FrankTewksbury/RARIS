---
type: spec
created: 2026-02-25
sessionId: S20260225_0002
source: cursor
description: Phase 1 — Domain Discovery Agent, YAML manifest schema, React review UI
tags: [raris, phase1, spec, "#status/backlog", "#priority/critical"]
---

# Phase 1 — Domain Discovery & Analysis Specification

## Overview

Phase 1 is where RARIS starts. Before anything can be scraped, ingested, or indexed,
the system must learn about the target regulatory domain — what regulatory bodies exist,
what statutes and guides apply, how they're organized, where the source documents live,
and how they relate to each other.

Domain Discovery is an AI-agent-driven research process that takes a domain description
as input and produces a structured YAML manifest as output. That manifest is the contract
between Phase 1 and Phase 2.

---

## A. Domain Discovery Agent Architecture

The agent executes five sub-components in sequence:

### 1. Landscape Mapper
- Identifies regulatory bodies, authority hierarchy, and jurisdiction levels
- Builds the hierarchy: federal → state → local
- Maps primary legislation → implementing regulations → guidance → standards
- Output: `domain_map.regulatory_bodies` and `domain_map.jurisdiction_hierarchy`

### 2. Source Hunter
- For each regulatory body, finds specific statutes, rules, guides, directives, and
  educational materials
- Captures: URLs, document types, formats, publication dates, update frequencies,
  access methods
- Output: `sources[]` entries with metadata

### 3. Relationship Mapper
- Maps cross-references between documents
- Identifies supersession chains (what replaced what)
- Determines applicability hierarchies (which rules apply to which entities)
- Output: `sources[].relationships` fields

### 4. Coverage Assessor
- Evaluates completeness of discovered sources against expected regulatory coverage
- Identifies gaps — known regulatory areas with missing or inaccessible sources
- Assigns confidence scores per source and overall completeness score
- Flags items needing human review
- Output: `coverage_assessment` section

### 5. Manifest Generator
- Assembles all sub-component outputs into a validated YAML manifest
- Runs schema validation before output
- Flags items with low confidence for human review
- Output: Complete manifest with `status: "pending_review"`

### Tools Available to the Agent

| Tool | Purpose |
|------|---------|
| **Web Search** | Find regulatory bodies, source documents, legal databases |
| **Web Fetch** | Read agency homepages, regulation indexes, table of contents pages |
| **LLM Reasoning** | Classify sources, map relationships, assess coverage |
| **Schema Validator** | Validate produced manifest against YAML schema before output |

**Important:** The agent DISCOVERS — it does NOT scrape. Actual content acquisition
happens in Phase 2.

---

## B. LLM Provider Abstraction

```python
from abc import ABC, abstractmethod
from typing import AsyncIterator

class LLMProvider(ABC):
    @abstractmethod
    async def complete(self, messages: list[dict], **kwargs) -> str:
        """Send messages and return a complete response."""
        ...

    @abstractmethod
    async def stream(self, messages: list[dict], **kwargs) -> AsyncIterator[str]:
        """Send messages and stream response tokens."""
        ...

class OpenAIProvider(LLMProvider): ...
class AnthropicProvider(LLMProvider): ...
class GeminiProvider(LLMProvider): ...

# Selected by LLM_PROVIDER env var
providers: dict[str, type[LLMProvider]] = {
    "openai": OpenAIProvider,
    "anthropic": AnthropicProvider,
    "gemini": GeminiProvider,
}
```

---

## C. YAML Manifest Schema

```yaml
manifest:
  id: "rori-manifest-{domain}-{seq}"
  domain: "Domain description"
  created: "ISO-8601 timestamp"
  created_by: "domain-discovery-agent-v1"
  version: 1
  status: "pending_review"  # pending_review | approved | active | archived

  domain_map:
    regulatory_bodies:
      - id: "string"                          # REQUIRED — unique identifier
        name: "string"                        # REQUIRED — full name
        jurisdiction: "string"                # REQUIRED — federal | state | municipal
        authority_type: "string"              # REQUIRED — regulator | gse | sro | industry_body
        url: "string"                         # REQUIRED — primary URL
        governs:                              # list of governed areas
          - "string"

    jurisdiction_hierarchy:
      - level: "federal"                      # REQUIRED
        sources_count: 0                      # populated by agent
        children:
          - level: "state"
            sources_count: 0
            children:
              - level: "municipal"
                sources_count: 0

  sources:
    - id: "string"                            # REQUIRED — unique identifier (src-NNN)
      name: "string"                          # REQUIRED — document/source name
      regulatory_body: "string"               # REQUIRED — references regulatory_bodies[].id
      type: "string"                          # REQUIRED — enum: statute | regulation | guidance | standard | educational | guide
      format: "string"                        # REQUIRED — enum: html | pdf | legal_xml | api | structured_data
      authority: "string"                     # REQUIRED — enum: binding | advisory | informational
      jurisdiction: "string"                  # REQUIRED — enum: federal | state | municipal
      url: "string"                           # REQUIRED — source URL
      access_method: "string"                 # REQUIRED — enum: scrape | download | api | manual
      update_frequency: "string"              # enum: annual | quarterly | as_amended | static | unknown
      last_known_update: "string"             # ISO date or empty
      estimated_size: "string"                # enum: small (<50 pages) | medium (50-500) | large (500+)
      scraping_notes: "string"                # free text — tips for the acquisition phase
      relationships:
        supersedes: []                        # list of source IDs
        superseded_by: []                     # list of source IDs
        cross_references: []                  # list of source IDs
        implements: "string"                  # statutory authority reference
      classification_tags: []                 # list of domain-specific tags
      confidence: 0.0                         # 0.0-1.0 — agent's confidence in accuracy
      needs_human_review: false               # boolean
      review_notes: "string"                  # reviewer comments

  coverage_assessment:
    total_sources: 0                          # populated by agent
    by_jurisdiction:
      federal: 0
      state: 0
      municipal: 0
    by_type:
      statute: 0
      regulation: 0
      guidance: 0
      standard: 0
      educational: 0
      guide: 0
    known_gaps:
      - description: "string"
        severity: "string"                    # enum: high | medium | low
        mitigation: "string"
    completeness_score: 0.0                   # 0.0-1.0

  review_history:
    - date: "string"
      reviewer: "string"
      action: "string"                        # enum: approved | revised | rejected
      notes: "string"
```

### Schema Validation Rules

| Field | Rule |
|-------|------|
| `manifest.id` | Required. Must be unique. Pattern: `rori-manifest-{domain}-{seq}` |
| `manifest.status` | Required. Must be one of: `pending_review`, `approved`, `active`, `archived` |
| `sources[].id` | Required. Must be unique within the manifest. Pattern: `src-NNN` |
| `sources[].type` | Required. Must be one of: `statute`, `regulation`, `guidance`, `standard`, `educational`, `guide` |
| `sources[].format` | Required. Must be one of: `html`, `pdf`, `legal_xml`, `api`, `structured_data` |
| `sources[].authority` | Required. Must be one of: `binding`, `advisory`, `informational` |
| `sources[].access_method` | Required. Must be one of: `scrape`, `download`, `api`, `manual` |
| `sources[].confidence` | Required. Must be between 0.0 and 1.0 |
| `sources[].regulatory_body` | Required. Must reference a valid `regulatory_bodies[].id` |
| `coverage_assessment.completeness_score` | Required. Must be between 0.0 and 1.0 |

---

## D. FastAPI Endpoint Specifications

### Endpoints

| Method | Path | Description |
|--------|------|-------------|
| POST | `/api/manifests/generate` | Start agent run for a domain description |
| GET | `/api/manifests/{id}` | Get manifest with all sources |
| GET | `/api/manifests/{id}/stream` | SSE stream of agent progress events |
| GET | `/api/manifests` | List all manifests |
| PATCH | `/api/manifests/{id}/sources/{src_id}` | Edit a source entry |
| POST | `/api/manifests/{id}/sources` | Add a source manually |
| POST | `/api/manifests/{id}/approve` | Approve manifest (status → approved) |
| POST | `/api/manifests/{id}/reject` | Reject manifest with notes |

### Request/Response Schemas

#### `POST /api/manifests/generate`

Request:
```json
{
  "domain_description": "All US Insurance regulation — federal + all 50 states",
  "llm_provider": "openai"
}
```

Response (`202 Accepted`):
```json
{
  "manifest_id": "rori-manifest-insurance-001",
  "status": "generating",
  "stream_url": "/api/manifests/rori-manifest-insurance-001/stream"
}
```

#### `GET /api/manifests/{id}`

Response (`200 OK`):
```json
{
  "manifest": {
    "id": "rori-manifest-insurance-001",
    "domain": "All US Insurance regulation",
    "status": "pending_review",
    "created": "2026-02-25T00:00:00Z",
    "sources_count": 250,
    "coverage_score": 0.85,
    "sources": [ ... ],
    "domain_map": { ... },
    "coverage_assessment": { ... }
  }
}
```

#### `GET /api/manifests/{id}/stream`

SSE event stream:
```
event: step
data: {"step": "landscape_mapper", "status": "running", "message": "Identifying federal regulatory bodies..."}

event: step
data: {"step": "landscape_mapper", "status": "complete", "bodies_found": 12}

event: step
data: {"step": "source_hunter", "status": "running", "message": "Discovering sources for NAIC..."}

event: progress
data: {"sources_found": 45, "bodies_processed": 5, "total_bodies": 12}

event: complete
data: {"manifest_id": "rori-manifest-insurance-001", "total_sources": 250, "coverage_score": 0.85}
```

#### `GET /api/manifests`

Response (`200 OK`):
```json
{
  "manifests": [
    {
      "id": "rori-manifest-insurance-001",
      "domain": "All US Insurance regulation",
      "status": "pending_review",
      "created": "2026-02-25T00:00:00Z",
      "sources_count": 250,
      "coverage_score": 0.85
    }
  ]
}
```

#### `PATCH /api/manifests/{id}/sources/{src_id}`

Request:
```json
{
  "name": "Updated source name",
  "url": "https://updated-url.gov",
  "needs_human_review": false,
  "review_notes": "Verified URL is correct"
}
```

Response (`200 OK`): Updated source object.

#### `POST /api/manifests/{id}/sources`

Request:
```json
{
  "name": "Manually added source",
  "regulatory_body": "naic",
  "type": "guidance",
  "format": "pdf",
  "authority": "advisory",
  "jurisdiction": "federal",
  "url": "https://example.gov/doc.pdf",
  "access_method": "download",
  "confidence": 1.0,
  "needs_human_review": false
}
```

Response (`201 Created`): Created source object with auto-generated `id`.

#### `POST /api/manifests/{id}/approve`

Request:
```json
{
  "reviewer": "frank",
  "notes": "All sources verified. Ready for acquisition."
}
```

Response (`200 OK`):
```json
{
  "manifest_id": "rori-manifest-insurance-001",
  "status": "approved",
  "approved_at": "2026-02-25T00:00:00Z"
}
```

Precondition: All sources with `needs_human_review: true` must have been reviewed (flag set to `false`).

#### `POST /api/manifests/{id}/reject`

Request:
```json
{
  "reviewer": "frank",
  "notes": "Missing state regulators for AK, HI. Needs re-run."
}
```

Response (`200 OK`):
```json
{
  "manifest_id": "rori-manifest-insurance-001",
  "status": "pending_review",
  "rejection_notes": "Missing state regulators for AK, HI. Needs re-run."
}
```

---

## E. React UI — Manifest Review Dashboard

### Components

#### 1. Domain Input Panel
- Text area for domain description (e.g., "All US Insurance regulation")
- Model selector dropdown: `openai` / `anthropic` / `gemini`
- "Generate Manifest" button → calls `POST /api/manifests/generate`
- Disabled while an agent run is in progress

#### 2. Agent Progress Panel
- SSE-connected live log of agent steps via `/api/manifests/{id}/stream`
- Progress bar with labeled stages:
  `Landscape → Sources → Relationships → Coverage → Manifest`
- Current step highlighted, completed steps checked
- Real-time source count and bodies processed

#### 3. Manifest Summary Card
- Domain name
- Total sources count
- Coverage score (displayed as percentage with color: green ≥0.85, yellow ≥0.70, red <0.70)
- Status badge: `pending_review` (yellow) / `approved` (green) / `rejected` (red)
- Created timestamp

#### 4. Sources Table
- **Columns:** ID, Name, Regulatory Body, Type, Format, Authority, Jurisdiction,
  Confidence Score, Needs Review (flag icon)
- **Row actions:** Edit (inline), Approve source, Reject source
- **Filters:** by Jurisdiction, by Type, by `needs_review` status
- **Sort:** by Confidence (ascending — low confidence first for review prioritization)
- **Pagination:** 25 rows per page

#### 5. Coverage Summary
- Breakdown by jurisdiction: Federal / State / Municipal (bar chart)
- Breakdown by type: Statute / Regulation / Guidance / Standard / Educational (pie chart)
- Known gaps list with severity badges (high=red, medium=yellow, low=blue)

#### 6. Approve / Request Revision Buttons
- **Approve Manifest** — calls `POST /api/manifests/{id}/approve`
  - Gated: disabled until all sources with `needs_human_review: true` have been reviewed
  - Shows count of remaining items to review
- **Request Revision** — calls `POST /api/manifests/{id}/reject` with notes modal

---

## F. Insurance Domain First Run Plan

### Federal Bodies
| ID | Name | Key Areas |
|----|------|-----------|
| `cms` | Centers for Medicare & Medicaid Services | Medicare, Medicaid, ACA marketplace |
| `hhs` | Dept. of Health and Human Services | ACA implementation, essential health benefits |
| `dol` | Dept. of Labor | ERISA, employee benefit plans |
| `fio` | Federal Insurance Office (Treasury) | Systemic risk monitoring, international insurance |
| `cfpb` | Consumer Financial Protection Bureau | Credit insurance, consumer complaints |
| `sec` | Securities and Exchange Commission | Variable annuities, insurance-linked securities |

### National Bodies
| ID | Name | Key Areas |
|----|------|-----------|
| `naic` | National Association of Insurance Commissioners | Model laws, IRIS ratios, FAST database, accreditation |
| `ncoil` | National Council of Insurance Legislators | Model legislation for state adoption |
| `iais` | International Association of Insurance Supervisors | Insurance Core Principles, global standards |

### State Regulators
All 50 state insurance commissioner/department offices. Each state maintains its own
insurance code, rate filings, market conduct standards, and consumer protection rules.

### Lines Covered
- **Health** — individual, group, Medicare supplement, managed care
- **Property & Casualty** — homeowners, auto, commercial, workers' comp
- **Life & Annuities** — term, whole, universal, variable, fixed annuities
- **Surplus Lines** — non-admitted carriers, excess liability
- **Title** — title insurance, title agents, search standards

### Estimated Source Count
200–400 entries across all bodies and lines.

---

## G. Acceptance Criteria

- [ ] Agent accepts a plain-language domain description and produces a valid YAML manifest
- [ ] Manifest schema validator passes on all agent-produced manifests
- [ ] React UI allows full review workflow: view → edit → approve per source → approve manifest
- [ ] Insurance domain run produces a manifest with ≥50 source entries and coverage score ≥0.80
- [ ] Approved manifest is the input contract for Phase 2
