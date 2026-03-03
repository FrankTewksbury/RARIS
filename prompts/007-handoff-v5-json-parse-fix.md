---
type: handoff
created: 2026-03-03T00:50:00
sessionId: S20260303_0050
source: cursor-agent
description: V5 BFS engine is running and finding real data — blocked only by JSON parse failure on truncated Gemini responses. Two fixes are coded and uncommitted. Ready to rebuild, verify, and commit.
---

# Handoff — V5 JSON Parse Fix + Verification

## Current State

The V5 BFS engine is **fully functional** and Gemini is finding real, high-quality data:
- Texas HFAs (TDHCA, TSAHC, SETH), Johns Hopkins EAH, tribal housing authorities, municipal DPA programs — all discovered correctly
- **All 6 sector calls fire in parallel**, run for 2-4 minutes each doing 64 real web searches
- **The only failure**: every sector's JSON response is truncated at `"next_actions":` (the last field in `queue_state`) and the JSON parser crashes

## Root Cause (100% confirmed via runtime logs at `x:\RARIS\.cursor\debug-b3299f.log`)

1. **Gemini truncates every response at `"next_actions":`** — the last field in `queue_state` at the bottom of the output schema. The response ends mid-object with no closing brackets.

2. **`_extract_json` can't recover** from this truncation. The brace-balanced extractor finds `"next_actions":` with no value and can't produce valid JSON.

