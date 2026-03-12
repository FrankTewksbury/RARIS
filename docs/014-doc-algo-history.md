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

### ALGO-011 — Prompt Observability Instrumentation
**Date:** 2026-03-10 | **Commit:** pending | **Version:** V6.2 (instrumentation)

**What changed:** `#algo`
Added full prompt capture and display for every entity expansion call.
This is an observability change — no algorithmic behavior is modified.

**Components added:**

- `log_prompt()` in `backend/app/llm/call_logger.py` — activated the previously dead
  `_should_log_prompts()` / `settings.llm_log_prompts` flag. When `LLM_LOG_PROMPTS=ON`,
  prints the full assembled expansion prompt to stdout using GREEN major header format
  per `print-header-style.mdc` + `log-file-rule.mdc §2`.

- `logger.info("[graph v6][expansion_prompt] ...")` in `_expand_entity()` — always logs
  entity ID, depth, prompt char count, and first 200 chars of prompt at INFO level
  regardless of `LLM_LOG_PROMPTS` setting (goes to `docker compose logs backend`).

- `expansion_prompt_preview` field added to `entity_expansion_start` SSE event — carries
  the first 200 chars of the entity's stored `expansion_prompt` (L1-generated), giving
  the frontend real-time visibility into what question is about to be asked.

- `.env.example` updated: `LLM_LOG_PROMPTS=OFF` documented with instructions.

**Cursor terminal color fix:**
Pinned ANSI hex values in `C:\Users\frank\AppData\Roaming\Cursor\User\profiles\-650467ac\settings.json`
via `workbench.colorCustomizations` to match the `log-file-rule.mdc §2` color scheme:
GREEN=`#00FF90`, WHITE=`#F0F0F0`, YELLOW=`#FFD700`, RED=`#FF4444`, PURPLE/MAGENTA=`#CC88FF`.

**How to use:**
Set `LLM_LOG_PROMPTS=ON` in `.env`, rebuild containers, run any discovery run.
Every entity expansion will print:
```
============================================
     EXPANSION PROMPT  L2  [nj-dobi]
============================================
Entity : New Jersey Department of Banking and Insurance
Type   : regulator  |  Jurisdiction: NJ
------------------------------------------------------------
## ENTITY EXPANSION — DEPTH L2
...full prompt text...
============================================
```

**Outcome:** Zero behavioral change. Full prompt visibility for analysis and debugging.

---

| ID | Issue | Root Cause | Status |
|----|-------|-----------|--------|
| OI-001 | Sources duplicated 5x | ALGO-008 prefix — same logical source, 5 parent entities | Open |
| OI-002 | Missing NJ sub-chapter statutes (17B:25, 17B:26...) | ALGO-006 dropped web grounding | **ALGO-012 addresses** |
| OI-003 | Anthropic K=3 runs take 15+ hours | 47K chars × 435 entities, sequential expansion | **ALGO-012 reduces per-call response size** |
| OI-004 | Gemini Flash stops at Title level | Parametric only + response size cap | **ALGO-012 matches model capability to one level per call** |

---

### ALGO-012 — Fine-Grain BFS Recursion (Framework Owns Traversal)
**Date:** 2026-03-10 | **Commit:** pending | **Version:** V7 #algo

**What changed:**

1. **EXPANSION_TEMPLATES replaced** — The single monolithic `"regulator"` template (6 depth rules, hardcoded NJ citation examples) is replaced with 13 node-type-keyed single-question templates keyed as `"node:entity:{authority_type}"` and `"node:source_title"` / `"node:source_chapter"` / `"node:source_section"`.

2. **One question per call** — Each template asks exactly one bounded question: "What are the direct children of this node at this level?" The LLM returns only direct children. No internal LLM recursion.

3. **Source nodes enter the BFS queue** — Sources returned from expansion are now classified by their `depth_hint` field (`title|chapter|section|leaf`) and re-enqueued as `source_title`, `source_chapter`, or `source_section` nodes. The framework traverses the citation tree level by level.

