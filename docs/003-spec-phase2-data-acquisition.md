---
type: spec
created: 2026-02-25
sessionId: S20260225_0002
source: cursor
description: Phase 2 — Data Acquisition, web scraping engine, acquisition monitor UI
tags: [raris, phase2, spec, "#status/backlog", "#priority/important"]
---

# Phase 2 — Data Acquisition Specification

## Overview

Phase 2 consumes approved YAML manifests from Phase 1 and acquires the actual regulatory
content. The manifest's `access_method` field drives routing: `scrape` goes to the
web scraping engine, `download` goes to direct fetch, `api` goes to API adapters,
and `manual` flags sources for human acquisition.

---

## A. Acquisition Orchestrator

The orchestrator is the central coordinator for all data acquisition activity.

### Responsibilities
- Reads an approved manifest from PostgreSQL
- Routes each source entry by `access_method` field:
  - `scrape` → Web Scraping Engine
  - `download` → Direct Download Adapter
  - `api` → API Adapter (stub for Phase 2, full implementation Phase 3)
  - `manual` → flags for human acquisition, skips automated pipeline
- Manages the Redis job queue: enqueues jobs, tracks state, handles retries
- Retry logic: 3 attempts with exponential backoff (1s, 4s, 16s)
- Maintains per-source progress state: `pending` → `running` → `complete` / `failed` / `retrying`
- Emits SSE progress events for the acquisition monitor UI

### Orchestrator Flow

```
Approved Manifest (PostgreSQL)
         │
         ▼
  ┌──────────────┐
  │ Orchestrator  │
  │   (FastAPI)   │
  └──────┬───────┘
         │
    ┌────┼────┬────────┐
    ▼    ▼    ▼        ▼
 scrape  dl   api    manual
    │    │    │        │
    ▼    ▼    ▼        ▼
 Redis  Redis Redis  (skip)
 Queue  Queue Queue
    │    │    │
    ▼    ▼    ▼
Workers process jobs
    │    │    │
    ▼    ▼    ▼
   Raw Staging Layer
```

---

## B. Web Scraping Engine

### Architecture
- **Firecrawl** for JS-rendered pages — regulatory bodies that require browser execution
  (e.g., state agency sites with dynamic navigation, interactive rate filing portals)
- **Crawlee** for static HTML — multi-page crawls, table of contents traversal,
  paginated document listings

### Job Schema

```json
{
  "job_id": "acq-001-src-001",
  "source_id": "src-001",
  "manifest_id": "rori-manifest-insurance-001",
  "url": "https://www.consumerfinance.gov/rules-policy/regulations/1026/",
  "scraping_notes": "Multi-page HTML with section navigation. JS rendering required.",
  "depth": 2,
  "output_format": "html",
  "tool": "firecrawl",
  "rate_limit_ms": 2000
}
```

### Output
Raw content in a standardized provenance envelope (see Raw Staging Layer schema).

### Rate Limiting
- Per-domain configurable rate limiting
- Default: 1 request per 2 seconds
- Configurable via manifest `scraping_notes` or orchestrator config
- Respects `robots.txt` directives

---

## C. Direct Download Adapter

### Responsibilities
- HTTP fetch for direct-URL PDFs and structured files
- Content-type validation (verify response matches expected format from manifest)
- File integrity check (SHA-256 hash computed on download)
- Handles redirect chains (up to 5 redirects)
- Supports authentication headers where needed (configured per-source)

### Download Flow

```
Source URL → HTTP GET → Follow redirects → Validate content-type
    → Compute SHA-256 → Write to staging path → Create provenance envelope
```

---

## D. Raw Staging Layer Schema

Every acquired document is stored with full provenance metadata:

```yaml
staged_document:
  id: "stg-001"
  manifest_id: "rori-manifest-insurance-001"
  source_id: "src-001"
  acquisition_method: "scrape"          # scrape | download | api | manual
  acquired_at: "2026-02-25T00:00:00Z"
  content_hash: "sha256:..."
  content_type: "text/html"             # text/html | application/pdf | application/xml
  raw_content_path: "staging/rori-manifest-insurance-001/src-001/"
  byte_size: 0
  status: "staged"                      # staged | validation_failed | duplicate
  provenance:
    source_url: "https://example.gov/regulation"
    scraping_tool: "firecrawl"          # firecrawl | crawlee | requests | manual
    tool_version: "1.0.0"
    acquisition_duration_ms: 0
    http_status: 200
```

### Storage Layout

```
staging/
  rori-manifest-insurance-001/
    src-001/
      content.html          # raw acquired content
      provenance.yaml       # provenance envelope
      metadata.json         # extracted metadata
    src-002/
      content.pdf
      provenance.yaml
      metadata.json
```

### Deduplication
- Content hash (SHA-256) is computed for every acquired document
- If a document with the same hash already exists in staging, status is set to `duplicate`
  and the content is not re-stored
