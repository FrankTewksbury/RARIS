---
type: spec
created: 2026-02-25
source: claude-code
description: Phase 6 — Feedback capture, change monitoring, re-curation, accuracy dashboard
tags: [raris, phase6, spec, "#status/backlog", "#priority/normal"]
---

# Phase 6 — Feedback & Continuous Curation Specification

## Overview

Phase 6 closes the loop. User feedback on retrieval responses propagates back to
the curation layer. Regulatory change monitoring detects source updates. Both
trigger re-acquisition and re-curation automatically. The result is a corpus that
improves and stays current without manual intervention.

---

## A. Response Feedback Capture

### Feedback Types

| Type | Signal | Action |
|------|--------|--------|
| **Inaccurate** | Claim doesn't match cited source | Trace citation → flag chunk + document |
| **Outdated** | Information is no longer current | Flag source for re-acquisition |
| **Incomplete** | Query topic not covered | Flag coverage gap in manifest |
| **Irrelevant** | Retrieved chunks not relevant to query | Adjust index weights |
| **Correct** | Response is accurate and helpful | Positive signal for scoring |

### Feedback Model

```python
class ResponseFeedback:
    id: str
    query_id: str                     # The original query
    response_id: str                  # The agent response
    feedback_type: FeedbackType       # inaccurate | outdated | incomplete | irrelevant | correct
    citation_id: str | None           # Specific citation being flagged (if applicable)
    description: str                  # Free-text explanation
    submitted_by: str                 # User or API key identifier
    submitted_at: datetime
    status: FeedbackStatus            # pending | investigating | resolved | dismissed
    resolution: str | None            # What was done to address the feedback
    resolved_at: datetime | None
```

### Feedback Flow

```
User flags response
        │
        ▼
  Feedback recorded
        │
        ├──▶ Inaccurate → Trace citation chain → Flag source for review
        ├──▶ Outdated → Flag source for re-acquisition
        ├──▶ Incomplete → Flag coverage gap → Queue re-discovery
        ├──▶ Irrelevant → Log for retrieval tuning
        └──▶ Correct → Positive signal, no action needed
```

---

## B. Feedback-to-Source Tracer

When a response is flagged, the tracer follows the citation chain back to its origin.

### Trace Steps

```
Flagged Response
    │
    ▼
Flagged Citation (chunk_id)
    │
    ▼
Source Chunk → Document → Staged Document → Manifest Source
    │
    ▼
Source flagged in manifest:
  - confidence score reduced
  - needs_human_review = true
  - flag_reason recorded
    │
    ▼
Source enters Re-Curation Queue
```

### Auto-Actions by Feedback Type

| Feedback Type | Auto-Action |
|--------------|-------------|
| Inaccurate | Reduce source confidence by 0.1, flag chunk for review |
| Outdated | Queue source for re-acquisition |
| Incomplete | Create coverage gap entry in manifest |
| Irrelevant | Log query-chunk pair as negative example for retrieval tuning |
| Correct | Increase source confidence by 0.05 (cap at 1.0) |

---

## C. Re-Curation Queue

Flagged sources enter a priority queue for re-processing.

### Queue Priority

| Priority | Trigger | SLA |
|----------|---------|-----|
| Critical | Multiple inaccuracy reports on same source | 24 hours |
| High | Outdated flag on binding authority source | 48 hours |
| Medium | Single flag or coverage gap | 1 week |
| Low | Scheduled refresh | Next maintenance window |

### Re-Curation Pipeline

```
Flagged Source
    │
    ├──▶ Re-Acquire (Phase 2 adapter)
    │         │
    │         ▼
    │    Compare with previous version
    │         │
    │         ├──▶ Content changed → Re-ingest → Re-index
    │         └──▶ Content unchanged → Mark as verified
    │
    ├──▶ Re-Discover (Phase 1 agent, targeted)
    │         │
    │         ▼
    │    Check for new sources in flagged area
    │         │
    │         └──▶ New sources found → Add to manifest → Acquire → Ingest
    │
    └──▶ Manual Review Queue
              │
              ▼
         Human reviewer resolves flag
```

---

## D. Regulatory Change Monitoring

Proactive detection of changes in known regulatory sources.

