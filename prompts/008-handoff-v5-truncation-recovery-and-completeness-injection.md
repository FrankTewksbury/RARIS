---
type: handoff
created: 2026-03-03T11:00:00
sessionId: S20260303_0500
source: cursor-agent
description: V5 BFS engine sectors now complete without crashing. Two root causes fixed: (1) Gemini always truncates at "funding_streams":" leaving open arrays; (2) COMPLETENESS section was sending cross-sector noise to every sector. Both fixed, not yet verified by a clean run.
---

# Handoff — V5 Truncation Recovery + Sector Completeness Injection

## Session Summary

This session fixed two compounding problems preventing the V5 BFS engine from returning data:

1. **JSON truncation recovery** — Gemini always truncates at the last field `"funding_streams":` leaving open array brackets. The recovery logic was building invalid JSON.
2. **Cross-sector COMPLETENESS noise** — Every sector call received the global COMPLETENESS block listing all 6 sectors' requirements, confusing the model about its scope.
3. **Frontend SSE event mismatch** — The frontend was listening for V3 event names (`"step"`, `"progress"`) while V5 emits `"sector_start"`, `"sector_complete"`, etc. UI showed nothing.
4. **Constitution rule added** — "Never remove debug instrumentation without explicit user instruction" added to `agent-constitution.mdc` and `docs/DFW-CONSTITUTION.md`.

## Current State

### What Works
- All 6 sectors fire in parallel (AFC enabled, 64 searches each)
- Sectors complete without throwing (no more `Expecting value` crashes)
- Frontend SSE handler updated — sector events now display in Agent Progress panel
- Per-sector completeness requirements injected from `DPA_Sectors_v2.json`

### What Is NOT Yet Verified
- Last K=1 run before context cutoff had no test results — the rebuild happened just before Frank ran it
- **The next agent must run K=1 and confirm entities > 0 per sector from the logs**

## Root Cause Detail

### Truncation Pattern (confirmed from logs)

Every Gemini sector response ends with:
```
    }
  ],
  "funding_streams":
```
— a dangling key-colon at the very end, with `programs[` still open.

The old recovery built `partial + "\n}"` which produced:
```json
{ "programs": [ { ...last item } }   ← ] never closed = invalid
```

### Fix Applied (`backend/app/agent/discovery.py`)

Three-layer recovery in `_extract_json_object`:
1. Strip dangling `"key":` with no value via regex
2. Strip dangling `"key": "partial-string` with unclosed quote via regex  
3. Count unclosed `[` brackets outside strings via `_count_open_brackets()` and append the right number of `]` before `\n}`

Result:
```json
{ "administering_entities": [...], "programs": [...] }
```
Valid JSON, all real data preserved, `funding_streams` dropped (it was always empty anyway).

Also fixed: `_extract_json` line 136 was `return json.loads(text)` bare — no try/except. Changed to `try/except -> return {}`.

## Files Modified This Session (all uncommitted)

| File | Change |
|------|--------|
| `backend/app/agent/discovery.py` | `_count_open_brackets()` helper; `_extract_json_object` truncation recovery closes open arrays; `_extract_json` fallback wrapped in try/except |
| `backend/app/agent/graph_discovery.py` | Debug instrumentation restored as `logger.debug/warning`; `_build_completeness_block()` helper added; `_discover_sector` injects completeness block |
| `backend/app/agent/prompts.py` | `SECTOR_SCOPE_HEADER` updated with `{completeness_block}` placeholder |
| `backend/app/llm/gemini_provider.py` | Already committed in `e19bd57` |
| `frontend/src/hooks/useSSE.ts` | V5 SSE event listeners added (`sector_start`, `sector_complete`, `l1_assembly_complete`, `entity_expansion_start/complete`) |
| `frontend/src/components/AgentProgressPanel.tsx` | Rewritten for V5 event shapes — sector-by-sector progress display |
| `prompts/DPA_Prompt_v8.md` | New — v7 minus global COMPLETENESS block |
| `prompts/DPA_Sectors_v2.json` | New — v1 plus per-sector `completeness_requirements` arrays |
| `.cursor/rules/agent-constitution.mdc` | New rule: Never remove debug instrumentation without explicit instruction |
| `docs/DFW-CONSTITUTION.md` | Same rule added (twin sync) |

## What The Next Agent Must Do

### Step 1 — Run K=1 and verify entities

Containers are already running. In the UI at `http://localhost:5900`:
1. Upload `prompts/DPA_Prompt_v8.md` as Instruction
2. Upload `prompts/DPA_Sectors_v2.json` as Sector Config
3. Set K Depth = 1, enter a manifest name, click Generate

Expected result:
- All 6 sectors show `✓` (not `✗`)
- entities_found > 0 for most sectors (federal should find 5-10, state_hfa 3-5, municipal 5-15)
- `L1 complete — N entities, 0 sources across 6 sectors` with N > 10

Check logs:
```powershell
docker-compose logs backend --since=10m | Select-String "sector|entities|WARNING|ERROR|empty"
```

### Step 2 — If K=1 is clean, commit everything

```
git add backend/app/agent/discovery.py backend/app/agent/graph_discovery.py backend/app/agent/prompts.py frontend/src/hooks/useSSE.ts frontend/src/components/AgentProgressPanel.tsx prompts/DPA_Prompt_v8.md prompts/DPA_Sectors_v2.json .cursor/rules/agent-constitution.mdc docs/DFW-CONSTITUTION.md
```

Commit message:
```
fix(discovery): robust truncation recovery for Gemini open-array responses

- _count_open_brackets(): string-aware bracket counter
- _extract_json_object: close open arrays before root } on truncated response
- _extract_json: wrap fallback json.loads in try/except -> return {}
- graph_discovery: inject per-sector completeness block from sector file
- prompts.py: SECTOR_SCOPE_HEADER gains {completeness_block} placeholder
- frontend/useSSE: add V5 SSE event listeners (sector_start, sector_complete, etc.)
- AgentProgressPanel: rewrite for V5 event shapes
- DPA_Prompt_v8.md: remove cross-sector COMPLETENESS block
- DPA_Sectors_v2.json: per-sector completeness_requirements arrays
- constitution: never remove debug instrumentation without explicit user instruction
```

### Step 3 — Run K=2 for first full program population

Once K=1 is verified and committed, run K=2:
- Expected: entity_expansion events fire per L1 entity
- Expected: programs_count > 0 in manifest detail
- Expected runtime: 15-30 minutes

### Step 4 — Update `_ACTIVE_CONTEXT.md`

After a successful K=2 run, update `context/_ACTIVE_CONTEXT.md`:
- Mark V5 JSON parse fix as complete
- Add completeness injection as complete
- Next items: AuthorityType DB migration, K=2 verification, K=3 test

## Key Facts for Next Agent

- **The data IS good** — logs showed real programs with confidence 1.0, real URLs (calhfa.ca.gov, collegeparkpartnership.org, miamidade.gov) before the array-close bug swallowed them
- **Truncation at `"funding_streams":` is permanent Gemini behavior** — the recovery is the right fix; do not try to remove `funding_streams` from the schema, just let recovery handle it
- **RECITATION blocks** (municipal sector in first run) are Gemini content policy, not bugs. They produce empty results gracefully. Acceptable.
- **Log level is INFO** — `logger.debug` calls in `graph_discovery.py` are invisible in production logs. To see raw response tails, temporarily set `LOG_LEVEL=DEBUG` in `.env` or check the `logger.warning` empty-result messages which always show the tail.
- Containers run on ports: frontend=5900, backend=5901, db=5902, redis=5903
- All 311 tests still pass (the changes are backward-compatible)
