---
type: doc
created: 2026-03-10T11:30:00
sessionId: S20260310_1130
source: cursor-agent
description: Complete chronological history of all RLM discovery algorithm changes — tagged #algo for patent and optimization tracking
tags: [algo, raris, discovery, rlm, patent-track]
---

# RARIS — RLM Discovery Algorithm History

> **#algo** — All algorithm changes must be recorded here in chronological order.
> Tag every change `#algo` in commit messages, journal entries, and Cursor rules.
> This file is the canonical patent-track record of the RARIS discovery engine.

---

## What is the RLM Algorithm?

**RLM (Recursive Language Model)** is the core discovery engine of RARIS. It performs
BFS (Breadth-First Search) graph traversal where each node is a regulatory entity
and each LLM call expands one node into its children (sub-entities, sources, programs).

The key novelty is that the LLM itself drives graph construction — no hardcoded ontology,
no pre-built entity list. The graph is discovered live, recursively, from the model's
parametric knowledge and/or web-grounded search.

---

## Algorithm Change Log

---

### ALGO-001 — Flat LLM Discovery (Baseline)
**Date:** 2026-02-25 | **Commit:** `a633159` | **Version:** V1

**What it was:**
Single-call flat LLM discovery. One prompt → one JSON response listing all programs.
No graph, no recursion, no depth.

**Parameters:**
- depth: 1 (no expansion)
- provider: Anthropic
- grounding: none

**Outcome:**
- Programs found: ~15
- Sources found: 0
- Assessment: Too shallow. LLM cannot enumerate a comprehensive landscape in one call.

**Why it failed:**
A single top-down prompt returns only the most common/obvious programs. The LLM
doesn't have enough "space" in one call to enumerate the long tail.

---

### ALGO-002 — Web Grounding Added
**Date:** 2026-02-26 | **Commit:** `eb17f39` | **Version:** V1.5

**What changed:** `#algo`
Added `complete_grounded()` method to all LLM providers. Uses Google Search grounding
(Gemini) and web search tools (Anthropic/OpenAI) to ground responses in live web data
rather than purely parametric knowledge.

**Outcome:**
- Improved factual accuracy for URLs
- Gemini: caused `function_call` part confusion (discovered later, ALGO-006)
- Anthropic/OpenAI: worked but slow

---

### ALGO-003 — Hierarchical Discovery L0-L3
**Date:** 2026-02-26 | **Commit:** `59dfa13` | **Version:** V2 (Hierarchical)

**What changed:** `#algo`
Replaced flat discovery with a 4-level hierarchical model:
- **L0:** Discover all regulatory bodies (entities)
- **L1:** Expand each entity → find its programs
- **L2:** Verify programs (web grounding)
- **L3:** Gap fill — find what L1/L2 missed

**Parameters:**
- k_depth: configurable (L0=always, L1 if k≥2, L2 if k≥3, L3 if k≥4)
- All levels used `complete_grounded()`
- Timeouts: 300s L0, 180s L1-L3

**Outcome:**
- Programs found: significantly higher than V1
- Sources: populated for first time
- NJ baseline coverage: not yet measured at this stage

**Key innovation:**
Entity-first discovery — find who governs first, then ask each governor what it governs.
This is the foundational insight of the RLM approach.

---

### ALGO-004 — Prompt-Driven Discovery (V4)
**Date:** 2026-03-02 | **Commit:** `84d3eaf`, `4d814c2` | **Version:** V4

**What changed:** `#algo`
Eliminated all hardcoded domain knowledge from engine code. The uploaded instruction
prompt (`instruction_text`) IS the L0 user message. L1-L3 prompts are dynamically
built from L0 output data.

**Before:** Generic hardcoded prompts drove all levels. Domain prompt was passive context.
**After:** Domain prompt is the primary driver. Engine is domain-agnostic.

**Key files:**
- `prompts/DPA_Prompt_v5.md` — first domain-agnostic instruction template
- `backend/app/agent/prompts.py` — `L0_ORCHESTRATOR_SYSTEM`, `L1_ENTITY_EXPANSION_PROMPT`

**Outcome:**
- 306 tests passing
- First run with domain knowledge fully externalized
- Programs found: baseline established

---

### ALGO-005 — V5 BFS Queue Engine (Domain-Agnostic Sectors)
**Date:** 2026-03-02 | **Commit:** `4d814c2` | **Version:** V5

**What changed:** `#algo`
Full architectural rewrite. Replaced L0-L3 sequential hierarchy with parallel BFS:

- **L1:** N parallel sector calls seed the queue with entities
- **L2+:** Queue-driven BFS loop expands each entity
- Sector file (`sector_file`) uploaded at runtime — no domain content in code
- Each sector call receives full `instruction_text` + 3-line scope header
- New SSE event stream: `sector_start`, `sector_complete`, `l1_assembly_complete`,
  `entity_expansion_start`, `entity_expansion_complete`

