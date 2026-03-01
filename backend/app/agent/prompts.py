SYSTEM_PROMPT = """You are a regulatory domain research agent. Your task is to discover and catalog
regulatory bodies, statutes, rules, guidance documents, and other regulatory sources for a given
domain description.

You must produce structured JSON output that conforms exactly to the schemas requested.
Be thorough and systematic. For each regulatory body, identify specific documents with URLs.
Assign confidence scores honestly — use lower scores when you are uncertain about a URL or
document's current availability.

Important rules:
- Only include sources you are reasonably confident exist
- Prefer official government (.gov) and authoritative organization URLs
- Flag anything uncertain with needs_human_review: true
- Be explicit about gaps — it's better to identify a gap than to fabricate a source
"""

GUIDANCE_CONTEXT_BLOCK = """
Additional guidance documents:
{guidance_context}
"""

LANDSCAPE_MAPPER_PROMPT = """Analyze the following regulatory domain and identify ALL relevant
regulatory bodies organized by jurisdiction level.

Domain: {domain_description}
{guidance_block}

CRITICAL INSTRUCTIONS:
- You MUST enumerate EVERY relevant body individually. Do NOT summarize or group them.
- If the domain mentions "all states" or "all 50 states", you MUST list EVERY state's
  regulatory body individually with its actual name, actual website URL, and jurisdiction.
- Include all federal agencies, national associations, self-regulatory organizations,
  and industry bodies relevant to this domain.
- For each state, use the actual name of the department/division (e.g., "California
  Department of Insurance", "Texas Department of Insurance", "New York Department of
  Financial Services") — these vary by state.

Return a JSON object with this structure:
{{
  "regulatory_bodies": [
    {{
      "id": "short-kebab-case-id",
      "name": "Full Official Name",
      "jurisdiction": "federal|state|municipal",
      "authority_type": "regulator|gse|sro|industry_body",
      "url": "https://official-website.gov",
      "governs": ["area1", "area2"]
    }}
  ],
  "jurisdiction_hierarchy": {{
    "federal": {{"bodies": ["id1", "id2"], "count": 0}},
    "state": {{"bodies": ["id3"], "count": 0}},
    "municipal": {{"bodies": [], "count": 0}}
  }}
}}

You MUST list every single body. Do not abbreviate, summarize, or use "etc."
This is a compliance system — completeness is mandatory."""

SOURCE_HUNTER_PROMPT = """For each of the following regulatory bodies, discover specific
regulatory source documents — statutes, regulations, guidance documents, standards,
educational materials, and guides.

Regulatory bodies:
{bodies_json}
{guidance_block}

For each body, find at least 1-3 key regulatory sources. For major federal agencies,
find more (3-5). Focus on the most important, authoritative documents.

CRITICAL EXPANSION RULES (Stage-2 scraping target):
- The manifest feeds web acquisition. Prefer direct, crawlable official program pages over summary pages.
- For each body, include program catalog/index pages PLUS individual program detail pages.
- Do not stop at one homepage/program overview URL if deeper official program endpoints exist.
- Use seeded program/provider hints from guidance to discover additional official pages.
- When `k_depth` in guidance is 3 or higher, target broad coverage: typically 6-12 source URLs per body where available.
- Every URL must be official or authoritative for that body/program.

For each source, provide:
{{
  "id": "src-NNN",
  "name": "Document name",
  "regulatory_body": "body-id (from the list above)",
  "type": "statute|regulation|guidance|standard|educational|guide",
  "format": "html|pdf|legal_xml|api|structured_data",
  "authority": "binding|advisory|informational",
  "jurisdiction": "federal|state|municipal",
  "url": "https://specific-document-url",
  "access_method": "scrape|download|api|manual",
  "update_frequency": "annual|quarterly|as_amended|static|unknown",
  "last_known_update": "YYYY-MM-DD or empty",
  "estimated_size": "small|medium|large",
  "scraping_notes": "Any notes about accessing this content",
  "classification_tags": ["tag1", "tag2"],
  "confidence": 0.0-1.0,
  "needs_human_review": true/false
}}

Return a JSON object: {{"sources": [...]}}

Number source IDs sequentially starting from src-{start_id:03d}.
Focus on finding real, accessible documents. Assign confidence based on how certain you are
that the URL is valid and the document is current. Use needs_human_review: true for anything
with confidence below 0.7."""

