---
type: note
created: 2026-03-11T19:00:00
sessionId: S20260311_1600
source: cursor-agent
description: Post-run citation normalization — batch LLM lookup to resolve official citation identifiers for legacy source rows
---

# Citation Normalization — Post-Run Cleanup Note

## Context

The `sources` table now has a `citation` column (migration 008). For the initial 499 rows discovered in the insurance domain run (`raris-manifest-insurance---domain-regulations-20260311023257`), the `citation` field was backfilled by splitting the `name` on the ` — ` separator (e.g. `N.J.S.A. Title 17 Ch. 17 — Property and Casualty Insurance` → `N.J.S.A. Title 17 Ch. 17`).

This is a best-effort extraction. It does not produce the canonical short-form citation identifier (e.g. `N.J.S.A. 17:17`) that would be needed for cross-manifest deduplication and legal citation matching.

## Decision

After each discovery run completes, run a **batch citation normalization pass**:

1. Select all sources where `citation` looks like a descriptive phrase rather than a formal citation code (heuristic: no `:` separator, or citation = name, or length > 40 chars)
2. For each batch of ~20 sources, send a single LLM call:
   - Input: source name + URL + jurisdiction
   - Ask: "What is the official short-form citation identifier for this regulatory source? Return only the citation string (e.g. N.J.S.A. 17:17, 12 C.F.R. § 14, etc.) or null if none exists."
3. Update `sources.citation` with the normalized result
4. Sources with no formal citation (e.g. `NAIC Model Laws`) get `citation = NULL` to distinguish from sources with real citation numbers

## Why Batch

- Avoids 1 LLM call per row (499 individual calls = expensive)
- 20 rows per call × ~25 calls = manageable cost (~$0.10–0.50 total with Flash)
- Can be run as a one-time cleanup script or wired into the post-run pipeline

## Related

- Migration: `backend/alembic/versions/008_add_citation_depth_hint_to_sources.py`
- Backfill already applied to: manifest `raris-manifest-insurance---domain-regulations-20260311023257` (499 rows)
