---
type: specification
project: RORI
component: collect/web-scraping-infra
version: 1.0
created: 2026-02-13
updated: 2026-02-13
status: draft
authors: [Frank, Candi]
parent: RORI_MACRO_DEVELOPMENT_PLAN_v1.1.md
branch: collect/web-scraping-infra
---

# RORI Web Scraping Infrastructure — Specification v1.0

## `collect/web-scraping-infra`

---

## 1. Purpose

This specification defines the architecture, tooling, data flow, and output schema for RORI's automated web scraping infrastructure. The system scrapes public regulatory data from approved manifest sources, stages it in a standardized raw format with full metadata, and delivers it to the Phase 1 ingestion pipeline.

**Scope:** Automated collection of publicly available regulatory data from .gov, GSE, and authorized .org targets. No authentication bypass. No aggressive crawling. No proprietary content extraction. Robots.txt respected. Rate limits honored.

**Upstream dependency:** `collect/research-manifest-system` — Only sources on an approved manifest are scraped.

**Downstream consumer:** `phase1/ingestion-pipeline` — Raw scraped output is the input.

---

## 2. Tool Selection — Analysis & Recommendation

### 2.1 Evaluation Criteria

| Criterion | Weight | Why It Matters for RORI |
|-----------|--------|------------------------|
| LLM-Ready Output | High | RORI's ingestion pipeline processes content for vector embedding and agent retrieval — clean markdown reduces token cost and parsing complexity |
| Bot-Detection Bypass | Medium | .gov sites have minimal protection; GSE guides have moderate; industry .orgs vary |
| JavaScript Rendering | High | Modern .gov sites (CFPB, HUD) use JS-rendered content |
| Cost at RORI Scale | High | ~200–500 regulatory sources, scraped weekly-to-monthly = moderate volume |
| API Simplicity | Medium | Small team, fast iteration — complex SDKs add friction |
| Change Detection Support | Medium | Must detect when source content changes between scrapes |
| Self-Host Option | Low | Managed service preferred at current stage; self-host as fallback |
| Swagger/OpenAPI Ingest | Low | Future requirement — tool should not block this |

### 2.2 Tools Evaluated

