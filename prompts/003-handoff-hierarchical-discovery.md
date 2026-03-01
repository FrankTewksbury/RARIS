---
type: handoff
created: 2026-03-01T20:15:00
sessionId: S20260301_1800
source: cursor-agent
target: claude-code
description: Build handoff for hierarchical graph discovery (L0-L3) with web grounding and topic-indexed seeds
---

# Handoff: Hierarchical Graph Discovery — Claude Code Build Agent

## Objective

Implement the hierarchical graph discovery architecture (DPA V3) that replaces the flat single-pass LLM pipeline with a multi-level traversal using live web grounding and topic-indexed seed injection.

## Mandatory Reads Before Coding

Read these files in order. Do not skip any.

1. `CLAUDE.md` — Agent bootstrap and project context
2. `docs/DFW-CONSTITUTION.md` — Universal rules (P1-P9)
3. `context/_ACTIVE_CONTEXT.md` — Current project state
4. `plans/_TODO.md` — Active and queued work
5. `plans/002-plan-hierarchical-discovery.md` — **The authoritative plan for this build**
6. `research/003-analysis-dpa-program-taxonomy.md` — **The three-axis taxonomy (funding entity, benefit structure, eligibility persona)**
7. `.cursor/rules/gemini-model-rules.mdc` — Gemini 3.1 SDK patterns including web grounding (Section 3)
8. `.cursor/rules/anthropic-model-rules.mdc` — Anthropic SDK patterns including web search (Section 3)
9. `.cursor/rules/openai-model-rules.mdc` — OpenAI SDK patterns including web search (Section 3)

## Current State — What Already Works

### Docker Stack
```
docker-compose.yml → 4 services:
  db:       pgvector/pgvector:pg16 (port 5432)
  redis:    redis:7 (port 6379)
  backend:  python:3.12-slim + uv (port 8000)
  frontend: React 18 + nginx (port 80)
```

Start: `docker compose up --build`
Backend health: `http://localhost:8000/health`

### LLM Provider Architecture
```
backend/app/llm/base.py          — LLMProvider ABC (complete, stream)
backend/app/llm/gemini_provider.py — GeminiProvider with full resilience (_call_with_resilience)
backend/app/llm/anthropic_provider.py — AnthropicProvider (basic, no resilience)
backend/app/llm/openai_provider.py — OpenAIProvider (basic, no resilience)
backend/app/llm/registry.py      — get_provider() factory
```

The Gemini provider has the most mature resilience: exponential backoff + jitter, ordered model fallback chain, fail-fast on 400/401/403/404, retry on 429/500/502/503/504. Anthropic and OpenAI providers are minimal.

### Discovery Pipeline (V2 — flat, to be preserved)
```
backend/app/agent/discovery.py    — DomainDiscoveryAgent (5-stage linear pipeline)
backend/app/agent/prompts.py      — All LLM prompts (LANDSCAPE_MAPPER, SOURCE_HUNTER, etc.)
```

The flat pipeline MUST be preserved for backward compatibility. The new graph engine is a separate module selected via `discovery_mode`.

### API Route
```
POST /api/manifests/generate      — Triggers discovery
  JSON body: domain_description, llm_provider, k_depth, geo_scope, target_segments
  Multipart: constitution_file, instruction_file, seeding_files
```

Seed files are parsed in `backend/app/routers/manifests.py` by `_parse_seed_upload()` → `_classify_seed_record()` → `_normalize_program_seed()`.

### Config
```
backend/app/config.py             — Settings via pydantic-settings + .env
.env                              — Live environment (GEMINI_API_KEY, LLM_PROVIDER=gemini, etc.)
.env.example                      — Template
```

### Package Manager
**UV is mandatory.** Do not use pip/conda/poetry. All dependency operations use `uv add`, `uv sync`, `uv run`.

### Tests
```
cd backend && uv run pytest tests/ -x -q
```
230+ backend tests, 16 frontend tests. All must pass after every phase.

## Prerequisite — Deferred Code Fixes

Apply these corrections FIRST before starting Phase A. They fix model ID errors found during the LLM rules overhaul:

