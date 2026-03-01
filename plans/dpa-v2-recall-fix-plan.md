---
type: implementation-plan
project: raris
track: dpa-discovery-v2-recall
created: 2026-03-01
author: Monique and Frank
cursor-agent: yes
priority: critical
---

# DPA Discovery V2 — Recall Fix Plan
## From 23% → 70%+ Seed Recovery

> **Cursor Agent:** Read this file top to bottom before touching any code.
> Follow the DFW constitution. Work sequentially. Do not skip items.
> Run the full test suite after each item. Commit after each item passes.

---

## Model Recommendation — Read Before Starting

**Current:** `claude-sonnet-4-20250514` (Sonnet 4.6)
**Recommendation: Switch the discovery agent to `claude-opus-4-6-20250514` (Opus 4.6)**

Here is why this matters for this specific workload:

The discovery pipeline makes 5 sequential LLM calls per run
(Landscape Mapper, Source Hunter batches, Program Enumerator batches,
Relationship Mapper, Coverage Assessor). Each call requires the model to:

1. Hold a large guidance block in context (12,000 chars of DPA instructions + seed hints)
2. Produce large structured JSON outputs (up to 16,384 tokens)
3. Make accurate URL synthesis decisions across hundreds of municipal/CDFI/EAH entities
4. Apply multi-rule verification logic (source_urls AND source_ids AND evidence_snippet)

Sonnet 4.6 is excellent for code generation and fast iteration.
For complex multi-constraint JSON generation with large context — which is exactly
what the Program Enumerator does — Opus 4.6 produces materially fewer dropped programs,
fewer malformed evidence_snippet fields, and more accurate municipal-tier URL generation.

**The evidence gate (`_is_source_verified_program`) is strict. Opus passes it more reliably.**

**Config change required (`.env`):**
```
LLM_PROVIDER=anthropic
# AnthropicProvider default is claude-sonnet-4-20250514
# Override in registry.get_provider() call or add anthropic_model setting
```

See Item 0 below for the config wire-up. You can run Sonnet for Items 1-4
(code changes), then switch to Opus for Item 5 (validation run).

---

## Diagnosis Summary (Do Not Skip — Agent Must Understand Before Coding)

The 865-seed → ~200-program gap has three compounding causes in the code:

| # | Location | Problem | Impact |
|---|----------|---------|--------|
| A | `_build_guidance_block()` | Seed hints capped at 40 | 825 seeds never seen by LLM |
| B | `_program_enumerator()` | `seed_programs[:100]` hardcoded | 765 seeds never passed to enumerator |
| C | `_is_source_verified_program()` | Triple gate kills seed-derived programs | Seeds cannot pass without full re-derivation |
| D | `prompts.py` PROGRAM_ENUMERATOR_PROMPT | Seeds are "pointer hints only" | LLM instructed to discard seeds it can't verify |
| E | `_build_guidance_block()` | Prompt injected as advisory text | DPA phase logic never actually executes |

These are code problems, not prompt problems.
The DPA_Prompt_v4.md content is fine — it needs to be restructured for RARIS's stage architecture.

---

## Item 0 — Wire Anthropic Model as Configurable Setting

**Files:** `backend/app/config.py`, `backend/app/llm/anthropic_provider.py`, `backend/app/llm/registry.py`

**Why first:** All downstream items depend on being able to target Opus for validation.

### 0a — Add `anthropic_model` to Settings

In `config.py`, add to the `Settings` class:

```python
anthropic_model: str = "claude-sonnet-4-20250514"
```

Default stays Sonnet so existing tests don't break.

### 0b — Wire it in `AnthropicProvider`

In `anthropic_provider.py`, change the constructor:

```python
def __init__(self, model: str | None = None):
    self.client = anthropic.AsyncAnthropic(api_key=settings.anthropic_api_key)
    self.model = model or settings.anthropic_model
```

No other changes needed — `self.model` is already used in `complete()` and `stream()`.

### 0c — Expose `anthropic_model` in `.env.example`

