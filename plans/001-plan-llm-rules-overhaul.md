---
type: plan
created: 2026-03-01T18:00:00
sessionId: S20260301_1800
source: cursor-agent
description: Overhaul all LLM Cursor rules to be vendor-grounded with web search sections
---

# LLM Cursor Rules Overhaul

## Goal

Rewrite all LLM Cursor rules so every model ID, SDK pattern, and capability section is grounded in verified March 2026 vendor documentation. Add web search / grounding as a mandatory section in every rule. Create the missing Anthropic rule.

## Constraints

- All model IDs verified against vendor documentation (web searches, March 2026)
- No LLM training data assumptions
- Rules are `alwaysApply: false` (agent-requestable)
- Consistent 7-section structure across all three rules
- DFW sequencing: `NNN-type-slug.md` pattern

## Implementation Steps

### Completed

- [x] **Gemini rule** (`gemini-model-rules.mdc`): Corrected Flash model ID from `gemini-3.1-flash-preview` to `gemini-3-flash-preview`, fixed broken markdown (unclosed code fences from section 2.2 onward), added Section 3 (Web Grounding with Google Search) with `google_search` tool pattern and `grounding_metadata` access, removed chatbot artifact at end of file, updated fallback chain to use correct model IDs
- [x] **OpenAI rule** (`openai-model-rules.mdc`): Added Section 3 (Web Search via Responses API) with `web_search` tool, domain filtering, user location, search types table, added reasoning modes documentation (`none`, `low`, `high`), removed `name:` from frontmatter, removed `gpt-5.2-codex` (unverified), added `gpt-5-mini`
- [x] **Anthropic rule** (`anthropic-model-rules.mdc`): Created from scratch with model table (Opus 4.6, Sonnet 4.6, Haiku 4.5), Messages API pattern with system message extraction, web search tool (`web_search_20260209`) with dynamic filtering, extended thinking (standard + adaptive for Opus 4.6), structured outputs (`output_config.format`), full error handling with exception types and retry pattern

## Files Created/Updated

- `UPDATE` — `.cursor/rules/gemini-model-rules.mdc`
- `UPDATE` — `.cursor/rules/openai-model-rules.mdc`
- `CREATE` — `.cursor/rules/anthropic-model-rules.mdc`

## Deferred — Downstream Code Fixes (Rules Only, Per User)

These code changes are required to align the application code with the corrected rules but were explicitly deferred:

- `backend/app/llm/gemini_provider.py` line 49: Change `gemini-3.1-flash-preview` to `gemini-3-flash-preview` in hardcoded safety net
- `backend/app/config.py`: Change `gemini_fallback_models` default to use `gemini-3-flash-preview`
- `.env.example`: Correct the fallback model ID
- `backend/app/llm/openai_provider.py` line 10: Change default from `gpt-4o` to `gpt-5.2-pro`

## Validation

- Each rule's model IDs match vendor documentation
- Each rule has a Web Search / Grounding section with working code examples
- All three rules follow the same 7-section structure
- No references to deprecated or non-existent model IDs
- Markdown renders correctly (no broken code fences, no chatbot artifacts)
