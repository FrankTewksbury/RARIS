---
type: doc
created: 2026-03-02T02:00:00
sessionId: S20260302_0200
source: cursor-agent
description: Base contract between instruction prompts and the V4 discovery engine — 7 required sections, 4 forbidden sections
---

# Base Instruction Template — Discovery Engine Contract

This document defines the **required structure** for all domain instruction prompts used with the V4 prompt-driven discovery engine.

Every instruction prompt uploaded to the engine MUST conform to this template. The engine passes the instruction prompt directly as the L0 user message without modification. The template enforces that the prompt contains domain knowledge, not execution logic.

---

## How the Engine Uses This Prompt

- **L0** — The full instruction prompt text becomes the user message. The engine wraps it with only a thin JSON output schema. The LLM uses web search grounding and the domain methodology here to perform comprehensive initial discovery.
- **L1-L3** — The engine builds its own data-driven prompts from L0 output. The instruction prompt is NOT used again after L0.

---

## Required Sections (every prompt MUST include all 7)

### Section 1 — Domain Definition

What is being discovered? Define the entity types, program types, and source types that exist in this domain. Include the agent persona if relevant to discovery quality.

- What administering entities exist and how are they structured?
- What types of programs, products, or instruments does this domain contain?
- What types of source documents are authoritative in this domain?

### Section 2 — Coverage Scope

Who administers these programs/entities? What entity types must be searched? This section drives the **breadth** of L0 discovery.

- List every administering entity category (e.g., federal agencies, state agencies, municipal departments, nonprofits, employers, tribal authorities)
- For each category, indicate priority (primary / secondary / contextual)
- List specific sub-categories where known (e.g., "Community Development departments" within municipal)

### Section 3 — Taxonomy / Classification

How to classify discovered items. This drives deduplication, coverage assessment, and gap analysis.

- Program type taxonomy (multi-label if appropriate)
- Classification rules (e.g., "do not collapse X and Y")
- Entity type taxonomy

### Section 4 — Search Vocabulary / Lexicon

Domain-specific terms, synonyms, and search keywords. This improves web search recall.

- Assistance/product terms (what programs are called)
- Administering entity signals (what to search to find these orgs)
- Segment signals (targeted beneficiary terms)
- Query templates (example search strings using `<PLACEHOLDER>` notation)

### Section 5 — Evidence Requirements

What constitutes a valid discovery? What is the minimum required to include an item?

- Minimum required fields per entity/program/source
- Confidence criteria (when to mark `verified` vs `candidate_only` vs `needs_human_review`)
- Prequalification rules (what disqualifies an item)
- Behavioral guardrails (do-not-do rules)

### Section 6 — Quality Gates

What coverage targets must be met? What gaps are unacceptable? This drives L3 gap analysis.

- Category coverage targets (e.g., "municipal entries should be the majority")
- Seed recovery expectations
- Sector completeness requirements (non-trivial counts per entity type)
- Monitoring readiness requirements

### Section 7 — Output Schema

The JSON schema the engine expects in the LLM response. This is the contract — the engine parses this exact structure.

Instruction prompts MUST align their output schema to the engine's data models:

```json
{
  "regulatory_bodies": [
    {
      "id": "short-kebab-case-id",
      "name": "Full Official Name",
      "jurisdiction": "federal|state|municipal",
      "authority_type": "regulator|gse|sro|industry_body",
      "url": "https://verified-official-website",
      "governs": ["area1", "area2"]
    }
  ],
  "sources": [
    {
      "id": "src-NNN",
      "name": "Document or page name",
      "regulatory_body": "body-id",
      "type": "statute|regulation|guidance|standard|educational|guide",
      "format": "html|pdf|legal_xml|api|structured_data",
      "authority": "binding|advisory|informational",
      "jurisdiction": "federal|state|municipal",
      "url": "https://verified-url",
      "access_method": "scrape|download|api|manual",
      "confidence": 0.0,
      "needs_human_review": false,
      "verification_state": "verified|candidate_only|verification_pending"
    }
  ],
  "programs": [
    {
      "name": "Program Name",
      "administering_entity": "Entity Name",
      "geo_scope": "national|state|county|city|tribal",
      "jurisdiction": "optional jurisdiction text",
      "benefits": "optional summary",
      "eligibility": "optional summary",
      "status": "active|paused|closed|verification_pending",
      "evidence_snippet": "quoted text from web source",
      "source_urls": ["https://verified-url"],
      "provenance_links": {
        "source_ids": [],
        "discovery_level": "L0"
      },
      "confidence": 0.0,
      "needs_human_review": false
    }
  ],
  "jurisdiction_hierarchy": {
    "federal": {"bodies": [], "count": 0},
    "state": {"bodies": [], "count": 0},
    "municipal": {"bodies": [], "count": 0}
  }
}
```

**Confidence scoring rules:**
- `>= 0.8` — verified via official source, direct URL confirmed
- `0.5–0.79` — plausible, primary source not directly confirmed
- `< 0.5` — candidate only; set `needs_human_review: true` and `verification_state: candidate_only`

---

## Forbidden Sections (do NOT include in instruction prompts)

The engine handles these internally. Including them in the instruction prompt creates conflicts:

| Forbidden | Reason |
|-----------|--------|
| Execution phases (L0/L1/L2/L3 steps) | Engine orchestrates levels; prompt should not describe phases |
| Search strategy mechanics (how to ground, retry, batch) | Engine calls `complete_grounded()` — this is infrastructure |
| Seed reconciliation logic (pass A/B/C/D/E) | Engine handles seed matching in code |
| PDF traversal / portal fingerprinting steps | Engine handles these as L1-L2 data-driven expansion |

---

## Validation Checklist

Before submitting an instruction prompt, verify:

- [ ] Section 1 defines domain, entity types, and source types
- [ ] Section 2 lists all administering entity categories with priority
- [ ] Section 3 provides a complete program/entity taxonomy
- [ ] Section 4 includes domain-specific search terms and query templates
- [ ] Section 5 defines confidence criteria and behavioral guardrails
- [ ] Section 6 defines measurable coverage targets
- [ ] Section 7 output schema is aligned to engine models
- [ ] No execution phases, search mechanics, seed pass logic, or PDF traversal instructions
- [ ] Target length: 120–200 lines (dense with domain knowledge, not execution steps)