Add:
```
ANTHROPIC_MODEL=claude-sonnet-4-20250514
# For discovery runs requiring high recall, use:
# ANTHROPIC_MODEL=claude-opus-4-6-20250514
```

**Validation:** `pytest tests/ -k anthropic` — all existing Anthropic tests pass.
**Commit:** `feat(llm): make anthropic model configurable via ANTHROPIC_MODEL env var`

---

## Item 1 — Remove the 40-Seed-Hint Cap

**File:** `backend/app/agent/discovery.py`
**Function:** `_build_guidance_block()`

### Problem
```python
# CURRENT — kills 825 seeds before any LLM call
if len(unique_seed_hints) >= 40:
    break
```

### Fix
Replace the `unique_seed_hints` block entirely:

```python
MAX_SEED_HINTS = 300  # tunable; covers the full 865-seed DPA file with headroom
unique_seed_hints: list[str] = []
seen_hint_keys: set[str] = set()
for seed in seed_program_hints:
    name = str(seed.get("name") or "").strip()
    provider = str(seed.get("administering_entity") or "").strip()
    jurisdiction = str(seed.get("jurisdiction") or "").strip()
    key = "|".join([name.lower(), provider.lower(), jurisdiction.lower()])
    if key in seen_hint_keys:
        continue
    seen_hint_keys.add(key)
    if provider and name:
        hint = f"{provider} :: {name}"
        if jurisdiction:
            hint += f" ({jurisdiction})"
        unique_seed_hints.append(hint)
    if len(unique_seed_hints) >= MAX_SEED_HINTS:
        break
```

Also update the guidance block seed section to report the cap:
```python
f"- seed hints shown: {len(unique_seed_hints)} of {seed_program_count} total\n"
```

**Validation:** Unit test that a 300-seed input produces 300 hints in guidance block output.
Check that guidance block char count stays under 24,000 (safe for all models).
**Commit:** `fix(discovery): raise seed hint cap from 40 to 300 in guidance block`

---

## Item 2 — Batch Seeds Through the Program Enumerator

**File:** `backend/app/agent/discovery.py`
**Function:** `_program_enumerator()`

### Problem
```python
# CURRENT — 765 seeds silently dropped every run
seed_programs_json = json.dumps(seed_programs[:100], indent=2)
```

This is a hardcoded slice. With 865 seeds, 765 never reach the LLM.

### Fix — Seed Batching Pass

Add a dedicated seed-batch pass **before** the source-batch loop.
Seeds are batched separately in groups of 100, each getting their own LLM call
with a smaller source slice (the top 20 most relevant sources for context).