**Parameters:**
- `sector_concurrency`: 3 (parallel sector calls)
- `k_depth`: 1=L1 only, 2=L1+L2, 3=L1+L2+L3
- `max_api_calls`: from config
- `max_entities_per_sector`: 50 (cap)

**New component:** `DiscoveryQueue` — priority queue with dedup by `target_id`,
max depth enforcement, visited set.

**Outcome:**
- 311 tests passing
- First successful multi-sector parallel discovery
- Sectors: 6 (federal, state_hfa, employer, tribal, municipal, county)

---

### ALGO-006 — Switched from `complete_grounded` to `complete` + JSON mode
**Date:** 2026-03-04 | **Commit:** `bff2d5f` / journal `007` | **Version:** V6 fix

**What changed:** `#algo`
**Critical change.** Switched ALL LLM calls from `complete_grounded()` to `complete()`
with `response_mime_type="application/json"`.

**Why:**
- Gemini `complete_grounded()` adds Google Search as a tool → model returns
  `function_call` parts instead of JSON → engine received 0 entities
- `response_mime_type="application/json"` forces pure JSON output, bypasses tool mode

**Side effect (negative, discovered later):**
Loss of web grounding. Engine now runs on purely parametric knowledge. This reduces
factual URL accuracy and depth for obscure statutes/regulations. The model cannot
fetch real pages — it can only recall from training data.

**Gemini thinking leak fix:**
Even without grounding, thinking budget caused reasoning text to leak into response.
`response_mime_type="application/json"` also fixed this.

**Parameters change:**
- `max_tokens`: 16384 → 32768 for L1 sector calls
- `timeout`: 300s → 900s

**Outcome at the time:**
- First successful live run with entities > 0
- K=1: 68 entities across 3 sectors
- Best single run (Anthropic Sonnet 4, K=3): **1,105 programs**
- Benchmark: Sonnet 4 >> GPT-4.1 >> Gemini 3.1 Pro >> GPT-5.2 Pro >> Gemini Flash

**Assessment (retrospective):**
This was the right fix for the Gemini JSON issue but introduced a trade-off:
parametric-only knowledge vs. grounded knowledge. The 1,105 program result was
for the DPA domain (housing assistance programs) which is well-represented in
training data. For the Insurance regulatory domain (NJSA Title 17B sub-chapters),
this change caused regressions — the model stops at Title level, doesn't enumerate
sub-chapters it would find if reading real NJDOBI pages.

---

### ALGO-007 — Dynamic Node-Type-Aware Expansion Prompts
**Date:** 2026-03-09 | **Commit:** `87203b9` (bundled) | **Version:** V6.1

**What changed:** `#algo`
`_expand_entity()` rewritten to use node-type-aware prompts:

**Before:**
```python
prompt = entity_context + instruction_text  # full L1 prompt sent to every L2 call
text, _citations = await self.llm.complete_grounded([...], max_tokens=16384)
```

**After:**
```python
# Priority: stored expansion_prompt from LLM (L1 output) > template fallback
expansion_question = entity.get("expansion_prompt") or build_expansion_prompt(entity)
# Template keyed by authority_type: regulator → statute enumeration template
#                                   compact → compact provisions template, etc.
prompt = f"## ENTITY EXPANSION — DEPTH L{depth+1}\n...{expansion_question}\n\n{DISCOVERY_OUTPUT_SCHEMA}"
text = await self.llm.complete([...], max_tokens=16384, response_mime_type="application/json")
```

**New components:**
- `build_expansion_prompt(entity)` — template factory keyed on `authority_type`
- `resolve_jurisdiction_code(entity)` — extracts/infers jurisdiction with fallback chain
- `JURISDICTION_CITATION_HINTS` — maps jurisdiction codes to citation format strings
  (e.g., `NJ` → `N.J.S.A.`, `TX` → `Tex. Ins. Code`)
- `EXPANSION_TEMPLATES` — 8 templates: `regulator`, `sro`, `compact`,
  `residual_market_mechanism`, `advisory_org`, `actuarial_body`, `trade_association`, `default`
- `DISCOVERY_OUTPUT_SCHEMA` — added `sub_citations[]` field and `CITATION DEPTH RULE`

**Citation Depth Rule (injected into every expansion call):**
> "For statutes and administrative code, emit a SEPARATE sources[] entry for EVERY
> individual title, chapter, part, article, and named act. NEVER collapse multiple
> citation identifiers into a single entry."

**Outcome:**
- Response size: 6-7K chars (Gemini Flash) to 47K chars (Anthropic Sonnet)
- Anthropic 47K chars = deep statute enumeration from parametric memory
- Gemini Flash 6-7K = still stopping at Title level
- **Problem:** Same source returned 5x by 5 different expansion calls (no cross-entity source dedup)
- **Problem:** Anthropic 47K × 435 entities = 15+ hour run at K=3

---