4. **`_expand_entity()` renamed `_expand_node()`** — Dispatcher routes by `node_type` (entity vs source node type) not just `authority_type`. Accepts `node_type` parameter.

5. **Stored `expansion_prompt` from L1 REMOVED** — The if/else "use L1 expansion_prompt if present, else fall back to template" logic is deleted. The template is always authoritative. L1 no longer writes expansion prompts (field removed from `DISCOVERY_OUTPUT_SCHEMA`).

6. **`depth_hint` and `citation` fields added to schema** — `depth_hint` (required) classifies each source's depth level. `citation` (required) carries the full citation identifier. Both are used by the engine to route re-enqueuing.

7. **`jurisdiction_code` added to sources schema** — Sources now carry their jurisdiction explicitly.

8. **Run sequence tag on all log output** — `log_stage()`, `log_heartbeat()`, and `log_prompt()` now accept `manifest_id` and prefix every output line with `[RUN-{timestamp}]` for per-run log correlation.

9. **NJ-specific examples removed from templates** — All hardcoded `N.J.A.C. 11:2-17` and `N.J.S.A. 17:22A-26` examples replaced with `{citation_hint}` placeholders and generic descriptions.

10. **"Statute title" added to task sentences** — All entity templates now include "statute title, administrative code title" in the task sentence (not just in depth rules).

**Rationale:**
ALGO-007 introduced internal LLM recursion ("enumerate everything under this node exhaustively"). This produced 47K-char responses for Anthropic, caused 15+ hour runs, and still missed key sub-chapters because the LLM chose what to include. ALGO-012 restores the principle that **the framework drives traversal, the LLM answers single questions**. Each LLM call is now small, bounded, and verifiable. Depth is controlled by `k_depth` with precise semantics: k=2 → titles, k=3 → chapters, k=4 → sections.

**New k_depth semantics:**
| k | What is discovered |
|---|-------------------|
| 1 | Entities only (no expansion) |
| 2 | Entities + top-level statute/code titles |
| 3 | Entities + titles + chapters/parts/named acts |
| 4 | Entities + titles + chapters + individual sections |
| 5 | Full depth to sub-sections (leaf level) |

**Expected outcome:** Each NJ DOBI expansion call at k=2 returns only `[N.J.S.A. Title 17, N.J.S.A. Title 17B, N.J.A.C. Title 11, ...]`. At k=3, Title 17B expands to its chapters. At k=4, each chapter expands to its sections. Complete statutory coverage without model overload.

**Files changed:**
- `backend/app/agent/prompts.py` — 13 new templates, updated schema, new `build_expansion_prompt` signature
- `backend/app/agent/graph_discovery.py` — `_expand_node()`, source enqueue by `depth_hint`, `node_type` in SSE events
- `backend/app/llm/call_logger.py` — `manifest_id` param on all log functions, `_run_tag()` extractor

---

### ALGO-013 — depth_hint Required in L1 Prompts; BFS Enqueue Fix
**Date:** 2026-03-12 | **Commit:** `e3f6c87` | **Version:** V7.1 #algo

**What changed:**

1. **`depth_hint` added to all 4 L1 insurance prompt schemas** — `1-Insurance_Prompt_v5.md` through
   `4-Insurance_Prompt_v5.md` were missing `depth_hint` from their `sources[]` output schema. The BFS
   enqueue logic in `graph_discovery.py` requires `depth_hint IN ('title','chapter','section')` to
   re-enqueue a source for deeper expansion. Without it every L1-seeded source was treated as a leaf
   and never expanded. Added `"depth_hint": "title|chapter|section|leaf"` field and a classification
   rule to the QUALITY RULES section of all 4 prompts.

2. **`_write_checkpoint()` uses fresh session** — Long-lived `self.db` session shared across the L2
   loop becomes stale after hundreds of flush/commit cycles. Checkpoint writes to the `Manifest` row
   were silently no-oping. Fixed by opening `async with _async_session_factory() as fresh_db` inside
   `_write_checkpoint()`, isolated from the loop session.