1. `backend/app/llm/gemini_provider.py` line 49: Change `gemini-3.1-flash-preview` to `gemini-3-flash-preview` in the hardcoded safety net list
2. `backend/app/config.py` line 30: Change `gemini-3.1-flash-preview` to `gemini-3-flash-preview` in `gemini_fallback_models` default
3. `.env.example`: Update `GEMINI_FALLBACK_MODELS` to use `gemini-3-flash-preview`
4. `backend/app/llm/openai_provider.py` line 10: Change default model from `gpt-4o` to `gpt-5.2-pro`

Run tests after these fixes. Commit: `fix(llm): correct model IDs per vendor-grounded rules overhaul`

## Phase A — LLM Provider Grounding Support

### What to Build

Add a new abstract method to `LLMProvider`:

```python
# backend/app/llm/base.py
from dataclasses import dataclass

@dataclass
class Citation:
    url: str
    title: str = ""

class LLMProvider(ABC):
    @abstractmethod
    async def complete(self, messages: list[dict], **kwargs) -> str: ...

    @abstractmethod
    async def stream(self, messages: list[dict], **kwargs) -> AsyncIterator[str]: ...

    async def complete_grounded(self, messages: list[dict], **kwargs) -> tuple[str, list[Citation]]:
        """Generate with web search/grounding. Returns (text, citations).
        Default: falls back to complete() with no citations."""
        text = await self.complete(messages, **kwargs)
        return text, []
```

### Gemini Implementation

In `gemini_provider.py`, override `complete_grounded()`:

```python
async def complete_grounded(self, messages, **kwargs):
    contents = self._build_contents(messages)
    config = self._build_config(kwargs)
    config.tools = [types.Tool(google_search=types.GoogleSearch())]

    text = await self._call_with_resilience(contents, config, label="grounded")

    # Extract citations from grounding metadata
    citations = []
    # Note: _call_with_resilience returns text, not the full response.
    # You'll need to modify it or add a variant that returns the response object
    # so you can access response.candidates[0].grounding_metadata.grounding_chunks
    return text, citations
```

**Important:** The current `_call_with_resilience()` returns `response.text`. For grounding, you need access to `response.candidates[0].grounding_metadata`. Either:
- (A) Add a `_call_with_resilience_full()` that returns the full response object, or
- (B) Add a `return_metadata: bool` flag to the existing method

The Gemini grounding pattern from the rule file (`.cursor/rules/gemini-model-rules.mdc` Section 3):

```python
grounding_tool = types.Tool(google_search=types.GoogleSearch())
config = types.GenerateContentConfig(
    tools=[grounding_tool],
    thinking_config=types.ThinkingConfig(thinking_budget=16384)
)
response = client.models.generate_content(model=model, contents=contents, config=config)

# Access grounding metadata
candidate = response.candidates[0]
if candidate.grounding_metadata and candidate.grounding_metadata.grounding_chunks:
    for chunk in candidate.grounding_metadata.grounding_chunks:
        if chunk.web:
            citations.append(Citation(url=chunk.web.uri, title=chunk.web.title))
```

### Anthropic Implementation

From the rule file (`.cursor/rules/anthropic-model-rules.mdc` Section 3):

```python
async def complete_grounded(self, messages, **kwargs):
    system_msg, chat_messages = self._split_system(messages)
    params = {
        "model": kwargs.get("model", self.model),
        "max_tokens": kwargs.get("max_tokens", 4096),
        "messages": chat_messages,
        "tools": [{"type": "web_search_20260209", "name": "web_search"}],
    }
    if system_msg:
        params["system"] = system_msg

    response = await self.client.messages.create(**params)

    text_parts = []
    citations = []
    for block in response.content:
        if block.type == "text":
            text_parts.append(block.text)
        # Parse web_search tool_use results for citations
    return "\n".join(text_parts), citations
```

### OpenAI Implementation

From the rule file (`.cursor/rules/openai-model-rules.mdc` Section 3):

