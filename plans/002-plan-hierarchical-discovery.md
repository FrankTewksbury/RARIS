---
type: plan
created: 2026-03-01T20:00:00
sessionId: S20260301_1800
source: cursor-agent
description: Hierarchical graph discovery architecture (L0-L3) with web grounding and topic-indexed seeds
---

# DPA Discovery V3 — Hierarchical Graph Discovery

## Goal

Replace the flat, single-pass, hallucination-dependent discovery pipeline with a multi-level graph traversal (L0/L1/L2/L3) that uses live web grounding at each level and topic-indexed seed injection to discover real, verifiable DPA programs.

## Why the Current Architecture Fails

The V2 pipeline makes 5 sequential LLM calls — all against training data, zero web access. Result: ~2% seed recovery, zero CDFIs, zero EAH, zero tribal housing. The LLM cannot discover what it hasn't been trained on, and it fabricates URLs that 404.

Root cause diagnosed in session S20260301: **context source mismatch**. Seed batches (especially municipal/specialized programs) had no relevant verification sources because the landscape mapper and source hunter only discover "regulatory bodies" — a narrow entity type that misses CDFIs, nonprofits, employers, and tribal authorities.

## Architecture Overview

```
L0 — Federal/State Landscape (grounded)
  └─ Landscape Mapper + google_search → real regulatory bodies
  └─ Source Hunter + google_search → real URLs
  └─ Program Enumerator → initial program set

L1 — Entity Expansion (grounded + topic seeds)
  └─ For each L0 entity: discover child entities
  └─ Inject topic-matched seeds per funding_entity category
  └─ Targeted web search per entity type (see taxonomy)

L2 — Program Verification (grounded)
  └─ URL verification for each L1 program
  └─ Evidence collection + portal fingerprinting

L3 — Gap Fill
  └─ Remaining unmatched seeds → targeted search
  └─ Coverage gaps from L0-L2 → explicit queries
  └─ Hard cap — prevents graph inflation
```

Termination: L3 reached (hard cap), no new programs at current level (convergence), or all seeds matched.

## Taxonomy Reference

See `research/003-analysis-dpa-program-taxonomy.md` for the three-axis classification:
- **Axis I — Funding Entity**: federal, state_hfa, municipal, employer, nonprofit, tribal, gse
- **Axis II — Benefit Structure**: grant, forgivable_lien, deferred_lien, repayable_lien, mcc, tax_abatement, rate_subsidy, renovation
- **Axis III — Eligibility Persona**: fthb, veteran, occupation, lmi, tribal, demographic, property_specific, general

## Implementation Phases

### Phase A — LLM Provider Grounding Support

Add `complete_grounded()` to `LLMProvider` ABC. Each provider implements web search:

- **Gemini**: `types.Tool(google_search=types.GoogleSearch())` in config. Extract `grounding_metadata` from response.
- **Anthropic**: `{"type": "web_search_20260209", "name": "web_search"}` in tools. Parse tool_use blocks.
- **OpenAI**: `client.responses.create()` with `tools=[{"type": "web_search"}]`. Parse annotations.

Returns `(str, list[Citation])` — text plus source URLs.

Grounding is selective:
- Grounded: landscape mapper, source hunter, entity expansion, URL verification
- Not grounded: program enumerator, relationship mapper, coverage assessor

Files: `backend/app/llm/base.py`, `gemini_provider.py`, `anthropic_provider.py`, `openai_provider.py`

### Phase B — Topic-Indexed Seed Parser

Extend `_normalize_program_seed()` in `manifests.py` to infer `program_type` from seed fields. Build `dict[str, list[dict]]` grouping seeds by type.

Inference: keyword matching on `name`, `administering_entity`, `benefits`. Explicit `program_type` field overrides.

Categories: `fthb`, `veteran`, `occupation`, `lmi`, `tribal`, `municipal`, `cdfi`, `eah`, `general`

Files: `backend/app/routers/manifests.py`

### Phase C — Discovery Graph Engine

New file `backend/app/agent/graph_discovery.py` with `DiscoveryGraph` class. Implements L0/L1/L2/L3 traversal reusing existing pipeline stages (landscape mapper, source hunter, program enumerator) with grounding and topic-matched seed injection.

Graph state is in-memory during the run. Final output is a flat manifest (programs, sources, bodies). The graph is the traversal strategy, not the persistence model.

Files: `backend/app/agent/graph_discovery.py` (NEW), `backend/app/agent/prompts.py`

### Phase D — Route Wiring

Add `discovery_mode: "flat" | "hierarchical"` to `GenerateManifestRequest`. Branch `_run_agent()`:
- `flat`: existing `DomainDiscoveryAgent` (unchanged)
- `hierarchical`: new `DiscoveryGraph`

Files: `backend/app/routers/manifests.py`, `backend/app/schemas/manifest.py`

### Phase E — Metrics and Observability

SSE events extended with: `discovery_level`, `nodes_at_level`, `cumulative_programs`, `seed_match_rate_by_topic`

## Deferred Code Fixes (Prerequisite)

Before starting Phase A, these corrections from the LLM rules overhaul must be applied:

- `backend/app/llm/gemini_provider.py` line 49: `gemini-3.1-flash-preview` → `gemini-3-flash-preview`
- `backend/app/config.py` line 30: same correction in `gemini_fallback_models` default
- `.env.example`: correct fallback model ID
- `backend/app/llm/openai_provider.py` line 10: `gpt-4o` → `gpt-5.2-pro`

## Validation Targets

- All existing 230+ backend tests pass (flat mode unchanged)
- Seed recovery rate: 50%+ (up from 2%)
- Coverage: programs found in municipal, nonprofit, employer, and tribal categories (currently zero)
- All discovered URLs are real (grounded, not hallucinated)

## DFW Tags

`#track/dpa-v3-discovery` `#priority/critical` `#status/ready` `#agent/claude-code`
