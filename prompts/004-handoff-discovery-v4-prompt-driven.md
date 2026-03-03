---
type: handoff
created: 2026-03-02T01:30:00
sessionId: S20260302_0100
source: cursor-agent
target: claude-code
description: Rewrite discovery engine to be prompt-driven — instruction prompt drives L0, data drives L1-L3 recursion
source_prompt: prompts/DPA_Prompt_v4.md
---

# Handoff: Discovery V4 — Prompt-Driven Architecture

## Objective

Rewrite the hierarchical discovery engine so that:
1. The **domain description field** is just a manifest label/name — not a discovery driver
2. The **uploaded instruction prompt** (e.g., DPA_Prompt_v5.md) drives L0 discovery directly — no "guidance block" wrapper
3. **L1-L3 recursion is self-sustaining** — driven by what L0 actually discovered, not by the original prompt
4. **Low-confidence items are preserved** — persisted with confidence scores for later human review
5. A **base instruction template** is created for future verticals
6. The **DPA instruction prompt is rewritten** (v5) to match the template, derived from DPA_Prompt_v4.md

## Mandatory Reads Before Coding

Read these files in order. Do not skip any.

1. `CLAUDE.md` — Agent bootstrap and project context
2. `docs/DFW-CONSTITUTION.md` — Universal rules (P1-P9)
3. `docs/DFW-OPERATING-MANUAL.md` — Methodology, tagging, session lifecycle
4. `.dfw/personal-config.md` — Environment paths, tool mappings
5. `context/_ACTIVE_CONTEXT.md` — Current project state
6. `plans/_TODO.md` — Active and queued work
7. `research/003-analysis-dpa-program-taxonomy.md` — Three-axis taxonomy (funding entity, benefit structure, eligibility persona)
8. `prompts/DPA_Prompt_v4.md` — Current DPA instruction prompt (the source material for v5 rewrite)
9. `.cursor/rules/gemini-model-rules.mdc` — Gemini 3.1 SDK patterns including web grounding (Section 3)
10. `.cursor/rules/anthropic-model-rules.mdc` — Anthropic SDK patterns including web search (Section 3)
11. `.cursor/rules/openai-model-rules.mdc` — OpenAI SDK patterns including web search (Section 3)

## Current State — What Exists

### Docker Stack (all 4 containers healthy)
- `db` — PostgreSQL 16 + pgvector on port 5432
- `redis` — Redis 7 on port 6379
- `backend` — FastAPI on port 8000
- `frontend` — React/Vite/nginx on port 80

### Discovery Engines (two exist, both have problems)
- `backend/app/agent/discovery.py` — V2 flat pipeline (works but caps at ~180 programs, no web grounding)
- `backend/app/agent/graph_discovery.py` — V3 hierarchical (has web grounding but generic prompts produce 15 programs with 0 sources)

### LLM Providers (all 3 have grounded search)
- `backend/app/llm/gemini_provider.py` — `complete_grounded()` via `google_search` tool, `_call_with_resilience()` retry/fallback
- `backend/app/llm/anthropic_provider.py` — `complete_grounded()` via `web_search_20250305` tool
- `backend/app/llm/openai_provider.py` — `complete_grounded()` via Responses API `web_search`

### Frontend Form Fields
- `domain_description` — text input (currently drives discovery; should become manifest label only)
- `llm_provider` — dropdown (gemini/openai/anthropic)
- `k_depth` — 1-4 slider
- `geo_scope` — national/state/municipal
- `discovery_mode` — flat/hierarchical dropdown
- `constitution_file` — optional file upload
- `instruction_file` — file upload (THIS IS THE KEY INPUT — the instruction prompt)
- `seeding_files` — multi-file upload (seed CSVs/JSONs)

### API Schema
- `POST /api/manifests/generate` — multipart form
- `GenerateManifestRequest` in `backend/app/schemas/manifest.py`
- Router in `backend/app/routers/manifests.py` — `_run_agent()` branches on `discovery_mode`