```python
async def complete_grounded(self, messages, **kwargs):
    # OpenAI web search requires the Responses API, not Chat Completions
    response = await self.client.responses.create(
        model=kwargs.get("model", self.model),
        input=messages[-1]["content"],  # Responses API uses 'input' not 'messages'
        tools=[{"type": "web_search"}],
    )

    citations = []
    for item in response.output:
        if item.type == "message":
            for annotation in item.content[0].annotations:
                if annotation.type == "url_citation":
                    citations.append(Citation(url=annotation.url, title=annotation.title))
    return response.output_text, citations
```

### Validation
- Unit test: `complete_grounded()` on each provider returns `(str, list[Citation])`
- Mock test: verify Gemini adds `google_search` tool to config
- All existing tests pass (non-grounded paths unchanged)

Commit: `feat(llm): add complete_grounded() with web search support for all providers`

## Phase B — Topic-Indexed Seed Parser

### What to Build

In `backend/app/routers/manifests.py`, extend `_normalize_program_seed()` to infer `program_type`:

```python
_PROGRAM_TYPE_KEYWORDS = {
    "veteran": ["veteran", "va ", "military", "service member", "armed forces"],
    "tribal": ["tribal", "native american", "alaska native", "section 184", "indian"],
    "occupation": ["teacher", "firefighter", "police", "ems", "good neighbor", "gnnd", "first responder"],
    "cdfi": ["cdfi", "community development financial"],
    "eah": ["employer", "workforce housing", "employee homeownership"],
    "municipal": ["city of", "county of", "cdbg", "home funds", "block grant"],
    "lmi": ["low income", "moderate income", "lmi", "80% ami", "120% ami"],
    "fthb": ["first-time", "first time", "fthb", "homebuyer"],
}

def _infer_program_type(record: dict) -> str:
    """Infer program_type from seed record fields."""
    if explicit := record.get("program_type") or record.get("category"):
        return explicit.lower().strip()
    searchable = " ".join([
        str(record.get("name", "")),
        str(record.get("administering_entity", "")),
        str(record.get("benefits", "")),
    ]).lower()
    for ptype, keywords in _PROGRAM_TYPE_KEYWORDS.items():
        if any(kw in searchable for kw in keywords):
            return ptype
    return "general"
```

Add to `_normalize_program_seed()` output:
```python
"program_type": _infer_program_type(record),
```

Add a grouping function:
```python
def _index_seeds_by_type(seeds: list[dict]) -> dict[str, list[dict]]:
    index: dict[str, list[dict]] = {}
    for seed in seeds:
        ptype = seed.get("program_type", "general")
        index.setdefault(ptype, []).append(seed)
    return index
```

### Validation
- Unit test: seed with "CalHFA" → `state_hfa` or `fthb`
- Unit test: seed with "CDFI" in name → `cdfi`
- Unit test: seed with explicit `program_type` field → uses that value
- Unit test: `_index_seeds_by_type()` groups correctly

Commit: `feat(seeds): add program_type inference and topic-indexed seed grouping`

## Phase C — Discovery Graph Engine

### What to Build

New file: `backend/app/agent/graph_discovery.py`

This is the core new module. It orchestrates L0-L3 traversal using the existing pipeline stages (landscape mapper, source hunter, program enumerator) with grounding and topic-matched seed injection.

Key design:
- Reuse `_landscape_mapper()`, `_source_hunter()`, `_program_enumerator()` from `DomainDiscoveryAgent` (import or inherit)
- Add `grounded=True` flag to calls that need web search
- At L1, classify each entity's topic and inject matching seeds from the index
- At L3, collect unmatched seeds and run targeted gap-fill searches
- Graph state is in-memory (no new DB tables)
- Final output is a flat manifest (same schema as V2)
- SSE events include `discovery_level` field

The taxonomy in `research/003-analysis-dpa-program-taxonomy.md` defines the search queries per entity type. Use those templates for grounded L1 expansion.

### Prompt Updates

