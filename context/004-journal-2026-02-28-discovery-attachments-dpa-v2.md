---
type: journal
created: 2026-02-28
source: cursor
description: Discovery attachments delivered, infra restarts verified, DPA Discovery V2 plan/refinement
tags: [raris, journal, "#source/session"]
---

# Session Journal — 2026-02-28 — Discovery Attachments + DPA V2 Planning

## Executive Summary

Implemented the requested discovery attachment feature (constitution + instruction uploads, placeholder no-op), upgraded backend generation to support multipart and file text extraction, threaded guidance content into discovery prompts, restarted Docker stack and verified endpoints, and produced/refined a DPA Discovery V2 plan with deterministic seeding expanded to active multi-file seeding.

## Work Delivered

### 1. Discovery attachments in UI

**Delivered:**
- Added 3 discovery controls in `DomainInputPanel`:
  - Upload Constitution
  - Upload Instruction / Guidance
  - Placeholder (no-op)
- Added selected file display + clear actions
- Switched manifest generation request to multipart `FormData`

**Files:**
- `frontend/src/components/DomainInputPanel.tsx`
- `frontend/src/App.css`
- `frontend/src/components/DomainInputPanel.test.tsx`

### 2. Multipart backend + file extraction

**Delivered:**
- `/api/manifests/generate` now parses JSON and multipart/form requests
- Upload validation for `.txt`, `.md`, `.pdf`, `.docx`
- Extractors implemented:
  - text/markdown decode
  - PDF via `pdfplumber`
  - DOCX via `python-docx`
- Guidance text passed into agent run path

**Files:**
- `backend/app/routers/manifests.py`

### 3. Guidance-aware discovery prompting

**Delivered:**
- Discovery run accepts optional `constitution_text` and `instruction_text`
- Guidance context injected into mapper/hunter/relationship/coverage prompts

**Files:**
- `backend/app/agent/discovery.py`
- `backend/app/agent/prompts.py`

### 4. Dependencies and test updates

**Dependencies added:**
- `python-docx`
- `python-multipart`
- `aiosqlite` (for test DB compatibility)

**Files:**
- `backend/pyproject.toml`
- `backend/uv.lock`
- `backend/tests/test_api_integration.py`

**Frontend test added:**
- `frontend/src/components/DomainInputPanel.test.tsx`

## Runtime / Environment Outcomes

### Stack restart verification

Performed full restart (`docker compose down`, `docker compose up -d --build`) and confirmed:
- Backend healthy on `http://localhost:8000/health`
- Frontend responsive on `http://localhost:80` (HTTP 200)
- DB and Redis healthy

### Test caveats observed

1. **Rate limiting (`429`) during backend integration tests**  
   Needed `RATE_LIMIT_RPM=0` for targeted high-frequency test paths.

2. **Vitest mapped-drive path issue**  
   Running from `X:\...` could fail setup resolution in this Windows mapping scenario; running from `C:\DATA\RARIS\frontend` succeeded.

## Planning / Strategy Work

### DPA prompt and export evaluation completed

Reviewed:
- `X:\Keyz\DPA\DPA_Prompt_v1.md`
- `X:\Keyz\DPA\DPA One- Search Results 2026-02-28 05_24_14.pdf`

Assessment:
- Prompt quality is strong for scope and extraction intent.
- Current engine remains body/source-centric; not yet full program-registry depth.

### DPA Discovery V2 plan produced and refined

Plan file:
- `C:\Users\frank\.cursor\plans\dpa_discovery_v2_9331e066.plan.md`

Refinement added per request:
- Deterministic seeding item expanded
- Third button repurposed from placeholder to active `Seeding`
- Multi-file seed upload support
- Seeds may include traversal anchors and/or direct program records

## Decisions Made

| Decision | Reason |
|---|---|
| Keep `/api/manifests/generate` backward compatible with JSON while adding multipart support | Preserve existing client/test behavior while enabling attachments |
| Inject guidance context into all major discovery stages | Ensure uploaded constitution/instruction materially influence output |
| Add strict extension gate for uploads | Prevent unsupported/unsafe file parsing paths |
| Use targeted test runs for new behavior where global suite is noisy under limiter | Fast validation of changed surfaces |

## Carried Forward

1. Replace placeholder button with active `Seeding` and multi-file flow (from refined V2 plan).
2. Add first-class program model and program enumerator stage for municipal depth.
3. Add depth controls (`k_depth`, `geo_scope`) to make runs tunable.
4. Define seed schema v1 and parser acceptance contract.