### Tests
- 237 backend tests passing (across 23 test files)
- 16 frontend tests passing
- Run with: `docker exec raris-backend-1 python -m pytest tests/ -x -q`

### Config
- `.env` has `LLM_PROVIDER=gemini`, `GEMINI_MODEL=gemini-3.1-pro-preview`
- Fallback chain: `gemini-3.1-pro-preview,gemini-3.1-pro-preview:no-think,gemini-3.1-flash-preview`
- Use UV for Python package management (mandatory per project rules)

## What's Wrong — Why This Rewrite Is Needed

### Problem: Prompt-Algorithm Mismatch
The V3 `DiscoveryGraph` engine uses **generic prompts** (`GROUNDED_LANDSCAPE_MAPPER_PROMPT`, `GROUNDED_SOURCE_HUNTER_PROMPT`, etc.) that say "find regulatory bodies" and "find source documents." These are domain-agnostic and produce thin results.

The DPA_Prompt_v4.md is a 359-line domain-specific discovery methodology with coverage scopes, lexicons, search strategies, and quality gates. But the engine buries it in a `guidance_block` wrapper (truncated to 12,000 chars) and passes it as passive context — the generic prompts override it.

### Evidence from the last run (no seed file, hierarchical mode):
- L0 landscape: 20 bodies found (only federal + 10 state HFAs)
- L0 source hunter: **0 sources** (both batches timed out — generic "find statutes and regulations" prompt doesn't match DPA domain)
- L1 municipal: **FAILED** (timeout)
- L1 nonprofit: **FAILED** (empty JSON response)
- L1 employer: 4 entities, 5 programs
- L1 tribal: 5 entities, 5 programs
- L3 gap fill: 5 programs
- **Final: 20 bodies, 0 sources, 15 programs** (vs V2 flat getting 183 programs)

### Root Cause
The instruction prompt (DPA_Prompt_v4) should BE the L0 discovery driver, not a guidance appendix. The engine's generic prompts are fighting the domain-specific prompt.

## Architecture — What To Build

### Core Principle
**Instruction prompt drives L0. Data drives L1-L3.**

### New Flow

```
User uploads:
  - manifest_name (text) — just a label, e.g. "DPA National Scan March 2026"
  - instruction_file (markdown) — THE discovery driver (e.g., DPA_Prompt_v5.md)
  - seeding_files (optional) — seed CSVs/JSONs for matching
  - llm_provider, k_depth, geo_scope, target_segments — run controls

Engine:
  L0 — Comprehensive Initial Discovery
    - System prompt: thin orchestration wrapper
    - User prompt: THE FULL instruction file content (not truncated, not wrapped)
    - Uses complete_grounded() for web search
    - Output: entities, sources, programs — ALL confidence levels preserved
    - Persist everything to DB immediately

  L1 — Data-Driven Expansion
    - Input: L0 output (entities, sources, programs)
    - For each L0 entity: "Given this entity [name, URL, type], find all
      child programs, sub-entities, application portals, and source documents"
    - Inject topic-matched seeds where entity type matches
    - Uses complete_grounded() for web search
    - Persist incrementally

  L2 — Verification and Evidence
    - Input: L0+L1 output
    - For each program with confidence < threshold: verify via web search
    - For each source URL: lightweight validation (does it exist?)
    - Upgrade/downgrade confidence based on evidence
    - Persist updates

  L3 — Gap Analysis and Fill
    - Input: L0+L1+L2 output + seed file
    - Compare discovered programs against seeds → find unmatched
    - Compare discovered entity types against instruction prompt's coverage scope → find gaps
    - Targeted web search for gaps
    - Hard cap — no further recursion
```

### Key Design Decisions

1. **No more `guidance_block`** — the instruction prompt goes directly into the L0 user message, untruncated. The engine adds only a thin JSON output schema wrapper.

2. **No more generic prompts for L0** — delete `GROUNDED_LANDSCAPE_MAPPER_PROMPT` and `GROUNDED_SOURCE_HUNTER_PROMPT`. L0 uses the instruction prompt directly. The instruction prompt already contains the discovery methodology.

3. **L1-L3 prompts are generated from data** — the engine constructs L1 prompts from L0 output: "Entity: CalHFA. URL: calhfa.ca.gov. Type: state_hfa. Found programs: [MyHome, ZIP]. Task: find all additional programs, sub-entities, application portals, and source documents for this entity."

4. **Low-confidence items preserved** — everything gets persisted with its confidence score. No silent drops. `needs_human_review: true` for anything below 0.5. `verification_state: candidate_only` for items found via third-party indexes.

5. **`domain_description` becomes `manifest_name`** — rename in schema, router, frontend. It's just a label.

6. **Timeout increase** — the current 120s timeout on grounded calls is too aggressive. Gemini grounded search can take 60-90s per call. Increase to 300s for L0, 180s for L1-L3.

## Deliverable 1: Base Instruction Template

Create `prompts/005-doc-base-instruction-template.md` — the contract between instruction prompts and the engine.

Required sections that every instruction prompt MUST have:

```markdown
# [Domain] Discovery Instruction Prompt

## 1. Domain Definition
What is being discovered? What types of entities/programs/sources exist?

## 2. Coverage Scope
Who administers these programs? What entity types to search?
(This drives L0 breadth)

## 3. Taxonomy / Classification
How to classify discovered items. Program types, benefit structures, etc.
(This drives dedup and coverage assessment)

## 4. Search Vocabulary / Lexicon
Domain-specific terms, synonyms, and search keywords.
(This improves web search recall)

## 5. Evidence Requirements
What constitutes a valid discovery? Minimum fields, confidence criteria.
(This drives the verification gate)

## 6. Quality Gates
What coverage targets must be met? What gaps are unacceptable?
(This drives L3 gap analysis)

## 7. Output Schema
What fields the engine expects in the JSON response.
(This is the contract — engine parses this)
```

Sections the instruction prompt should NOT contain (engine handles these):
- Execution phases (L0/L1/L2/L3 — that's engine logic)
- Search strategies (grounded search — that's engine logic)
- Seed reconciliation (that's engine code)
- PDF traversal / portal fingerprinting (that's L1-L2 engine logic)

## Deliverable 2: DPA Instruction Prompt v5

Create `prompts/DPA_Prompt_v5.md` — rewrite of v4 following the base template.

Source material: `prompts/DPA_Prompt_v4.md` (359 lines)

Decomposition guide:

| DPA_Prompt_v4 Section | → Where in v5 |
|---|---|
| Section 1 (System Persona) | → Section 1 (Domain Definition) — keep the persona framing |
| Section 2 (Coverage Scope A-G) | → Section 2 (Coverage Scope) — keep ALL 7 categories verbatim |
| Section 3 (Canonical Program Types) | → Section 3 (Taxonomy) — keep all 10 types |
| Section 4 (Mandatory Lexicon) | → Section 4 (Search Vocabulary) — keep all terms |
| Section 5 Phase 0 (Seed Reconciliation) | → DELETE — engine handles seed matching in code |
| Section 5 Phase 1 (Infrastructure Mapping) | → DELETE — engine handles this as L1 recursion |
| Section 5 Phase 2 (Nested Content/PDF) | → DELETE — engine handles this as L1-L2 |
| Section 5 Phase 3 (Sector Expansion) | → DELETE — engine handles this as L1 + L3 gap fill |
| Section 5 Phase 4 (Evidence Collection) | → Section 5 (Evidence Requirements) — keep the evidence criteria, delete the execution steps |
| Section 6 (Manifest Output) | → Section 7 (Output Schema) — align field names to engine's Program/Source/RegulatoryBody models |
| Section 7 (Quality Gates) | → Section 6 (Quality Gates) — keep the gate criteria |
| Section 8 (Do-Not-Do Rules) | → Append to Section 5 as behavioral guardrails |
| Appendix (Query Templates) | → Section 4 (Search Vocabulary) — merge into the lexicon section |

Target: ~120-150 lines (vs 359 in v4). Dense with domain knowledge, zero execution logic.

## Deliverable 3: Rewrite `graph_discovery.py`

Rewrite `backend/app/agent/graph_discovery.py` to implement the new architecture.

Key changes:
- L0 uses the instruction prompt directly (full text, not truncated)
- L1-L3 prompts are generated from L0 output data
- No more `_build_guidance_block()` — delete it
- No more `GROUNDED_LANDSCAPE_MAPPER_PROMPT` / `GROUNDED_SOURCE_HUNTER_PROMPT` — delete from `prompts.py`
- Keep `L1_ENTITY_EXPANSION_PROMPT` and `L3_GAP_FILL_PROMPT` but rewrite to be data-driven
- Increase timeouts (300s L0, 180s L1-L3)
- Persist ALL items including low-confidence (no silent drops)
- Keep existing SSE event structure for frontend compatibility

## Deliverable 4: Schema and Router Updates

- Rename `domain_description` → `manifest_name` in:
  - `backend/app/schemas/manifest.py` (GenerateManifestRequest)
  - `backend/app/routers/manifests.py` (form parsing, _run_agent params)
  - `frontend/src/components/DomainInputPanel.tsx` (form field, FormData append)
  - `backend/app/models/manifest.py` (Manifest.domain field — check if this needs migration)
- Make `instruction_file` effectively required for hierarchical mode (warn if missing)
- Keep `discovery_mode` — `flat` still uses old `discovery.py`, `hierarchical` uses new `graph_discovery.py`

## Deliverable 5: Update Context Files

After build:
- Update `context/_ACTIVE_CONTEXT.md` with V4 status
- Update `plans/_TODO.md` — mark V3 items as superseded, add V4 validation items
- Write journal entry to `X:\DFW\Vault\journal\`

## Build Sequence (suggested commit order)

1. Base instruction template (`prompts/005-doc-base-instruction-template.md`)
2. DPA_Prompt_v5.md (rewrite from v4 using template)
3. Schema rename (`domain_description` → `manifest_name`) + router updates
4. Frontend rename + instruction_file validation
5. Rewrite `graph_discovery.py` — L0 prompt-driven, L1-L3 data-driven
6. Update/delete prompts in `prompts.py` (remove generic grounded prompts)
7. Tests — update existing, add new for prompt-driven flow
8. Docker rebuild + validation run
9. Context/TODO/journal updates

## Validation Criteria

1. Run with DPA_Prompt_v5.md as instruction file, NO seed file, hierarchical mode, Gemini 3.1 Pro
2. L0 should discover 50+ entities across federal/state/municipal/nonprofit/employer/tribal
3. L0 should discover 100+ sources with real URLs
4. L1-L3 should produce 200+ programs total
5. Zero silent drops — all items persisted with confidence scores
6. SSE events flow correctly to frontend
7. All existing tests pass (237 backend, 16 frontend)

## Environment

- OS: Windows 10 (PowerShell)
- Workspace: `x:\RARIS`
- Python: 3.12 via UV
- Docker: `docker compose up --build -d` from workspace root
- Git remote: `origin/main`
- Test command: `docker exec raris-backend-1 python -m pytest tests/ -x -q`
- Backend logs: `docker compose logs -f --tail=200 backend`
- Debug log (V3 graph engine): `docker exec raris-backend-1 cat /app/debug-bab8de.log`

## Reference: Prior Session Transcripts

- [DPA V3 Build & Debug](16969738-0066-4937-8ae8-eb2d212af996) — P0 resilience build, V2 recall fix, LLM rules overhaul, V3 hierarchical build, taxonomy, handoff to Claude Code
- [V3 Build Review & Testing](bab8dee2-98af-4938-94c8-5bdc3891d19b) — Claude Code V3 build review, Docker setup, integration testing, discovery analysis
- [V4 Prompt Analysis](f0579382-1e69-461a-bfa3-79aa80c9a530) — This session: diagnosed prompt-algorithm mismatch, designed V4 architecture