3. **Session rollback on flush error** — Added `await self.db.rollback()` as first line of both outer
   `except` handlers in `run()` and `run_resumed()`. Clears poisoned session state so subsequent nodes
   can proceed.

4. **`sources.id` / `regulatory_bodies.id` widened to VARCHAR(255)** — Compound IDs at k=3 depth exceed
   100 chars. Migration 009 widens `sources.id`, `sources.regulatory_body_id`, `regulatory_bodies.id`.

5. **`max_api_calls` raised 1500 → 3000** — Insufficient for k=3 runs with 504+ queue items.

6. **Broken program count query fixed** — `__import__("sqlalchemy").table("programs").c.id` at line
   1024 of `run_resumed()` was a malformed reflection expression causing `AttributeError: id` at run
   completion. Fixed with `select(func.count()).select_from(Program).where(Program.manifest_id == ...)`.

7. **DB repair script** — `backend/scripts/repair_depth_hint_checkpoint.py` patches existing manifests
   with NULL `depth_hint` and writes a corrected BFS checkpoint.

**Root cause of low NJ recall (ALGO-012 validation):**
499/1005 sources (across all 50 states + territories + federal) had `depth_hint = NULL` because the
L1 prompts never asked for it. The BFS engine silently treated all of them as leaves, so no state's
top-level statutes or regulations were ever expanded into chapters. NJ recall was 40% (12/30) not
because the engine couldn't find the sub-statutes — it never tried.

**Before / After:**
```
Before: sources[].schema = {id, name, regulatory_body, type, format, authority, url, access_method, confidence}
After:  sources[].schema = {id, name, regulatory_body, type, format, authority, url, access_method, depth_hint, confidence}
```

**Outcome:**
- Checkpoint batch 20 confirmed written (fresh session fix validated)
- 499 NULL depth_hint rows repaired in DB
- 391 undrilled title sources queued for chapter expansion via repair checkpoint
- Run resumed successfully — NJ chapter-level expansion now in progress
- NJ recall post-expansion: TBD (measuring after current run completes)

**Files changed:**
- `prompts/1-Insurance_Prompt_v5.md` — added `depth_hint` field + classification rule
- `prompts/2-Insurance_Prompt_v5.md` — added `depth_hint` field + classification rule
- `prompts/3-Insurance_Prompt_v5.md` — added `depth_hint` field + classification rule
- `prompts/4-Insurance_Prompt_v5.md` — added `depth_hint` field + classification rule
- `backend/app/agent/graph_discovery.py` — fresh session in `_write_checkpoint`, rollbacks, program count fix
- `backend/app/models/manifest.py` — String(255) for id columns
- `backend/app/config.py` — max_api_calls 3000
- `backend/alembic/versions/009_widen_id_columns.py` — NEW migration
- `backend/scripts/repair_depth_hint_checkpoint.py` — NEW repair utility
- `frontend/src/pages/Dashboard.tsx` — maxApiCalls 3000
- `frontend/src/components/AgentProgressPanel.tsx` — maxApiCalls default 3000

---

### ALGO-014 — Dynamic Context Injection for Source Node Expansion
**Date:** 2026-03-12 | **Commit:** pending | **Version:** V7.2 #algo

**What changed:**