3. **Some sectors wrap in markdown fences** (` ```json `) which the original regex handled, but when the fence is never closed (also due to truncation), the regex doesn't match and `json.loads(text)` fails on the backtick.

4. **`max_tokens=32768` was not wired** to Gemini's `max_output_tokens` — fixed already.

## Fixes Already Applied (uncommitted, not yet rebuilt)

### Fix 1 — `backend/app/agent/discovery.py` — `_extract_json` + `_extract_json_object`

Replaced `_extract_json` with a robust 3-strategy extractor:
- Strategy 1a: Complete markdown fence (` ```json ... ``` `)
- Strategy 1b: **Opened fence with no closing ` ``` `** (truncated) — falls through to brace extraction on inner content
- Strategy 2: Brace-balanced extraction with **truncation recovery** — when depth never returns to 0, strips trailing incomplete field and closes root object with `}`
- Strategy 3: Direct `json.loads` fallback

The truncation recovery in `_extract_json_object`:
```python
# When text ends with "next_actions": (no value, no closing braces)
# last_valid_close points to the } that closed the previous top-level item
partial = text[start:last_valid_close + 1]
partial = partial.rstrip().rstrip(",")
candidate = partial + "\n}"   # close the root object
return json.loads(candidate)
```

### Fix 2 — `prompts/DPA_Prompt_v7.md` — Remove `queue_state` from output schema

Removed `queue_state` / `next_actions` entirely from the OUTPUT FORMAT section. The engine drives BFS traversal — the model never needs to emit queue state. This prevents truncation at that field in future runs.

Before:
```json
  "funding_streams": [],
  "queue_state": {
    "visited_entities": [],
    "visited_sources": [],
    "next_actions": []
  }
}
```

After:
```json
  "funding_streams": []
}
```

### Fix 3 — `backend/app/llm/gemini_provider.py` — Wire `max_tokens` to `max_output_tokens`

```python
if "max_tokens" in kwargs:
    config.max_output_tokens = int(kwargs["max_tokens"])
```

Also added fallback text extraction when `response.text` returns `None` (thinking-only responses).

## Debug Instrumentation Still In Code

`graph_discovery.py` has active instrumentation writing to `/workspace/.cursor/debug-b3299f.log`. **Remove before final commit:**

```python
# In _discover_sector, remove these two #region blocks:
# 1. "prompt assembled" log (after prompt = sector_header + instruction_text)
# 2. "raw LLM response" + "JSON parse failed" log (wrapping _extract_json call)
```

The `try/except` wrapper around `_extract_json(text)` — also added by instrumentation — **must stay** because it's now the correct call pattern. Just remove the log lines inside it, but keep `result = _extract_json(text)` inside the try block... actually, revert to a clean call: `result = _extract_json(text)` without try/except since `_extract_json` now returns `{}` on failure rather than raising.

## What the Next Agent Must Do

### Step 1 — Clean up instrumentation in `graph_discovery.py`

Remove the two `#region agent log` blocks from `_discover_sector`. After cleanup, `_discover_sector` should look like:

```python
async def _discover_sector(self, sector, instruction_text, sector_n, sector_total):
    search_hints = sector.get("search_hints", [])
    if search_hints:
        hints_block = "\n## Suggested search queries for this sector:\n" + "\n".join(
            f"  - {hint}" for hint in search_hints
        ) + "\n"
    else:
        hints_block = ""

    sector_header = SECTOR_SCOPE_HEADER.format(
        sector_label=sector["label"],
        sector_n=sector_n,
        sector_total=sector_total,
        search_hints_block=hints_block,
    )
    prompt = sector_header + instruction_text

    text, _citations = await asyncio.wait_for(
        self.llm.complete_grounded([
            {"role": "system", "content": L0_ORCHESTRATOR_SYSTEM},
            {"role": "user", "content": prompt},
        ], max_tokens=32768),
        timeout=300.0,
    )
    result = _extract_json(text)

    for entity in result.get("administering_entities", []):
        entity.setdefault("sector_key", sector["key"])

    return result
```

### Step 2 — Rebuild and run

```powershell
cd C:\DATA\RARIS
docker-compose up --build -d
```

Wait for all containers healthy, then run a test:
- Upload `prompts/DPA_Prompt_v7.md` as Instruction
- Upload `prompts/DPA_Sectors_v1.json` as Sector Config  
- K Depth = 1
- Watch backend logs: you should see sectors **not** failing this time

### Step 3 — Verify entities are persisted

After the run completes, check the manifest in the UI — it should show entities_found > 0 per sector. The manifest detail page should show RegulatoryBody records.

Also check backend logs for no `sector failed` warnings:
```powershell
docker-compose logs backend --since=10m | Select-String "sector|WARNING|ERROR"
```

### Step 4 — Commit the fixes

Once verified working:
```
git add backend/app/agent/discovery.py backend/app/llm/gemini_provider.py prompts/DPA_Prompt_v7.md
git commit -m "fix(discovery): recover from truncated Gemini JSON responses

- _extract_json: add truncation recovery — strips trailing incomplete
  field, closes root object, returns partial but valid result
- _extract_json: handle opened-but-unclosed markdown fences
- gemini_provider: wire max_tokens kwarg to max_output_tokens
- gemini_provider: fallback text extraction when response.text=None
- DPA_Prompt_v7: remove queue_state/next_actions from output schema
  (engine drives BFS — model never needs to emit queue state)"
```

### Step 5 — Run K Depth = 2 for first full test

Once K=1 works, run K=2:
- Expected: 6 sector_complete events → l1_assembly_complete → entity_expansion events → complete
- Expected: programs_count > 0 in manifest

## Files Modified (uncommitted)

| File | Change |
|------|--------|
| `backend/app/agent/discovery.py` | `_extract_json` + `_extract_json_object` — truncation recovery |
| `backend/app/agent/graph_discovery.py` | Debug instrumentation (REMOVE before commit) |
| `backend/app/llm/gemini_provider.py` | `max_tokens` → `max_output_tokens`; fallback text extraction |
| `prompts/DPA_Prompt_v7.md` | Removed `queue_state` from output schema |

## Key Facts for New Agent

- **The data is good** — Gemini is finding real programs. This is purely a parse problem.
- **No schema changes needed** — `administering_entities[]` maps correctly to `RegulatoryBody` model
- **`queue_state` was the only structural issue** — once removed from prompt, responses will end cleanly with `"funding_streams": []\n}`
- **The truncation recovery in `_extract_json_object`** is a safety net for any future truncation — keep it even after `queue_state` is removed
- All 311 tests still pass (the fix is backward-compatible — `_extract_json({})` returns `{}` instead of raising)
- Containers are currently stopped (`docker-compose down` was run)
- Debug log at `x:\RARIS\.cursor\debug-b3299f.log` can be deleted before new run