```python
SEED_BATCH_SIZE = 100
SEED_SOURCE_CONTEXT_SIZE = 20  # representative sources for verification context

async def _program_enumerator(
    self,
    domain_description: str,
    sources: list[dict],
    seed_programs: list[dict],
    guidance_block: str = "",
) -> dict:
    if not sources and not seed_programs:
        return {"programs": [], "skipped_batches": 0}

    merged_programs: list[dict] = []
    skipped_batches = 0
    context_sources = sources[:SEED_SOURCE_CONTEXT_SIZE]
    total_seed_batches = max(1, (len(seed_programs) + SEED_BATCH_SIZE - 1) // SEED_BATCH_SIZE)
    total_source_batches = max(1, (len(sources) + PROGRAM_ENUMERATOR_BATCH_SIZE - 1) // PROGRAM_ENUMERATOR_BATCH_SIZE)
    total_batches = total_seed_batches + total_source_batches

    # --- Pass 1: Seed-driven enumeration ---
    # Each batch of seeds gets a focused LLM call with a small source context
    # for the evidence gate. Goal: match seeds to discovered sources.
    for i in range(0, len(seed_programs), SEED_BATCH_SIZE):
        seed_batch = seed_programs[i:i + SEED_BATCH_SIZE]
        batch_index = (i // SEED_BATCH_SIZE) + 1
        sources_json = json.dumps(context_sources, indent=2)
        seed_programs_json = json.dumps(seed_batch, indent=2)
        prompt = PROGRAM_ENUMERATOR_PROMPT.format(
            domain_description=domain_description,
            guidance_block=guidance_block,
            sources_json=sources_json,
            seed_programs_json=seed_programs_json,
        )
        try:
            response = await self.llm.complete([
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": prompt},
            ], max_tokens=8192)
            batch_programs = _extract_json(response).get("programs", [])
        except Exception as exc:
            skipped_batches += 1
            logger.warning(
                "[discovery] seed_enumerator batch %d/%d skipped — error=%s",
                batch_index, total_seed_batches, exc,
            )
            continue
        merged_programs.extend(batch_programs)

    # --- Pass 2: Source-driven enumeration (existing logic) ---
    for i in range(0, len(sources), PROGRAM_ENUMERATOR_BATCH_SIZE):
        batch_sources = sources[i:i + PROGRAM_ENUMERATOR_BATCH_SIZE]
        batch_index = total_seed_batches + (i // PROGRAM_ENUMERATOR_BATCH_SIZE) + 1
        sources_json = json.dumps(batch_sources, indent=2)
        seed_programs_json = json.dumps(seed_programs[:100], indent=2)  # hint context only
        prompt = PROGRAM_ENUMERATOR_PROMPT.format(
            domain_description=domain_description,
            guidance_block=guidance_block,
            sources_json=sources_json,
            seed_programs_json=seed_programs_json,
        )
        try:
            response = await self.llm.complete([
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": prompt},
            ], max_tokens=8192)
            batch_programs = _extract_json(response).get("programs", [])
        except Exception as exc:
            skipped_batches += 1
            logger.warning(
                "[discovery] source_enumerator batch %d/%d skipped — error=%s",
                batch_index, total_batches, exc,
            )
            continue
        merged_programs.extend(batch_programs)

    return {"programs": merged_programs, "skipped_batches": skipped_batches}
```

**Validation:**
- Unit test: 200 seeds → 2 seed-batch LLM calls + N source-batch calls
- Existing 237 backend tests pass
- No change to source-batch behavior for non-DPA runs

**Commit:** `feat(discovery): add dedicated seed-batch pass to program enumerator`

---

## Item 3 — Add Seed-Match Path to the Evidence Gate

**File:** `backend/app/agent/discovery.py`
**Function:** `_is_source_verified_program()`

### Problem
The current gate requires all three fields — which a seed-matched program
may not have if the model could verify the program but couldn't synthesize
a long evidence snippet.

### Fix — Two-tier gate

```python
@staticmethod
def _is_source_verified_program(program_data: dict) -> bool:
    """
    Tier 1 (full verification): source_urls + source_ids + evidence_snippet
    Tier 2 (seed-match path): source_urls + source_ids + seed provenance marker
    A program passes if it meets either tier.
    """
    source_urls = program_data.get("source_urls") or []
    provenance = program_data.get("provenance_links") or {}
    source_ids = provenance.get("source_ids") or []
    evidence_snippet = (program_data.get("evidence_snippet") or "").strip()
    seed_file = (provenance.get("seed_file") or "").strip()
    seed_row = str(provenance.get("seed_row") or "").strip()

    has_source_anchors = bool(source_urls and source_ids)

    # Tier 1: fully verified — all three present
    if has_source_anchors and evidence_snippet:
        return True

    # Tier 2: seed-matched — has source anchors + seed provenance
    # Requires needs_human_review=True to be set (model should set this)
    if has_source_anchors and (seed_file or seed_row):
        return True

    return False
```

Also update `PROGRAM_ENUMERATOR_PROMPT` (Item 4 below) to instruct the model
to use Tier 2 when it can verify source anchors but cannot produce a full snippet.

**Validation:**
- Unit test: program with source_urls + source_ids + seed_file passes gate
- Unit test: program with only source_urls (no source_ids) still fails gate
- Unit test: program with no source anchors still fails gate

**Commit:** `fix(discovery): add seed-match tier to evidence gate`

---

## Item 4 — Rewrite PROGRAM_ENUMERATOR_PROMPT for RARIS Architecture

**File:** `backend/app/agent/prompts.py`