### Monitoring Strategy

| Method | Frequency | Scope |
|--------|-----------|-------|
| **Content hash check** | Daily | All indexed sources with `access_method: scrape\|download` |
| **RSS/Atom feeds** | Real-time | Regulatory bodies with published feeds |
| **Federal Register API** | Daily | Federal regulatory actions (proposed rules, final rules) |
| **Last-Modified header** | Daily | Sources with reliable HTTP headers |

### Change Detection Flow

```
Scheduled Monitor Run
    │
    ├──▶ HTTP HEAD on each source URL
    │         │
    │         ├──▶ Last-Modified changed → Queue for re-acquisition
    │         ├──▶ Content-Length changed → Queue for re-acquisition
    │         └──▶ No change → Log and skip
    │
    ├──▶ RSS/Atom feed check
    │         │
    │         └──▶ New entries → Match against manifest sources → Queue affected
    │
    └──▶ Federal Register API poll
              │
              └──▶ New actions matching domain keywords → Create alerts
```

### Change Event Model

```python
class ChangeEvent:
    id: str
    source_id: str
    manifest_id: str
    detected_at: datetime
    detection_method: str          # hash_check | rss | federal_register | manual
    change_type: str               # content_update | new_document | supersession | removal
    previous_hash: str | None
    current_hash: str | None
    description: str
    status: str                    # detected | processing | resolved | dismissed
    impact_assessment: str | None  # LLM-generated summary of what changed
```

---

## E. FastAPI Endpoints

| Method | Path | Description |
|--------|------|-------------|
| POST | `/api/feedback` | Submit feedback on a query response |
| GET | `/api/feedback` | List all feedback (filterable by status, type) |
| GET | `/api/feedback/{id}` | Get feedback details with trace |
| PATCH | `/api/feedback/{id}/resolve` | Mark feedback as resolved |
| GET | `/api/curation-queue` | List items in re-curation queue |
| POST | `/api/curation-queue/{id}/process` | Trigger re-curation for a queued item |
| GET | `/api/changes` | List detected regulatory changes |
| GET | `/api/changes/{id}` | Get change event details |
| POST | `/api/monitor/run` | Trigger a manual change monitoring run |
| GET | `/api/accuracy/dashboard` | Accuracy metrics and trends |

---

## F. React UI — Accuracy Dashboard

### Components

#### 1. Feedback Feed
- Real-time feed of incoming feedback
- Filter by type, status, severity
- Quick-resolve actions (dismiss, investigate, escalate)
- Trend sparkline (feedback volume over time)

#### 2. Re-Curation Queue
- Priority-sorted list of flagged sources
- Status badges: pending → processing → resolved
- One-click re-acquisition and re-ingestion triggers
- SLA countdown timers

#### 3. Change Monitor
- Timeline of detected regulatory changes
- Change events grouped by regulatory body
- Impact assessment summaries
- "Process" button to trigger re-acquisition

#### 4. Accuracy Trends
- Line chart: accuracy score over time (30/60/90 day windows)
- Breakdown by vertical, jurisdiction, document type
- Feedback resolution rate (% resolved within SLA)
- Source confidence distribution histogram

#### 5. Corpus Health
- Per-vertical health score (freshness + accuracy + coverage)
- Stale source alerts (sources not re-checked in >30 days)
- Coverage gap summary across all verticals
- Re-curation success rate

---

## G. Acceptance Criteria

- [ ] Users can submit feedback on query responses with specific citation references
- [ ] Feedback tracer correctly identifies source documents from citation chains
- [ ] Inaccuracy feedback auto-reduces source confidence and flags for review
- [ ] Outdated feedback triggers automatic re-acquisition of the flagged source
- [ ] Re-curation pipeline processes flagged sources end-to-end (re-acquire → re-ingest → re-index)
- [ ] Change monitoring detects content changes on at least 5 real regulatory sources
- [ ] Federal Register API integration detects new regulatory actions matching domain keywords
- [ ] Accuracy Dashboard shows feedback trends, resolution rates, and corpus health
- [ ] No manual intervention required for the feedback → re-curation → re-index cycle
- [ ] Accuracy trends are measurable across 30-day windows