RELATIONSHIP_MAPPER_PROMPT = """Analyze the following regulatory sources and map relationships
between them. Identify:
1. Supersession chains (what replaced what)
2. Cross-references between documents
3. Implementation relationships (which regulation implements which statute)

Sources:
{sources_json}
{guidance_block}

Return a JSON object mapping source IDs to their relationships:
{{
  "relationships": {{
    "src-001": {{
      "supersedes": [],
      "superseded_by": [],
      "cross_references": ["src-002", "src-003"],
      "implements": "Reference to statutory authority"
    }}
  }}
}}

Only include relationships you are confident about. It's better to have fewer accurate
relationships than many speculative ones."""

COVERAGE_ASSESSOR_PROMPT = """Assess the coverage completeness of this regulatory domain discovery.

Domain: {domain_description}
{guidance_block}

Regulatory bodies found: {bodies_count}
Sources found: {sources_count}

Source breakdown by jurisdiction:
{jurisdiction_breakdown}

Source breakdown by type:
{type_breakdown}

Identify:
1. Known gaps — regulatory areas that should have sources but don't
2. Overall completeness score (0.0 to 1.0)
3. Any concerns about the quality of discovered sources

Return a JSON object:
{{
  "completeness_score": 0.0-1.0,
  "known_gaps": [
    {{
      "description": "What's missing",
      "severity": "high|medium|low",
      "mitigation": "How to address this gap"
    }}
  ],
  "assessment_notes": "Overall assessment narrative"
}}"""

PROGRAM_ENUMERATOR_PROMPT = """Extract concrete assistance programs from the discovered sources.

Domain: {domain_description}
{guidance_block}

Sources:
{sources_json}

Seeded direct program candidates:
{seed_programs_json}

Rules:
- Seeded records are POINTERS only. They are candidate hints and are not final output by themselves.
- Final programs MUST be source-verified using discovered official sources.
- Every final program MUST include:
  1) at least one official source URL in source_urls
  2) at least one discovered source id in provenance_links.source_ids
  3) an evidence_snippet derived from the discovered source context
- If a seeded candidate cannot be source-verified, do NOT emit it in programs.
- Normalize provider names and program names for dedup-ready output.
- Geo scope must be one of: national|state|county|city|tribal.
- Status must be one of: active|paused|closed|verification_pending.
- Confidence is 0.0 to 1.0.

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
      "evidence_snippet": "quoted evidence",
      "source_urls": ["https://..."],
      "provenance_links": {{
        "seed_file": "optional filename",
        "seed_row": "optional row marker",
        "source_ids": ["src-001"]
      }},
      "confidence": 0.0,
      "needs_human_review": false
    }}
  ]
}}

Do not include duplicate programs that differ only by punctuation/case."""

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
- Geo scope must be one of: national|state|county|city|tribal.
- Status must be one of: active|paused|closed|verification_pending.
- Confidence is 0.0 to 1.0.

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
}}

Do not include duplicate programs that differ only by punctuation/case."""


# ---------------------------------------------------------------------------
# Hierarchical Graph Discovery (V3) — Level-Aware Prompts
# ---------------------------------------------------------------------------

GROUNDED_LANDSCAPE_MAPPER_PROMPT = """Analyze the following regulatory domain and identify ALL relevant
regulatory bodies organized by jurisdiction level. USE YOUR WEB SEARCH CAPABILITY to find CURRENT,
real entities and their actual websites. Do not rely on training data alone.

Domain: {domain_description}
{guidance_block}

CRITICAL INSTRUCTIONS:
- Use web search to verify each entity exists and find its CURRENT official website URL.
- You MUST enumerate EVERY relevant body individually. Do NOT summarize or group them.
- Include all federal agencies, state housing finance agencies, national associations,
  self-regulatory organizations, and industry bodies relevant to this domain.
- Every URL must be verified via web search — do NOT guess or hallucinate URLs.