- Deduplication is per-manifest (same source re-acquired) and cross-manifest (same
  document discovered in multiple domains)

---

## E. FastAPI Endpoint Specifications

### Endpoints

| Method | Path | Description |
|--------|------|-------------|
| POST | `/api/acquisitions` | Start acquisition run for an approved manifest |
| GET | `/api/acquisitions/{id}` | Get acquisition run status + summary |
| GET | `/api/acquisitions/{id}/stream` | SSE stream of per-source progress events |
| GET | `/api/acquisitions/{id}/sources` | All source statuses for a run |
| GET | `/api/acquisitions/{id}/sources/{src_id}` | Single source status + staged document |
| POST | `/api/acquisitions/{id}/sources/{src_id}/retry` | Retry a failed source |
| GET | `/api/acquisitions` | List all acquisition runs |

### Request/Response Schemas

#### `POST /api/acquisitions`

Request:
```json
{
  "manifest_id": "rori-manifest-insurance-001"
}
```

Precondition: Manifest must have `status: "approved"`.

Response (`202 Accepted`):
```json
{
  "acquisition_id": "acq-001",
  "manifest_id": "rori-manifest-insurance-001",
  "status": "running",
  "total_sources": 250,
  "stream_url": "/api/acquisitions/acq-001/stream"
}
```

#### `GET /api/acquisitions/{id}`

Response (`200 OK`):
```json
{
  "acquisition_id": "acq-001",
  "manifest_id": "rori-manifest-insurance-001",
  "status": "running",
  "started_at": "2026-02-25T00:00:00Z",
  "elapsed_seconds": 3600,
  "total_sources": 250,
  "completed": 180,
  "failed": 5,
  "pending": 60,
  "retrying": 5
}
```

#### `GET /api/acquisitions/{id}/stream`

SSE event stream:
```
event: source_start
data: {"source_id": "src-001", "name": "TILA / Regulation Z", "method": "scrape"}

event: source_complete
data: {"source_id": "src-001", "staged_id": "stg-001", "duration_ms": 5200, "byte_size": 245000}

event: source_failed
data: {"source_id": "src-015", "error": "HTTP 403 Forbidden", "retry_count": 1, "next_retry_at": "..."}

event: progress
data: {"completed": 45, "failed": 2, "pending": 203, "retrying": 0}
```

#### `GET /api/acquisitions/{id}/sources`

Response (`200 OK`):
```json
{
  "sources": [
    {
      "source_id": "src-001",
      "name": "TILA / Regulation Z",
      "regulatory_body": "cfpb",
      "access_method": "scrape",
      "status": "complete",
      "duration_ms": 5200,
      "staged_document_id": "stg-001",
      "error": null
    }
  ]
}
```

#### `POST /api/acquisitions/{id}/sources/{src_id}/retry`

Response (`202 Accepted`):
```json
{
  "source_id": "src-015",
  "status": "retrying",
  "retry_count": 2,
  "message": "Source re-queued for acquisition"
}
```

---

## F. React UI — Acquisition Monitor Dashboard

### Components

#### 1. Run Selector
- Dropdown of approved manifests (from `GET /api/manifests?status=approved`)
- "Start Acquisition" button → calls `POST /api/acquisitions`
- Shows active acquisition runs with status badges

#### 2. Run Summary Card
- Manifest name and domain
- Total sources count
- Completed / Failed / Pending / Retrying counts
- Elapsed time (live counter)
- Overall progress bar (completed / total)

#### 3. Sources Status Table
- **Columns:** Source Name, Regulatory Body, Access Method, Status, Duration, Error Message
- **Status badges:** color-coded
  - `pending` — gray
  - `running` — blue (animated)
  - `complete` — green
  - `failed` — red
  - `retrying` — orange
- **Row click:** opens Raw Content Viewer modal for completed sources
- **Pagination:** 25 rows per page
- **Filters:** by status, by access_method

#### 4. Error Log Panel
- Filterable list of failed sources
- Shows: source name, error message, retry count, last attempt timestamp
- **Retry button** per row → calls `POST /api/acquisitions/{id}/sources/{src_id}/retry`
- Bulk retry option for all failed sources

#### 5. Raw Content Viewer
- Modal triggered by clicking a completed source row
- Shows staged document metadata: content type, byte size, content hash, provenance
- Content preview: first 500 lines for text/HTML, PDF thumbnail for PDFs
- Download link for raw content

---

## G. Acceptance Criteria

- [ ] Orchestrator correctly routes all `access_method` types from a real manifest
- [ ] Web scraping engine acquires at least 10 real insurance regulatory sources successfully
- [ ] Direct download adapter handles PDF sources from manifest
- [ ] Raw staging layer stores acquired content with full provenance metadata
- [ ] Acquisition monitor UI shows real-time progress via SSE stream
- [ ] Failed sources can be retried from the UI without restarting the full run
- [ ] Insurance corpus: ≥80% of manifest sources successfully acquired and staged