Add level-aware prompt variants to `backend/app/agent/prompts.py`:
- `GROUNDED_LANDSCAPE_MAPPER_PROMPT` — instructs model to use web search for current entities
- `GROUNDED_SOURCE_HUNTER_PROMPT` — instructs model to use web search for real URLs
- `L1_ENTITY_EXPANSION_PROMPT` — for discovering child entities of an L0 body
- `L3_GAP_FILL_PROMPT` — for targeted search of unmatched seed categories

### Validation
- Unit test: `DiscoveryGraph` instantiates and runs L0 with mocked LLM
- Unit test: seed index routing — CDFI seeds only injected at nonprofit nodes
- Unit test: L3 termination — stops when no new programs found
- Integration test: full L0-L1 run with Gemini grounding returns real URLs

Commit: `feat(discovery): add hierarchical graph discovery engine (L0-L3)`

## Phase D — Route Wiring

Add `discovery_mode: str = "flat"` to `GenerateManifestRequest` in `backend/app/schemas/manifest.py`.

In `backend/app/routers/manifests.py` `_run_agent()`, branch:

```python
if discovery_mode == "hierarchical":
    from app.agent.graph_discovery import DiscoveryGraph
    seed_index = _index_seeds_by_type(seed_programs or [])
    agent = DiscoveryGraph(llm=provider, db=db, manifest_id=manifest_id)
    async for event in agent.run(..., seed_index=seed_index):
        ...
else:
    agent = DomainDiscoveryAgent(llm=provider, db=db, manifest_id=manifest_id)
    async for event in agent.run(...):
        ...
```

Commit: `feat(api): add discovery_mode parameter for flat vs hierarchical discovery`

## Phase E — Metrics and Observability

Extend SSE events from `DiscoveryGraph` with:
- `discovery_level`: 0-3
- `nodes_at_level`: count of entities being expanded
- `cumulative_programs`: running total across all levels
- `seed_match_rate_by_topic`: `dict[str, float]` per taxonomy category

Commit: `feat(discovery): add level-aware metrics to hierarchical discovery SSE events`

## Cursor Rules Reference

The LLM rules were overhauled on 2026-03-01 and are vendor-grounded (March 2026 documentation). They live in `.cursor/rules/` and are also synced to `X:\DFW\Tools\rules\`. Key sections for this build:

| Rule File | Critical Section for This Build |
|-----------|-------------------------------|
| `gemini-model-rules.mdc` | Section 3: Web Grounding with Google Search — `types.Tool(google_search=types.GoogleSearch())`, `grounding_metadata` access |
| `anthropic-model-rules.mdc` | Section 3: Web Search Tool — `web_search_20260209`, dynamic filtering |
| `openai-model-rules.mdc` | Section 3: Web Search (Responses API) — `web_search` tool, citations, domain filtering |

All three rules share a consistent 7-section structure. The web search patterns in each rule are the canonical implementation reference for Phase A.

## Environment

```
OS: Windows 10
Project root: X:\RARIS
Python: 3.12 (via UV in Docker)
Package manager: UV (mandatory — do not use pip)
Docker: docker compose up --build
Backend tests: cd backend && uv run pytest tests/ -x -q
Frontend tests: cd frontend && npm test
Git remote: https://github.com/FrankTewksbury/RARIS.git
Branch: main
```

## Build Sequence

```
1. Apply prerequisite code fixes (model IDs)           → commit
2. Phase A: LLM provider grounding support              → commit
3. Phase B: Topic-indexed seed parser                   → commit
4. Phase C: Discovery graph engine                      → commit
5. Phase D: Route wiring                                → commit
6. Phase E: Metrics and observability                   → commit
7. Run full test suite                                  → verify
8. Update context/_ACTIVE_CONTEXT.md                    → commit
```

## Success Criteria

- All existing tests pass (flat mode backward compatible)
- `complete_grounded()` works on Gemini with real `google_search` results
- Seed parser correctly infers `program_type` for all taxonomy categories
- `DiscoveryGraph` runs L0-L1 and returns programs with grounded URLs
- SSE events include `discovery_level` and per-topic seed match rates
- Seed recovery rate target: 50%+ (up from 2% in V2)

## DFW Tags

`#track/dpa-v3-discovery` `#priority/critical` `#status/handoff` `#agent/claude-code`