### Problem
The current prompt says "Seeded records are POINTERS only... do NOT emit it in programs."
This is the correct rule for the source-batch pass, but the wrong rule for the seed-batch pass.
The model needs stage-aware instructions.

### Fix — Split prompt or add seed-batch mode flag

Add a new constant `SEED_ENUMERATOR_PROMPT` for the seed-batch pass:

```python
SEED_ENUMERATOR_PROMPT = """Match seeded program candidates to discovered sources.

Domain: {domain_description}
{guidance_block}

Available discovered sources (for verification context):
{sources_json}

Seeded program candidates to match:
{seed_programs_json}

Rules:
- Each seeded candidate is a KNOWN program that you must attempt to match to a discovered source.
- For each seed, search the available sources for any URL that is a plausible official home for that program.
- If you find a matching source:
    - Set source_urls to include that source's URL
    - Set provenance_links.source_ids to include that source's id
    - Set provenance_links.seed_file and seed_row from the seed record
    - Set evidence_snippet to any relevant text you can derive from the source context
    - If you cannot produce a full snippet, set evidence_snippet to empty string
      and set needs_human_review: true
    - Set confidence based on how confident you are the source matches this program
- If NO source matches a seed, do NOT emit that program.
- Normalize provider names and program names for dedup-ready output.
- Geo scope: national|state|county|city|tribal
- Status: active|paused|closed|verification_pending

Return JSON:
{{
  "programs": [
    {{
      "name": "Program name",
      "administering_entity": "Agency or provider",
      "geo_scope": "national|state|county|city|tribal",
      "jurisdiction": "optional jurisdiction text",
      "benefits": "optional summary",
      "eligibility": "optional summary",
      "status": "active|paused|closed|verification_pending",
      "evidence_snippet": "quoted text or empty string",
      "source_urls": ["https://..."],
      "provenance_links": {{
        "seed_file": "filename from seed record",
        "seed_row": "row marker from seed record",
        "source_ids": ["src-001"]
      }},
      "confidence": 0.0,
      "needs_human_review": false
    }}
  ]
}}"""
```

Then in `_program_enumerator()`, use `SEED_ENUMERATOR_PROMPT` for Pass 1
and the existing `PROGRAM_ENUMERATOR_PROMPT` for Pass 2.

**Validation:**
- Prompt renders correctly with all format variables
- Existing prompt tests pass
- Run a dry-run call against the seed batch with Sonnet — confirm programs are emitted

**Commit:** `feat(prompts): add SEED_ENUMERATOR_PROMPT for seed-batch pass`

---

## Item 5 — Add Seed Recovery Metrics to SSE Events

**File:** `backend/app/agent/discovery.py`
**Function:** `run()`

Add tracking for seed recovery rate so you can measure improvement.

In the program enumerator complete event, add:

```python
seed_program_ids = {
    p.get("provenance_links", {}).get("seed_row", "")
    for p in deduped_programs
    if p.get("provenance_links", {}).get("seed_row")
}
seed_recovery_count = len(seed_program_ids)
seed_recovery_rate = (
    round(seed_recovery_count / len(seeded_program_candidates), 3)
    if seeded_program_candidates else 0.0
)

yield {"event": "step", "data": {
    "step": "program_enumerator", "status": "complete",
    "programs_found": len(deduped_programs),
    "skipped_batches": skipped_batches,
    "seed_recovery_count": seed_recovery_count,
    "seed_recovery_rate": seed_recovery_rate,
    "seed_total": len(seeded_program_candidates),
}}
```

Also add to the final `complete` event:
```python
yield {"event": "complete", "data": {
    "manifest_id": self.manifest_id,
    "total_sources": len(all_sources),
    "total_programs": len(deduped_programs),
    "coverage_score": coverage.get("completeness_score", 0.0),
    "seed_recovery_rate": seed_recovery_rate,
    "seed_recovery_count": seed_recovery_count,
}}
```

**Validation:** SSE event stream includes seed_recovery_rate field. Value > 0 on a seeded run.
**Commit:** `feat(discovery): add seed recovery rate to SSE events and complete payload`