Return a JSON object with this structure:
{{
  "regulatory_bodies": [
    {{
      "id": "short-kebab-case-id",
      "name": "Full Official Name",
      "jurisdiction": "federal|state|municipal",
      "authority_type": "regulator|gse|sro|industry_body",
      "url": "https://verified-official-website",
      "governs": ["area1", "area2"]
    }}
  ],
  "jurisdiction_hierarchy": {{
    "federal": {{"bodies": ["id1", "id2"], "count": 0}},
    "state": {{"bodies": ["id3"], "count": 0}},
    "municipal": {{"bodies": [], "count": 0}}
  }}
}}

You MUST list every single body with verified URLs."""

GROUNDED_SOURCE_HUNTER_PROMPT = """For each of the following regulatory bodies, discover specific
regulatory source documents. USE YOUR WEB SEARCH CAPABILITY to find REAL, CURRENT documents
with verified URLs.

Regulatory bodies:
{bodies_json}
{guidance_block}

For each body, use web search to find at least 2-4 key source documents.

CRITICAL RULES:
- Every URL MUST be verified via web search — no hallucinated URLs.
- Prefer direct, crawlable official program pages over summary pages.

For each source, provide:
{{
  "id": "src-NNN",
  "name": "Document name",
  "regulatory_body": "body-id",
  "type": "statute|regulation|guidance|standard|educational|guide",
  "format": "html|pdf|legal_xml|api|structured_data",
  "authority": "binding|advisory|informational",
  "jurisdiction": "federal|state|municipal",
  "url": "https://verified-specific-document-url",
  "access_method": "scrape|download|api|manual",
  "confidence": 0.0-1.0,
  "needs_human_review": true/false
}}

Return a JSON object: {{"sources": [...]}}

Number source IDs sequentially starting from src-{start_id:03d}."""

L1_ENTITY_EXPANSION_PROMPT = """Expand the discovery graph for a specific entity type.
USE YOUR WEB SEARCH CAPABILITY to find real entities and programs.

Parent entity: {parent_entity_name} ({parent_entity_type})
Entity type to discover: {target_entity_type}
Geographic scope: {geo_scope}
{guidance_block}

Seed programs for this category (use as search hints):
{seed_hints_json}

Search queries to use (execute via web search):
{search_queries}

Return a JSON object:
{{
  "entities": [
    {{
      "id": "entity-kebab-case-id",
      "name": "Entity Name",
      "type": "{target_entity_type}",
      "url": "https://verified-url",
      "jurisdiction": "federal|state|municipal",
      "programs": [
        {{
          "name": "Program Name",
          "administering_entity": "Entity Name",
          "geo_scope": "national|state|county|city|tribal",
          "jurisdiction": "jurisdiction text",
          "benefits": "summary",
          "eligibility": "summary",
          "status": "active|verification_pending",
          "evidence_snippet": "text from web source",
          "source_urls": ["https://verified-url"],
          "confidence": 0.0-1.0,
          "needs_human_review": false
        }}
      ]
    }}
  ]
}}"""

L3_GAP_FILL_PROMPT = """Fill coverage gaps in a DPA discovery run.
USE YOUR WEB SEARCH CAPABILITY to find real programs for underrepresented categories.

Domain: {domain_description}
Geographic scope: {geo_scope}
{guidance_block}

Programs already discovered: {discovered_count}

Unmatched seed programs (NOT found in L0-L2):
{unmatched_seeds_json}

Underrepresented categories:
{gap_categories_json}

INSTRUCTIONS:
- For each unmatched seed, use web search to find the actual program page.
- Only return programs verified via web search with at least one source URL.
- Do NOT duplicate programs already discovered.

Return a JSON object:
{{
  "programs": [
    {{
      "name": "Program Name",
      "administering_entity": "Entity Name",
      "geo_scope": "national|state|county|city|tribal",
      "jurisdiction": "jurisdiction text",
      "benefits": "summary",
      "eligibility": "summary",
      "status": "active|verification_pending",
      "evidence_snippet": "text from web source",
      "source_urls": ["https://verified-url"],
      "provenance_links": {{
        "seed_file": "optional",
        "seed_row": "optional",
        "source_ids": [],
        "discovery_level": "L3"
      }},
      "confidence": 0.0-1.0,
      "needs_human_review": false
    }}
  ],
  "gap_fill_summary": {{
    "seeds_recovered": 0,
    "new_programs_found": 0,
    "categories_searched": []
  }}
}}"""