**Tier 1 — Managed Scraping APIs (recommended for RORI's current stage)**

| Tool | LLM Output | Bot Bypass | JS Render | Pricing (entry) | Success Rate* | Notes |
|------|-----------|-----------|----------|-----------------|--------------|-------|
| **Firecrawl** | ✅ Native markdown + JSON | ✅ Proxies, CAPTCHA avoidance | ✅ Full headless | $16/mo (500 credits) | 71.2% | Y Combinator-backed, 48K GitHub stars, MCP integration, open-source core |
| **ScrapingAnt** | ❌ HTML only (post-process) | ✅ Rotating proxies, fingerprinting | ✅ Headless Chrome | $19/mo (100K credits) | Varies | Developer recommended, good support, MCP integration, competitive on credit volume |
| **ScrapingBee** | ❌ HTML/JSON only | ✅ Proxies, stealth | ✅ Headless | $49/mo (150K credits) | ~60% | 5x credit multiplier for JS rendering inflates real cost |
| **Bright Data** | ❌ HTML only | ✅ Enterprise-grade | ✅ Full | $499/mo | High | Overkill for RORI's regulatory targets |

*\*Success rates from Scrapeway benchmark (December 2024) — tested against commercial sites with aggressive bot detection. .gov regulatory targets are significantly easier.*

**Tier 2 — Self-Hosted / Open Source (fallback layer)**

| Tool | LLM Output | Bot Bypass | JS Render | Cost | Notes |
|------|-----------|-----------|----------|------|-------|
| **Crawlee + Playwright** | ❌ (add converter) | ✅ Built-in fingerprinting, session management | ✅ Full | Free (infra cost) | Apify-maintained, Apache 2.0, Python + Node, production-grade queue management |
| **Scrapy** | ❌ HTML only | ❌ Manual | ❌ (plugin) | Free | Fastest for static HTML, no JS rendering without middleware |

### 2.3 Recommendation: Hybrid — Firecrawl Primary + Crawlee Fallback

**Primary: Firecrawl**

Firecrawl wins on the criterion that matters most for RORI: **LLM-ready output**. Every other tool returns raw HTML that must be post-processed into a format suitable for chunking, embedding, and agent retrieval. Firecrawl returns clean markdown natively, which:

- Reduces token consumption by ~67% vs raw HTML when fed to LLMs
- Eliminates an entire parsing/cleaning stage from the ingestion pipeline
- Returns structured metadata (title, description, language, source URL) automatically
- Supports crawling entire sites with a single API call (critical for GSE seller/servicer guides that span hundreds of pages)
- Provides a `/map` endpoint that discovers all URLs on a domain before scraping — useful for manifest expansion
- Has an open-source core that can be self-hosted if needed later
- Offers MCP integration for direct use in AI agent workflows

**Fallback: Crawlee + Playwright (self-hosted)**

For sources that Firecrawl struggles with (heavily JS-rendered state agency portals, sites behind Cloudflare with aggressive challenges), Crawlee provides:

- Full Playwright browser automation with built-in bot-detection bypass
- Browser fingerprint rotation out of the box
- Persistent request queues (crashed crawlers resume)
- Session management that ties proxies to browser contexts
- Python and Node.js SDKs
- Zero ongoing API cost (you manage infrastructure)

**Acknowledging the ScrapingAnt Recommendation**

ScrapingAnt was the original tool recommendation and remains a viable option. Its strengths are competitive credit volume (100K at $19/mo vs Firecrawl's 500 at $16/mo), strong customer support, and proven bot-bypass capabilities. If credit volume becomes a concern at scale or if Firecrawl's pricing proves prohibitive for high-frequency scraping of many sources, ScrapingAnt should be reconsidered as the primary API. The architecture below is designed to be **provider-agnostic** — swapping the scraping backend requires changing one adapter, not rewriting the system.

### 2.4 Future: Swagger/OpenAPI File Ingestion

When RORI needs to ingest API specifications (Swagger/OpenAPI files), the scraping infrastructure won't be the right tool — those are structured data files, not web pages. The architecture includes a `swagger-ingestion` extension point in the manifest schema. When activated, the system will:

1. Download the raw `.json` or `.yaml` spec file (simple HTTP GET, no scraping needed)
2. Parse with a standard OpenAPI parser
3. Extract endpoints, schemas, descriptions, and constraints
4. Stage as structured metadata alongside scraped content

This is a Phase 2 enhancement and does not affect the current architecture.

---

## 3. Architecture

### 3.1 System Overview

```
┌─────────────────────────────────────────────────────────────────────┐
│                        RORI Collection Layer                        │
│                                                                     │
│  ┌──────────────┐    ┌──────────────┐    ┌───────────────────────┐  │
│  │   Research    │    │   Scrape     │    │    Scrape Engine      │  │
│  │   Manifest    │───▶│   Scheduler  │───▶│  ┌─────────────────┐ │  │
│  │   (approved   │    │  (cron/queue)│    │  │  Firecrawl API  │ │  │
│  │   sources)    │    │              │    │  │  (primary)      │ │  │
│  └──────────────┘    └──────────────┘    │  └────────┬────────┘ │  │
│                                          │           │          │  │
│                                          │  ┌────────▼────────┐ │  │
│                                          │  │  Crawlee/PW     │ │  │
│                                          │  │  (fallback)     │ │  │
│                                          │  └────────┬────────┘ │  │
│                                          └───────────┼──────────┘  │
│                                                      │             │
│                                          ┌───────────▼──────────┐  │
│                                          │   Output Writer      │  │
│                                          │   (normalize + stage)│  │
│                                          └───────────┬──────────┘  │
│                                                      │             │
│                                          ┌───────────▼──────────┐  │
│                                          │   RAW Staging Area   │  │
│                                          │   /collect/staged/   │  │
│                                          └───────────┬──────────┘  │
│                                                      │             │
└──────────────────────────────────────────────────────┼─────────────┘
                                                       │
                                           ┌───────────▼──────────┐
                                           │  phase1/ingestion    │
                                           │  pipeline (consumer) │
                                           └──────────────────────┘
```

### 3.2 Component Breakdown

**3.2.1 Manifest Reader**
- Reads approved sources from the Research Manifest
- Filters to `status: active` entries only
- Extracts: URL, format hint, scrape frequency, scrape method, content selectors (optional)
- Emits a `ScrapeJob` for each active source

**3.2.2 Scrape Scheduler**
- Accepts `ScrapeJob` queue
- Respects per-source frequency (daily, weekly, monthly)
- Implements backoff on failure (exponential, max 3 retries)
- Deduplicates — won't re-scrape if last scrape is within the frequency window and content hash unchanged
- Concurrency control — max parallel scrapes configurable (default: 5)
- Priority queue — CFPB and Federal Register get higher priority than state-level sources

**3.2.3 Scrape Engine (Provider-Agnostic Adapter)**

```typescript
interface ScrapeAdapter {
  scrape(job: ScrapeJob): Promise<ScrapeResult>;
  crawl(job: CrawlJob): Promise<ScrapeResult[]>;
  mapUrls(domain: string): Promise<string[]>;
  healthCheck(): Promise<boolean>;
}

// Implementations:
class FirecrawlAdapter implements ScrapeAdapter { ... }
class CrawleeAdapter implements ScrapeAdapter { ... }
class ScrapingAntAdapter implements ScrapeAdapter { ... }  // reserve slot
```

The adapter interface ensures any scraping backend can be swapped without changing upstream or downstream code. Each adapter normalizes its output to the common `ScrapeResult` type.

**3.2.4 Output Writer**
- Receives `ScrapeResult` from the engine
- Computes content hash (SHA-256 of body text)
- Compares against last-known hash for this source — if unchanged, logs "no change" and skips staging
- If changed: writes the full output envelope (see Section 5) to the staging area
- Writes one file per scraped page/document in the defined output schema

**3.2.5 RAW Staging Area**
- File-system directory: `/collect/staged/` (or S3-compatible bucket in cloud deploy)
- Organized by domain and date (see Section 5.3)
- Consumed by `phase1/ingestion-pipeline` via polling or event notification
- Retention policy: staged files retained for 90 days after ingestion confirmation

### 3.3 Scrape Flow — Single Source

```
1. Scheduler picks next due ScrapeJob from manifest
2. Check last scrape timestamp — skip if within frequency window
3. Route to primary adapter (Firecrawl)
   a. Call scrape(url) → returns markdown + metadata
   b. On failure (timeout, 4xx, 5xx): retry up to 3x with backoff
   c. On persistent failure: route to fallback adapter (Crawlee)
   d. On fallback failure: log error, increment failure counter, emit alert
4. Output Writer receives ScrapeResult
   a. Compute SHA-256 of content body
   b. Compare against stored hash for this manifest entry
   c. If unchanged → log "no change", update last_checked timestamp, done
   d. If changed → write output envelope to staging area
5. Update manifest entry: last_scraped, last_hash, last_status
6. Write audit log entry
```

### 3.4 Crawl Flow — Multi-Page Source (GSE Guides)

Some sources (Fannie Mae Selling Guide, Freddie Mac Guide) span hundreds of pages. For these, the manifest entry specifies `method: crawl` instead of `method: scrape`.

```
1. Scheduler picks CrawlJob
2. Call adapter.mapUrls(domain) → discover all page URLs
3. Filter URLs against manifest inclusion/exclusion patterns
4. For each URL in filtered set:
   a. Call adapter.scrape(url)
   b. Run through Output Writer (same as single-source flow)
5. Write crawl summary: total pages found, pages scraped, pages changed, errors
6. Update manifest entry with crawl statistics
```

---

## 4. Frontend — Approach Decision

### 4.1 Options Evaluated

**Option A: GPT-Generated Manifest + Slim React Monitor**

The manifest (list of sources to scrape with their configuration) is generated using a GPT conversation (in ChatGPT, Claude, or similar). The output is a structured JSON/YAML file. A slim React application ingests this manifest and provides:

- Dashboard showing scrape status per source (last run, next run, success/fail)
- Error log viewer with filtering and search
- Manual trigger button to force-scrape a specific source
- Manifest upload/versioning (drag-and-drop JSON/YAML)
- Change detection summary (which sources changed since last scrape)

**Option B: Full React Interface with Integrated GPT API**

A full React application that includes a built-in prompt interface calling a GPT API to generate/modify the manifest interactively. The user describes what they want to scrape in natural language, the system generates manifest entries, and the same interface monitors execution.

### 4.2 Recommendation: Option A — GPT Manifest + Slim React

**Why Option A wins for RORI right now:**

1. **Separation of concerns** — Manifest generation is a one-time (or infrequent) task. Mixing it with runtime monitoring adds complexity without proportional value. You're already using AI tools (Claude, GPTs) daily — generating a manifest in conversation is natural and requires zero custom UI.

2. **Faster to build** — The React monitor is ~5 screens. Option B adds an entire prompt engineering interface, API key management, streaming response handling, and error recovery for the GPT integration. That's 3–4x the frontend scope.

3. **Manifest versioning is simpler** — A JSON/YAML file in git is trivially versioned, diffed, and reviewed. An in-app manifest editor adds state management complexity.

4. **The GPT API can be added later** — Option A doesn't preclude Option B. If generating manifests via conversation becomes painful, the GPT API integration can be added as a feature to the existing React app. The reverse is harder — stripping out a tightly coupled GPT interface is more work than adding one.

5. **Cost control** — No GPT API calls during runtime. The manifest is generated offline, reviewed by a human, and uploaded. The scraping system burns zero LLM tokens during operation.

### 4.3 React Monitor — Screen Inventory

| Screen | Purpose |
|--------|---------|
| **Dashboard** | Overview of all manifest sources with status badges (✅ OK, ⚠️ Changed, ❌ Failed, ⏳ Pending). Last scrape time, next scheduled scrape, content hash. |
| **Source Detail** | Per-source view: scrape history (timestamped list of runs), content diff viewer (what changed between versions), raw output preview, error details. |
| **Error Log** | Filterable log of all scrape failures: source, timestamp, HTTP status, error message, retry count. Sortable by severity and recency. |
| **Manifest Manager** | Upload/download manifest files. Version history. Diff between manifest versions. Validate manifest structure before activation. |
| **Run Control** | Manual scrape triggers. Bulk operations (scrape all, scrape by category). Schedule override. Pause/resume scheduler. |

### 4.4 Manifest Schema (GPT-Generated Input)

The manifest is a JSON file that the GPT generates based on the FTHB Regulatory Seed Manifest (Appendix A of the macro plan). Here is the schema:

```jsonc
{
  "$schema": "https://rori.dev/schemas/scrape-manifest-v1.json",
  "version": "1.0.0",
  "created": "2026-02-13T00:00:00Z",
  "updated": "2026-02-13T00:00:00Z",
  "vertical": "fthb",
  "sources": [
    {
      "id": "cfpb-reg-x",
      "name": "CFPB Regulation X (RESPA)",
      "description": "Real Estate Settlement Procedures Act implementing regulation",
      "url": "https://www.consumerfinance.gov/rules-policy/regulations/1024/",
      "domain": "consumerfinance.gov",
      "regulatory_domain": "RESPA",
      "citation": "12 C.F.R. Part 1024",
      "jurisdiction": "federal",
      "source_type": "regulation",       // regulation | guidance | guide | enforcement | educational
      "content_type": "html",            // html | pdf | xml | json | yaml
      "method": "crawl",                 // scrape (single page) | crawl (multi-page)
      "frequency": "weekly",             // daily | weekly | biweekly | monthly
      "priority": "high",               // high | medium | low
      "status": "active",               // active | paused | retired | proposed
      "scrape_config": {
        "include_patterns": ["/1024/*"],
        "exclude_patterns": ["/1024/*/interp*"],
        "max_depth": 3,
        "wait_for_selector": null,       // CSS selector to wait for before scraping (JS-heavy pages)
        "custom_headers": {}
      },
      "metadata": {
        "agency": "CFPB",
        "last_known_update": "2024-10-01",
        "update_source": "Federal Register",
        "corroboration_status": "verified",
        "notes": "Includes appendices and supplements"
      },
      "swagger": null                    // Future: path to OpenAPI spec file for API-based sources
    }
    // ... more sources
  ]
}
```

### 4.5 GPT Prompt Template for Manifest Generation

This is the prompt template used to generate the initial manifest from the seed data:

```markdown
You are generating a RORI scrape manifest for the First-Time Homebuyer (FTHB) regulatory vertical.

Using the FTHB Regulatory Seed Manifest below, generate a JSON manifest file following
the schema at [schema URL]. For each source:

1. Assign a unique kebab-case ID
2. Map to the correct regulatory_domain
3. Determine the appropriate scrape method (scrape for single pages, crawl for multi-page guides)
4. Set frequency based on how often the source typically updates
5. Set priority based on importance to FTHB compliance
6. Include any known include/exclude URL patterns

Seed data:
[paste Appendix A from macro plan v1.1]

Output: Valid JSON matching the manifest schema. No commentary, just the JSON.
```

---

## 5. RAW Output Structure

### 5.1 Design Principles

Every scraped document lands in the staging area as a self-contained envelope. The envelope contains everything the ingestion pipeline needs to process the document without referring back to the manifest or the scraping system. This is the contract between the collection layer and the ingestion layer.

**Principles:**
- **Self-contained** — Each envelope has all metadata needed for ingestion
- **Immutable** — Once written, an envelope is never modified (new versions create new envelopes)
- **Content-addressable** — The content hash serves as a deduplication key
- **Traceable** — Full provenance from manifest entry to scrape execution to output

### 5.2 Envelope Schema

Each scraped page produces one JSON envelope file:

```jsonc
{
  // === Identity ===
  "envelope_id": "uuid-v4",                          // Unique ID for this envelope
  "envelope_version": "1.0",                          // Schema version of this envelope format

  // === Source Provenance ===
  "source": {
    "manifest_id": "cfpb-reg-x",                     // ID from the scrape manifest
    "manifest_version": "1.0.0",                     // Version of the manifest that triggered this scrape
    "url": "https://www.consumerfinance.gov/rules-policy/regulations/1024/5/",
    "domain": "consumerfinance.gov",
    "canonical_url": null,                            // If the page declares a canonical URL, capture it
    "regulatory_domain": "RESPA",
    "citation": "12 C.F.R. § 1024.5",
    "jurisdiction": "federal",
    "source_type": "regulation",
    "agency": "CFPB"
  },

  // === Scrape Execution ===
  "scrape": {
    "timestamp": "2026-02-13T14:30:00Z",             // When this scrape executed
    "engine": "firecrawl",                            // Which adapter produced this result
    "engine_version": "2.1.0",                        // Version of the scraping tool
    "method": "scrape",                               // scrape | crawl
    "http_status": 200,
    "response_time_ms": 2340,
    "retry_count": 0,
    "credits_consumed": 1,                            // API credits used
    "parent_crawl_id": null                           // If part of a crawl, the crawl job ID
  },

  // === Content ===
  "content": {
    "format": "markdown",                             // markdown | html | pdf_text | raw
    "body": "# Regulation X — Section 1024.5\n\n...", // The actual scraped content
    "body_html": "<html>...</html>",                  // Original HTML (always preserved)
    "body_length_chars": 14523,
    "body_length_tokens_approx": 3800,                // Rough token estimate (chars / 4)
    "language": "en",
    "encoding": "utf-8"
  },

  // === Content Integrity ===
  "integrity": {
    "content_hash": "sha256:a1b2c3d4...",             // SHA-256 of content.body
    "html_hash": "sha256:e5f6g7h8...",                // SHA-256 of content.body_html
    "previous_content_hash": "sha256:x9y0z1...",      // Hash from last scrape (null if first)
    "content_changed": true,                          // Did content change since last scrape?
    "change_type": "modified"                          // new | modified | unchanged | deleted
  },

  // === Page Metadata (extracted from page) ===
  "page_metadata": {
    "title": "§ 1024.5 Coverage of RESPA",
    "description": "Coverage requirements under the Real Estate Settlement Procedures Act",
    "keywords": ["RESPA", "settlement", "coverage"],
    "author": null,
    "published_date": null,
    "modified_date": "2024-09-15",
    "og_title": null,
    "og_description": null,
    "og_image": null,
    "robots": "index, follow",
    "links_outbound": [                               // External links found on page
      "https://www.ecfr.gov/current/title-12/chapter-X/part-1024"
    ],
    "links_internal": [                               // Internal links found on page
      "/rules-policy/regulations/1024/4/",
      "/rules-policy/regulations/1024/6/"
    ]
  },

  // === Processing Hints (for ingestion pipeline) ===
  "processing": {
    "suggested_chunk_strategy": "section_aware",      // section_aware | paragraph | fixed_size
    "has_tables": true,
    "has_lists": true,
    "has_code_blocks": false,
    "has_embedded_pdfs": false,
    "cross_references": [                             // Regulatory cross-references detected in content
      "12 C.F.R. § 1024.2",
      "Regulation Z",
      "42 U.S.C. § 3601"
    ],
    "estimated_complexity": "medium"                   // simple | medium | complex
  },

  // === Audit ===
  "audit": {
    "scrape_run_id": "uuid-v4",                       // ID of the scrape run (groups multiple pages in a crawl)
    "scheduler_job_id": "uuid-v4",                    // ID of the scheduler job that triggered this
    "operator": "system",                             // system | manual (if manually triggered)
    "environment": "production"                       // production | staging | development
  }
}
```

### 5.3 Staging Directory Structure

```
/collect/staged/
├── _index.jsonl                          # Append-only log of all staged envelopes
├── _errors.jsonl                         # Append-only log of all scrape errors
│
├── consumerfinance.gov/
│   ├── 2026-02-13/
│   │   ├── cfpb-reg-x__1024-5__a1b2c3d4.json      # {manifest_id}__{path-slug}__{hash-prefix}.json
│   │   ├── cfpb-reg-x__1024-6__e5f6g7h8.json
│   │   └── ...
│   └── 2026-02-20/
│       └── ...
│
├── hud.gov/
│   ├── 2026-02-13/
│   │   └── hud-counseling-214__part-214__b3c4d5e6.json
│   └── ...
│
├── singlefamily.fanniemae.com/
│   ├── 2026-02-13/
│   │   ├── fnma-selling-guide__b1-1-01__c4d5e6f7.json
│   │   ├── fnma-selling-guide__b1-1-02__d5e6f7g8.json
│   │   └── ...    (hundreds of pages from crawl)
│   └── ...
│
├── guide.freddiemac.com/
│   └── ...
│
└── ecfr.gov/
    └── ...
```

**Naming convention:** `{manifest_id}__{url-path-slug}__{content-hash-prefix-8}.json`

**Index file (`_index.jsonl`):** One JSON line per staged envelope. Enables the ingestion pipeline to poll for new content without scanning the entire directory tree.

```jsonc
{"envelope_id":"uuid","manifest_id":"cfpb-reg-x","url":"https://...","staged_at":"2026-02-13T14:30:00Z","path":"consumerfinance.gov/2026-02-13/cfpb-reg-x__1024-5__a1b2c3d4.json","content_changed":true}
```

**Error file (`_errors.jsonl`):**

```jsonc
{"timestamp":"2026-02-13T14:32:00Z","manifest_id":"hud-9902","url":"https://...","error":"HTTP 503","retry_count":3,"engine":"firecrawl","resolved":false}
```

### 5.4 Content Hash & Change Detection

```
1. On every scrape, compute SHA-256 of the markdown body (content.body)
2. Look up the last known hash for this manifest_id + url combination
3. If hashes match → content_changed: false, skip staging
4. If hashes differ → content_changed: true, write new envelope, update stored hash
5. If no previous hash → change_type: "new", write envelope
```

The hash comparison is the primary mechanism for avoiding redundant processing. The ingestion pipeline only receives envelopes where `content_changed: true` or `change_type: "new"`.

---

## 6. Scheduling & Rate Limiting

### 6.1 Default Frequencies

| Source Category | Default Frequency | Rationale |
|----------------|-------------------|-----------|
| Federal Register | Daily | New rules and notices published daily |
| CFPB guidance pages | Weekly | Updates are irregular but impactful |
| eCFR regulatory text | Weekly | CFR is updated continuously as rules finalize |
| GSE seller/servicer guides | Biweekly | Fannie/Freddie update bulletins periodically |
| HUD program pages | Weekly | Program guidance updates |
| State agency sites | Monthly | State regulations change slowly |
| Industry .org sites | Monthly | Infrequent updates |

### 6.2 Politeness Controls

- **robots.txt:** Always respected. If a source disallows scraping, it cannot be added to the manifest.
- **Rate limiting:** Maximum 1 request per 2 seconds to any single domain (configurable per domain)
- **Concurrent domain limit:** Maximum 3 simultaneous requests to the same domain
- **Global concurrency:** Maximum 10 parallel scrape operations across all domains
- **User-Agent:** `RORI-Collector/1.0 (+https://rori.dev/collector; research-purposes)`
- **Time-of-day preference:** Schedule scrapes during off-peak hours (2 AM–6 AM ET) for .gov sites

---

## 7. Error Handling & Resilience

### 7.1 Retry Strategy

| Error Type | Retry? | Max Retries | Backoff | Escalation |
|-----------|--------|-------------|---------|------------|
| HTTP 429 (Rate Limited) | Yes | 5 | Exponential (30s, 60s, 120s, 300s, 600s) | Reduce frequency for source |
| HTTP 503 (Service Unavailable) | Yes | 3 | Exponential (10s, 30s, 60s) | Log, retry next scheduled run |
| HTTP 403 (Forbidden) | No | 0 | — | Alert: source may have blocked us, review robots.txt |
| HTTP 404 (Not Found) | No | 0 | — | Alert: source URL may have moved, flag for manifest review |
| Timeout (>30s) | Yes | 2 | Linear (15s) | Route to fallback adapter |
| CAPTCHA detected | No | 0 | — | Route to fallback adapter (Crawlee with stealth) |
| Parse error | No | 0 | — | Log raw HTML, flag for manual review |

### 7.2 Circuit Breaker

If a source fails 5 consecutive times across scheduled runs:
1. Set source status to `paused` in manifest
2. Emit alert to operator
3. Require manual review and re-activation
4. Log all failures with full HTTP response for diagnosis

### 7.3 Alerting

| Event | Severity | Channel |
|-------|----------|---------|
| Source blocked (403) | High | Dashboard + email |
| Source moved (404) | High | Dashboard + email |
| 5 consecutive failures | High | Dashboard + email |
| Content changed (normal) | Info | Dashboard only |
| No changes detected in 30 days | Warning | Dashboard |
| Credit usage > 80% of plan limit | Warning | Dashboard + email |

---

## 8. Audit Logging

Every scrape operation produces an audit record. Audit logs are append-only and never modified.

```jsonc
{
  "run_id": "uuid-v4",
  "timestamp": "2026-02-13T14:30:00Z",
  "manifest_id": "cfpb-reg-x",
  "url": "https://...",
  "engine": "firecrawl",
  "http_status": 200,
  "content_hash": "sha256:...",
  "content_changed": true,
  "response_time_ms": 2340,
  "credits_consumed": 1,
  "retry_count": 0,
  "error": null,
  "staged_path": "consumerfinance.gov/2026-02-13/cfpb-reg-x__1024-5__a1b2c3d4.json"
}
```

Audit logs support:
- Compliance reporting ("prove that we scraped from the authoritative source on date X")
- Cost tracking (credits consumed over time)
- Performance monitoring (response times, failure rates)
- Change frequency analysis (how often does each source actually change?)

---

## 9. Technology Stack

| Component | Technology | Rationale |
|-----------|-----------|-----------|
| Runtime | Node.js (TypeScript) | Firecrawl SDK is JS-first; Crawlee has excellent Node support |
| Scheduler | node-cron + BullMQ (Redis-backed) | Persistent job queue with retry, backoff, priority, and dead letter queue |
| Primary scraper | Firecrawl API | LLM-ready output, managed infrastructure |
| Fallback scraper | Crawlee + Playwright | Self-hosted, full browser automation |
| Storage (staging) | Local filesystem (dev) / S3 (prod) | Simple, cheap, scalable |
| Storage (audit/index) | SQLite (dev) / PostgreSQL (prod) | Structured queries on audit data |
| Frontend | React + Vite + Tailwind | Slim monitoring dashboard |
| State management | Zustand | Lightweight, minimal boilerplate |
| API layer | Express.js | REST endpoints for frontend and manual triggers |

---

## 10. Deliverables & Acceptance Criteria

| # | Deliverable | Acceptance Criteria |
|---|------------|-------------------|
| 1 | Scrape adapter interface + Firecrawl implementation | Can scrape a single .gov page and return markdown with metadata |
| 2 | Crawlee fallback adapter | Can scrape a page that Firecrawl fails on |
| 3 | Manifest reader | Parses manifest JSON, emits ScrapeJob queue |
| 4 | Scheduler | Respects frequencies, retries, backoff, circuit breaker |
| 5 | Output Writer + staging directory | Produces valid envelope JSON per schema; change detection works |
| 6 | Audit logging | Every operation logged; queryable by source, date, status |
| 7 | React dashboard (5 screens) | Displays source status, error log, manifest manager, manual triggers |
| 8 | GPT prompt template for manifest generation | Produces valid manifest from seed data in one prompt |
| 9 | FTHB seed manifest (JSON) | All sources from Appendix A converted to manifest schema |
| 10 | Integration test | End-to-end: manifest → schedule → scrape → stage → verify envelope |

---

## 11. Open Questions

| # | Question | Impact | Resolution Path |
|---|----------|--------|----------------|
| 1 | Should the staging area use S3 from day one or start with local filesystem? | Deployment complexity vs. cloud readiness | Defer to project scaffold decision |
| 2 | Should the React monitor be a standalone app or embedded in a larger RORI admin UI? | Architecture decision for Phase 2 | Start standalone, merge later if needed |
| 3 | What is the budget ceiling for Firecrawl credits per month? | Determines scrape frequency limits | Frank to define based on plan selection |
| 4 | Should PDF documents be converted to markdown at scrape time or at ingestion time? | Affects envelope content format | Recommend scrape time (Firecrawl handles it) |
| 5 | How should the system handle sources that require login (future)? | Out of scope for v1 but architecture should not block it | Reserve `auth_config` field in manifest schema |

---

## 12. Risk Register

| Risk | Likelihood | Impact | Mitigation |
|------|-----------|--------|-----------|
| Firecrawl pricing increases significantly | Medium | High | Provider-agnostic adapter means we can switch to ScrapingAnt or self-host Crawlee |
| .gov sites add aggressive bot detection | Low | Medium | Most .gov sites are public-data-friendly; Crawlee fallback handles edge cases |
| GSE guides restructure URLs | Medium | Medium | `/map` endpoint discovers URLs dynamically; manifest patterns are configurable |
| Credit burn exceeds budget | Medium | Medium | Change detection prevents re-scraping unchanged content; frequency is tunable |
| Scraping API rate limits throttle throughput | Low | Low | Off-peak scheduling + distributed scheduling across time windows |

---

*v1.0 — 2026-02-13 — Frank & Candi*
*Branch: collect/web-scraping-infra*
*Parent: RORI Macro Development Plan v1.1*