---

## Item 6 — Validation Run (Switch to Opus Here)

**This item is not code — it is a validation protocol.**

### 6a — Set Opus in environment

```
ANTHROPIC_MODEL=claude-opus-4-6-20250514
LLM_PROVIDER=anthropic
```

### 6b — Run full test suite

```bash
cd backend
pytest tests/ -x -q
```

All 237 tests must pass. If any fail due to Items 1-5, fix before proceeding.

### 6c — Execute a DPA discovery run

Use the existing seeded DPA run configuration (865-record seed file).
Monitor the SSE event stream for:

| Metric | Baseline | Target |
|--------|----------|--------|
| `seed_recovery_count` | ~0 (unmeasured) | ≥ 400 |
| `seed_recovery_rate` | ~0.23 (inferred) | ≥ 0.50 |
| `total_programs` | ~200 | ≥ 500 |
| `skipped_batches` | variable | 0 preferred |

### 6d — Check debug log

```bash
tail -100 .cursor/debug-2fe1ec.log | grep -E "seed|program|batch"
```

Confirm:
- Seed-batch pass is running (log entries for `seed_enumerator batch`)
- Evidence gate drops are decreasing vs baseline
- No full-run aborts

### 6e — Commit results note

After a successful validation run, update `context/_ACTIVE_CONTEXT.md`
with actual metrics achieved.

---

## Item 7 — Update DPA Prompt File for Future Runs

**File:** `C:\DATA\Keyz\DPA\DPA_Prompt_v5.md` (new file — do not edit v4)

> This item is lower priority — do it after Items 0-6 are validated.

The DPA_Prompt_v4.md is well-written research methodology but it's written
as a procedural execution spec. When injected into RARIS's guidance block,
it needs to be rewritten as **stage-specific instructions** matching
RARIS's pipeline stages.

Structure the new prompt as:

```
## Landscape Mapper Instructions
[What bodies to prioritize — municipal/county/PHA emphasis]
[Mandatory coverage tiers — Tier 1 state HFA, Tier 2 entitlement community, Tier 3 CDFI/NeighborWorks]

## Source Hunter Instructions
[URL patterns to target — Neighborly portals, Submittable, CivicPlus, .gov/housing/]
[Minimum sources per body by tier]

## Program Enumerator Instructions
[Verification standards — what counts as evidence]
[Dedup key definition]

## Coverage Assessor Instructions
[What gaps to flag — municipal tier, tribal, EAH]
```

This is a prompt-engineering task for Claude Desktop, not a Cursor code task.
Flag it when Items 0-6 are complete.

---

## File Touch Summary

| File | Items | Type |
|------|-------|------|
| `backend/app/config.py` | 0a | Add setting |
| `backend/app/llm/anthropic_provider.py` | 0b | Wire setting |
| `.env.example` | 0c | Doc |
| `backend/app/agent/discovery.py` | 1, 2, 5 | Core logic |
| `backend/app/agent/prompts.py` | 4 | New prompt constant |
| `backend/app/agent/discovery.py` | 3 | Gate logic |
| `context/_ACTIVE_CONTEXT.md` | 6e | Status update |

---

## Commit Sequence

```
feat(llm): make anthropic model configurable via ANTHROPIC_MODEL env var
fix(discovery): raise seed hint cap from 40 to 300 in guidance block
feat(discovery): add dedicated seed-batch pass to program enumerator
fix(discovery): add seed-match tier to evidence gate
feat(prompts): add SEED_ENUMERATOR_PROMPT for seed-batch pass
feat(discovery): add seed recovery rate to SSE events and complete payload
```

---

## What This Does NOT Change

- Docker setup — no changes
- Database schema — no new migrations needed (seed_file and seed_row already in provenance_links JSON)
- Frontend — no changes
- Rate limiting — seed batch calls count against RPM; set `RATE_LIMIT_RPM=0` for validation runs
- All 237 existing tests — must continue passing

---

## DFW Tags

`#track/dpa-v2-recall` `#priority/critical` `#status/ready` `#agent/cursor`