### ALGO-008 — Source ID Prefixing (PK Collision Fix)
**Date:** 2026-03-09 | **Commit:** `87203b9` (bundled)

**What changed:**
Prefixed all L2 LLM-generated source IDs with parent entity ID to prevent
`UniqueViolationError` on `sources_pkey`:

```python
sid = f"{entity_id}__{raw_sid}"  # e.g. "nj-dobi__src-njsa-17b27"
```

**Outcome:**
- Eliminated DB constraint violations
- **Side effect (negative):** Same logical source (e.g., NAIC website) returned by
  5 entities gets 5 different prefixed IDs → 5x duplicates in DB
- NJ run: 60 rows = 12 unique sources × 5 duplicates each

---

### ALGO-009 — Entity Registry (Canonical ID Enforcement)
**Date:** 2026-03-10 | **Commit:** `87203b9` | **Version:** V6.2

**What changed:** `#algo`
Added `EntityRegistry` class — in-memory canonical ID map for the entire run duration.

**Problem it solves:**
LLM independently invents entity IDs each call. L1: `new-jersey-doi`. L2: `nj-dobi`.
Sources saved under L2 ID become orphaned (no matching `regulatory_bodies` row).

**Implementation:**
```python
class EntityRegistry:
    # Maps (jurisdiction_code:normalized_name) → first-seen canonical ID
    # Maps any_seen_id → canonical_id (alias map for source body references)
    def resolve(entity) → canonical_id
    def rewrite(entity) → entity with canonical id
    def resolve_id(entity_id) → canonical_id
```

**Wired at:**
1. L1 queue enqueue — `entity = registry.rewrite(entity)`
2. L1 entity persist — `eid = registry.resolve(entity)`
3. L1 source body ref — `regulatory_body_id = registry.resolve_id(...)`
4. L2 sub-entity enqueue/persist — `sub_entity = registry.rewrite(sub_entity)`
5. L2 source body ref — `regulatory_body_id = registry.resolve_id(...)`

**Outcome:**
- Entity ID fragmentation: FIXED — `nj-dobi` now correctly joins to `new-jersey-doi` row
- Auto-approve: manifest transitions to `approved` on completion (no manual gate)
- Source duplicates: NOT fixed by this change (different root cause — ALGO-008 side effect)

---

### ALGO-010 — Auto-Approve
**Date:** 2026-03-10 | **Commit:** `87203b9`

**What changed:**
Both manifest completion paths changed from `ManifestStatus.pending_review`
to `ManifestStatus.approved`. Error path unchanged (stays `pending_review`).

**Outcome:** Eliminates manual approval gate for normal runs.

---

## Known Open Issues (as of 2026-03-10)

| ID | Issue | Root Cause | Status |
|----|-------|-----------|--------|
| OI-001 | Sources duplicated 5x | ALGO-008 prefix — same logical source, 5 parent entities | Open |
| OI-002 | Missing NJ sub-chapter statutes (17B:25, 17B:26...) | ALGO-006 dropped web grounding | Open |
| OI-003 | Anthropic K=3 runs take 15+ hours | 47K chars × 435 entities, sequential expansion | Open |
| OI-004 | Gemini Flash stops at Title level | Parametric only + response size cap | Open |

---

## Success Metrics by Algorithm Version

| Version | Domain | Model | K | Entities | Sources | NJ Coverage | Runtime |
|---------|--------|-------|---|----------|---------|-------------|---------|
| V1 flat | DPA | Anthropic | 1 | — | 0 | — | fast |
| V2 hier | DPA | Anthropic | 3 | — | — | — | — |
| V5 BFS | DPA | Sonnet 4 | 1 | 202 | — | — | ~5 min |
| V5 BFS | DPA | Sonnet 4 | 3 | — | — | — | — |
| V6 fix | DPA | Sonnet 4 | 1 | 68 | — | — | ~45 sec |
| V6 fix | DPA | Sonnet 4 | 3 | — | — | — | — |
| V6 fix | DPA | Sonnet 4 | 3 | — | 1,105 prg | — | — |
| V6.1 | Insurance | Gemini Flash | 3 | 68 | 12 unique | 10/30 (33%) | ~22 min |
| V6.2 | Insurance | Anthropic Sonnet | 3 | 93/435 | — | — | 3.5h+ (killed) |

---

## Pending Algorithm Experiments

| ID | Hypothesis | Expected Impact |
|----|-----------|----------------|
| EXP-001 | Restore `complete_grounded()` for L2+ expansion only | +depth for obscure statutes, slower |
| EXP-002 | Parallel entity expansion (asyncio.gather N at a time) | -runtime 5-10x |
| EXP-003 | Source dedup by (name, entity_id) not prefixed ID | -5x source inflation |
| EXP-004 | Hybrid: grounded L1 (entity discovery) + parametric L2 (statute enum) | best of both |
| EXP-005 | Haiku for volume runs, Sonnet for NJ-targeted expansion | cost/quality balance |