1. **`DOMAIN_CHAPTER_HINTS` lookup table added to `prompts.py`** — keyed by `(domain_key, source_type)`,
   returns a list of functional chapter descriptions that are structurally expected for that domain.
   No hardcoded citation numbers — only functional categories (e.g. "claims handling and unfair claims
   settlement practices"). Domain key is derived from `sector_key` at runtime via `_derive_domain_key()`.

2. **`build_sibling_context()` function added to `prompts.py`** — takes `already_found: list[str]`
   (citations already in DB) and `domain_hints: list[str]` (from lookup table). Returns a text block:
   ```
   CONTEXT — Already found under this parent: N.J.A.C. 11:1, N.J.A.C. 11:3, ...
   Do NOT re-return any of the above — return only entries not yet listed.
   Completeness check — ensure you have captured chapters governing: claims handling...; ...
   ```
   Returns empty string when both inputs are empty (no overhead for zero-context calls).

3. **`build_expansion_prompt()` gains `sibling_context: str = ""` parameter** — when non-empty,
   appended to the source-node template output before returning. Entity node calls are unaffected.

4. **`_expand_node()` queries DB siblings before calling `build_expansion_prompt()`** — for
   `source_title` and `source_chapter` nodes only. Queries `sources` where `id LIKE "{node_id}__%"`
   but NOT `id LIKE "{node_id}%__%__%"` (direct children only, not grandchildren). Looks up domain
   hints via `DOMAIN_CHAPTER_HINTS[(domain_key, src_type)]`. Injects combined context via
   `build_sibling_context()`. DB query wrapped in `try/except` — failure degrades gracefully to
   no context (no run impact).

5. **`src_meta` dict gains `id` and `type` fields** — needed by `_expand_node()` to key the domain
   hints lookup and identify the node in the sibling DB query.

**Rationale:**
Static templates ask "what are the children?" but give the LLM no signal about completeness.
The LLM returns what it most readily recalls — prominent chapters get returned, low-profile ones
(Claims Ch. 2, Producers Ch. 17) get skipped. ALGO-014 makes the prompt context-aware at call
time using data the engine already has in the DB. The static templates remain generic and reusable.
All intelligence moves into the prompt builder, not the template strings.

**Before / After:**
```
Before: expansion_question = build_expansion_prompt(node, node_type=node_type)
After:  sibling_context = build_sibling_context(already_found, domain_hints)
        expansion_question = build_expansion_prompt(node, node_type=node_type, sibling_context=sibling_context)
```

**Outcome:** Validated. N.J.A.C. 11:2 (Claims/Insurance Group), 11:17 (Producer Licensing), and 11:17A
(Producer Standards of Conduct) all appeared in the single re-expansion call. Domain hints also surfaced
5 additional chapters: 11:16 (Fraud), 11:17B/C/D (Producer conduct sub-parts), 11:25 (Surplus Lines).
No duplicates of already-found chapters. NJ recall: **90% (27/30)** — up from 77% pre-ALGO-014 and 40%
pre-ALGO-013. Remaining 3 misses are cross-title statutes (39:6B, 2A:53A, 52:14B) anchored outside
NJDOBI scope — not engine failures.

**Files changed:**
- `backend/app/agent/prompts.py` — `DOMAIN_CHAPTER_HINTS`, `_derive_domain_key()`, `build_sibling_context()`, updated `build_expansion_prompt()` signature
- `backend/app/agent/graph_discovery.py` — `_expand_node()` sibling query + context injection, `src_meta` gains `id` and `type`

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
| V7 ALGO-012 | Insurance | TBD | 3 | TBD | TBD | TBD (target: 80%+) | TBD (target: <30 min) |
| V7.1 ALGO-013 | Insurance | Gemini Flash | 3 | ~68 entities | 1,005 sources | 40% pre-repair / TBD post | ~9 hrs (k=3 resumed) |
| V7.2 ALGO-014 | Insurance | Gemini Flash | 3 | — | +33 new NJ sources | 90% (27/30) — up from 77% | 1 LLM call (targeted) |

---

## Pending Algorithm Experiments

| ID | Hypothesis | Expected Impact |
|----|-----------|----------------|
| EXP-001 | Restore `complete_grounded()` for L2+ expansion only | +depth for obscure statutes, slower |
| EXP-002 | Parallel entity expansion (asyncio.gather N at a time) | -runtime 5-10x |
| EXP-003 | Source dedup by (name, entity_id) not prefixed ID | -5x source inflation |
| EXP-004 | Hybrid: grounded L1 (entity discovery) + parametric L2 (statute enum) | best of both |
| EXP-005 | Haiku for volume runs, Sonnet for NJ-targeted expansion | cost/quality balance |
