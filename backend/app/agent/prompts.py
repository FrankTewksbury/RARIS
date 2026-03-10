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

# Used by V2 flat pipeline (discovery.py) — kept for backward compatibility
GUIDANCE_CONTEXT_BLOCK = """
Additional guidance documents:
{guidance_context}
"""

# ---------------------------------------------------------------------------
# V4 Prompt-Driven Discovery — Engine Prompts
# ---------------------------------------------------------------------------

L0_ORCHESTRATOR_SYSTEM = """You are a domain discovery agent. Execute the methodology \
in the user message exactly as specified.

Discover real, current entities, programs, and source documents. \
Use your training knowledge of government agencies, regulatory bodies, and domain-specific programs.

Produce ONLY valid JSON matching the output schema in the user message.
Do NOT include any prose, markdown fences, thinking, or explanation outside the JSON object.
The JSON must be parseable as-is — no trailing commas, no comments.
Assign honest confidence scores. Flag anything uncertain with needs_human_review: true.
"""

L0_JSON_SCHEMA_SUFFIX = """\
## Execution Instructions

Use web search grounding to verify all entities, URLs, and programs you discover.

Return ONLY the JSON object described in the Output Schema section above (Section 8).
Do not include any prose, markdown fences, or explanation outside the JSON.
The JSON must be parseable as-is — no trailing commas, no comments.

Rules:
- Every URL must be verified via web search — do NOT hallucinate URLs
- Assign confidence < 0.5 and needs_human_review: true for anything you cannot directly confirm
- Set verification_state: "candidate_only" for items found only via third-party indexes
- Include ALL items you discover — nothing is silently dropped
- For source files (PDFs, DOCs): include the direct file link, not just the hosting page
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
# Hierarchical Graph Discovery (V4) — Data-Driven Level Prompts
# ---------------------------------------------------------------------------

L1_ENTITY_EXPANSION_PROMPT = """For the following entities, find ALL child programs, source documents,
application portals, and sub-entities. USE YOUR WEB SEARCH CAPABILITY to find real, current information.

Entities to expand:
{entities_json}

Geographic scope: {geo_scope}

Seed programs as search hints (use to guide discovery, not as final output):
{seed_hints_json}

Programs already discovered (do NOT duplicate these):
{known_program_names_json}

INSTRUCTIONS:
- For each entity, search for all programs and products it administers
- Find source documents: guidelines PDFs, application portals, eligibility fact sheets
- Capture direct file links (PDF/DOC) where available — not just the generic hosting page
- Find application intake portals (Neighborly, Submittable, or equivalent) as direct apply URLs
- Identify sub-entities and subrecipients that administer programs on behalf of the entity

Return JSON with sources and programs found across ALL entities in this batch:
{{
  "sources": [
    {{
      "id": "src-{source_id_start:03d}",
      "name": "Document or page name",
      "regulatory_body": "entity-id-from-input",
      "type": "statute|regulation|guidance|standard|educational|guide",
      "format": "html|pdf|legal_xml|api|structured_data",
      "authority": "binding|advisory|informational",
      "jurisdiction": "federal|state|municipal",
      "url": "https://verified-direct-url",
      "access_method": "scrape|download|api|manual",
      "confidence": 0.0,
      "needs_human_review": false,
      "verification_state": "verified|candidate_only|verification_pending"
    }}
  ],
  "programs": [
    {{
      "name": "Program Name",
      "administering_entity": "Full Entity Name",
      "geo_scope": "national|state|county|city|tribal",
      "jurisdiction": "optional jurisdiction text",
      "benefits": "brief description",
      "eligibility": "brief description",
      "status": "active|paused|closed|verification_pending",
      "evidence_snippet": "quoted text from web source",
      "source_urls": ["https://verified-url"],
      "confidence": 0.0,
      "needs_human_review": false,
      "verification_state": "verified|candidate_only|verification_pending"
    }}
  ]
}}"""

L2_VERIFICATION_PROMPT = """Verify the following programs via web search.
For each program, search for the current official program page and confirm or update information.

Programs to verify:
{programs_json}

INSTRUCTIONS:
- For each program, use web search to find the current official page
- If found on official entity domain: set confidence >= 0.7, verification_state = "verified"
- If found only on third-party index: set verification_state = "candidate_only", confidence <= 0.4
- If not found at all: set confidence < 0.3, needs_human_review = true
- Update source_urls with any verified URLs found

Return JSON:
{{
  "verifications": [
    {{
      "name": "exact program name from input",
      "administering_entity": "exact entity from input",
      "confidence": 0.0,
      "needs_human_review": false,
      "verification_state": "verified|candidate_only|verification_pending",
      "source_urls": ["https://verified-url"],
      "evidence_snippet": "quoted text from web source or empty string"
    }}
  ]
}}"""

L3_GAP_FILL_PROMPT = """Fill coverage gaps in a discovery run.
USE YOUR WEB SEARCH CAPABILITY to find real programs for unmatched seeds and underrepresented categories.

Geographic scope: {geo_scope}
Programs already discovered: {discovered_count}

Unmatched seed programs (NOT yet found — search for these specifically):
{unmatched_seeds_json}

Underrepresented entity categories (search for programs in these sectors):
{gap_categories_json}

INSTRUCTIONS:
- For each unmatched seed, use web search to find the actual program page
- For each gap category, find representative programs in that sector
- Only return programs with at least one verified source URL
- Do NOT duplicate programs already in the discovery run

Return JSON:
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
      "evidence_snippet": "quoted text from web source",
      "source_urls": ["https://verified-url"],
      "provenance_links": {{
        "source_ids": [],
        "discovery_level": "L3"
      }},
      "confidence": 0.0,
      "needs_human_review": false
    }}
  ],
  "gap_fill_summary": {{
    "seeds_recovered": 0,
    "new_programs_found": 0,
    "categories_searched": []
  }}
}}"""


# ---------------------------------------------------------------------------
# V5 BFS Engine — Domain-Agnostic Sector Scope Header
# ---------------------------------------------------------------------------
# This is the ONLY engine-generated prompt fragment in V5.
# All domain methodology, output schema, and search behavior comes from the
# instruction file uploaded by the user. The engine prepends only this header
# to focus each sector call's AFC search budget on one sector at a time.

SECTOR_SCOPE_HEADER = """\
## SECTOR SCOPE FOR THIS CALL: {sector_label} (sector {sector_n} of {sector_total})
## Search budget: 64 searches — spend ALL searches on this sector only
## Do NOT discover entities from other sectors (those are running in parallel calls)
{search_hints_block}{completeness_block}---

"""


# ---------------------------------------------------------------------------
# ALGO-012 — Fine-Grain BFS Expansion Templates
# ---------------------------------------------------------------------------
# Each template asks exactly ONE bounded question scoped to the node type and
# depth level. The framework drives traversal; the LLM returns only direct
# children of the current node. No internal LLM recursion.
#
# Template key format:
#   "node:entity:{authority_type}"  — entity-level nodes (L1 output, L2 expansion)
#   "node:source_title"             — statute/code title nodes (L3 expansion)
#   "node:source_chapter"           — chapter/part nodes (L4 expansion)
#   "node:source_section"           — section nodes (L5 expansion, leaf)
#
# Placeholders available in ALL templates:
#   {name}             — entity or source name
#   {url}              — official URL
#   {jurisdiction_code}— 2-letter state code or US
#   {citation_hint}    — jurisdiction-specific citation format (e.g. N.J.S.A., Tex. Ins. Code)
#
# Additional placeholders for source-level templates:
#   {parent_citation}  — the citation being expanded (e.g. "N.J.S.A. Title 17")
#
# RULE: Do NOT hardcode jurisdiction-specific examples. Use {citation_hint} throughout.

# ── Entity-level templates (L2): ask for top-level titles only ──────────────

EXPANSION_TEMPLATES: dict[str, str] = {

    # Regulator: state/federal department — ask for top-level statute and admin code titles
    "node:entity:regulator": (
        "You are examining the regulatory body: {name} ({url}).\n"
        "Jurisdiction: {jurisdiction_code}. Citation format: {citation_hint}.\n\n"
        "YOUR TASK — ONE LEVEL ONLY:\n"
        "List ONLY the top-level statute titles and administrative code titles "
        "that this body administers or enforces.\n\n"
        "Return each title as one sources[] entry. "
        "Use depth_hint='title' for every entry.\n\n"
        "RULES:\n"
        "- Do NOT enumerate chapters, parts, sections, or sub-sections here. "
        "  Those will be discovered in subsequent calls.\n"
        "- Each title gets its own sources[] object "
        "  (e.g. '{citation_hint} Title 17', '{citation_hint} Title 17B', "
        "  '[Admin Code] Title 11').\n"
        "- Also list bulletins and circular index pages as single entries "
        "  (depth_hint='leaf').\n"
        "- Include the {citation_hint} identifier in the 'name' field of every entry."
    ),

    # GSE / federal quasi-governmental — CFR titles and USC chapters
    "node:entity:gse": (
        "You are examining the federal/quasi-governmental body: {name} ({url}).\n"
        "Citation format: {citation_hint}.\n\n"
        "YOUR TASK — ONE LEVEL ONLY:\n"
        "List ONLY the top-level U.S.C. chapter titles and C.F.R. title/part groupings "
        "that this body administers.\n\n"
        "Return each title/part grouping as one sources[] entry with depth_hint='title'.\n\n"
        "RULES:\n"
        "- Do NOT enumerate individual sections or sub-parts. Those come in subsequent calls.\n"
        "- Include Federal Register notice index pages as single entries "
        "  (depth_hint='leaf').\n"
        "- Use the specific legal citation (e.g. '42 U.S.C. ch. 50', '44 C.F.R. Subch. B') "
        "  in the 'name' field."
    ),

    # SRO — rule sets and published standard series
    "node:entity:sro": (
        "You are examining the self-regulatory organization: {name} ({url}).\n\n"
        "YOUR TASK — ONE LEVEL ONLY:\n"
        "List ONLY the top-level rule sets, standard series, and published guideline "
        "collections issued by this SRO.\n\n"
        "Return each series/collection as one sources[] entry with depth_hint='title'.\n\n"
        "RULES:\n"
        "- Do NOT enumerate individual rules or sub-rules. Those come in subsequent calls.\n"
        "- Use the series identifier (e.g. 'NAIC Model Laws Series', 'FINRA Rule 2000 Series') "
        "  in the 'name' field.\n"
        "- Include enforcement action databases and exam requirement indexes as single "
        "  entries (depth_hint='leaf')."
    ),

    # Industry/standards body — model law series and standard collections
    "node:entity:industry_body": (
        "You are examining the industry/standards body: {name} ({url}).\n\n"
        "YOUR TASK — ONE LEVEL ONLY:\n"
        "List ONLY the top-level model law series, accreditation standard collections, "
        "and published guideline series issued by this body.\n\n"
        "Return each series/collection as one sources[] entry with depth_hint='title'.\n\n"
        "RULES:\n"
        "- Do NOT enumerate individual model laws or sub-items. "
        "  Those come in subsequent calls.\n"
        "- Include certification program catalogs as single entries (depth_hint='leaf')."
    ),

    # Advisory/rating organization — filing and methodology series
    "node:entity:advisory_org": (
        "You are examining the advisory/rating organization: {name} ({url}).\n\n"
        "YOUR TASK — ONE LEVEL ONLY:\n"
        "List ONLY the top-level advisory filing series, rating methodology collections, "
        "and statistical plan groupings issued by this body.\n\n"
        "Return each series as one sources[] entry with depth_hint='title'.\n\n"
        "RULES:\n"
        "- Do NOT enumerate individual filings or circulars here.\n"
        "- Include circular index pages as single entries (depth_hint='leaf')."
    ),

    # Actuarial body — ASOP series
    "node:entity:actuarial_body": (
        "You are examining the actuarial standards body: {name} ({url}).\n\n"
        "YOUR TASK — ONE LEVEL ONLY:\n"
        "List ONLY the top-level Actuarial Standard of Practice (ASOP) series and "
        "practice note collections published by this body.\n\n"
        "Return each series as one sources[] entry with depth_hint='title'.\n\n"
        "RULES:\n"
        "- Do NOT enumerate individual ASOPs or sub-items here. "
        "  Those come in subsequent calls.\n"
        "- Include exposure draft index pages as single entries (depth_hint='leaf')."
    ),

    # Trade association — published standard and model legislation series
    "node:entity:trade_association": (
        "You are examining the trade association: {name} ({url}).\n\n"
        "YOUR TASK — ONE LEVEL ONLY:\n"
        "List ONLY the top-level published standard series, model legislation collections, "
        "and best-practice guide series issued by this body.\n\n"
        "Return each series as one sources[] entry with depth_hint='title'.\n\n"
        "RULES:\n"
        "- Do NOT enumerate individual standards or sub-items here.\n"
        "- Include certification program catalogs as single entries (depth_hint='leaf')."
    ),

    # Residual market mechanism — governing statute and plan of operation titles
    "node:entity:residual_market_mechanism": (
        "You are examining the residual market mechanism: {name} ({url}).\n"
        "Jurisdiction: {jurisdiction_code}. Citation format: {citation_hint}.\n\n"
        "YOUR TASK — ONE LEVEL ONLY:\n"
        "List ONLY the top-level governing statute titles and administrative rule titles "
        "for this mechanism. Also include the plan of operation as a single entry.\n\n"
        "Return each title as one sources[] entry with depth_hint='title'.\n\n"
        "RULES:\n"
        "- Do NOT enumerate individual chapters or sections here.\n"
        "- Include rate filing index pages and operational bulletin indexes as single "
        "  entries (depth_hint='leaf').\n"
        "- Use the {citation_hint} identifier in the 'name' field."
    ),

    # Interstate compact — compact provision series and uniform standard collections
    "node:entity:compact": (
        "You are examining the interstate compact: {name} ({url}).\n\n"
        "YOUR TASK — ONE LEVEL ONLY:\n"
        "List ONLY the top-level compact provision series and uniform standard "
        "collections published by this compact.\n\n"
        "Return each series as one sources[] entry with depth_hint='title'.\n\n"
        "RULES:\n"
        "- Do NOT enumerate individual provisions here. Those come in subsequent calls.\n"
        "- Include participating state adoption records as single leaf entries "
        "  (depth_hint='leaf')."
    ),

    # Generic fallback for unrecognized entity types
    "node:entity:other": (
        "You are examining the regulatory entity: {name} ({url}).\n"
        "Jurisdiction: {jurisdiction_code}. Citation format: {citation_hint}.\n\n"
        "YOUR TASK — ONE LEVEL ONLY:\n"
        "List ONLY the top-level statute titles, administrative code titles, rule series, "
        "and published standard collections issued or administered by this entity.\n\n"
        "Return each title/series as one sources[] entry with depth_hint='title'.\n\n"
        "RULES:\n"
        "- Do NOT enumerate individual chapters, sections, or sub-items here.\n"
        "- Include index/landing pages for bulletins and circulars as single "
        "  entries (depth_hint='leaf').\n"
        "- Use citation identifiers in the 'name' field where applicable."
    ),

    # ── Source-level templates (L3+): drill one level deeper per call ─────────

    # Title expansion (L3): ask for direct child chapters/parts/named acts
    "node:source_title": (
        "You are examining: {name}\n"
        "Citation: {parent_citation}\n"
        "URL: {url}\n\n"
        "YOUR TASK — ONE LEVEL ONLY:\n"
        "List ONLY the direct child chapters, parts, sub-titles, and named acts "
        "that exist immediately within {parent_citation}.\n\n"
        "Return each chapter/part as one sources[] entry with depth_hint='chapter'.\n\n"
        "RULES:\n"
        "- Do NOT enumerate sections or sub-sections. Those come in subsequent calls.\n"
        "- Each direct child gets its own sources[] object "
        "  (e.g. '{parent_citation}:17A — [Act Name]', "
        "  '{parent_citation}:22A-26 — [Act Name]').\n"
        "- If a child has no known URL of its own, use the parent URL and "
        "  note it in scraping_notes.\n"
        "- Include the full citation identifier in the 'name' field."
    ),

    # Chapter expansion (L4): ask for direct child sections
    "node:source_chapter": (
        "You are examining: {name}\n"
        "Citation: {parent_citation}\n"
        "URL: {url}\n\n"
        "YOUR TASK — ONE LEVEL ONLY:\n"
        "List ONLY the individual sections and sub-chapters that exist directly "
        "within {parent_citation}.\n\n"
        "Return each section as one sources[] entry with depth_hint='section'.\n\n"
        "RULES:\n"
        "- Do NOT enumerate sub-sections or paragraphs. Those come in subsequent calls.\n"
        "- Each section gets its own sources[] object "
        "  (e.g. '{parent_citation}-1', '{parent_citation}-2', etc.).\n"
        "- Include the full citation identifier in the 'name' field."
    ),

    # Section expansion (L5): leaf level — sub-sections only
    "node:source_section": (
        "You are examining: {name}\n"
        "Citation: {parent_citation}\n"
        "URL: {url}\n\n"
        "YOUR TASK — LEAF LEVEL:\n"
        "List the direct sub-sections and paragraphs within {parent_citation}.\n\n"
        "Return each sub-section as one sources[] entry with depth_hint='leaf'.\n\n"
        "RULES:\n"
        "- This is the deepest expansion level. Do not go further.\n"
        "- If the section has no meaningful sub-divisions, return it as a single "
        "  entry with depth_hint='leaf'.\n"
        "- Include the full citation identifier in the 'name' field."
    ),
}

# Fallback when node_type or authority_type is missing or unrecognized
_EXPANSION_TEMPLATE_DEFAULT = EXPANSION_TEMPLATES["node:entity:other"]


# ---------------------------------------------------------------------------
# Jurisdiction resolution: citation-hint lookup table and name-based extractor
# ---------------------------------------------------------------------------

# Authoritative citation format per US jurisdiction code (all 50 states + DC + territories)
JURISDICTION_CITATION_HINTS: dict[str, str] = {
    "AL": "Ala. Code",
    "AK": "Alaska Stat.",
    "AZ": "A.R.S.",
    "AR": "Ark. Code Ann.",
    "CA": "Cal. Ins. Code",
    "CO": "C.R.S.",
    "CT": "Conn. Gen. Stat.",
    "DE": "Del. Code Ann.",
    "FL": "Fla. Stat.",
    "GA": "O.C.G.A.",
    "HI": "Haw. Rev. Stat.",
    "ID": "Idaho Code",
    "IL": "215 ILCS",
    "IN": "Ind. Code",
    "IA": "Iowa Code",
    "KS": "K.S.A.",
    "KY": "KRS",
    "LA": "La. R.S.",
    "ME": "Me. Rev. Stat.",
    "MD": "Md. Code Ann.",
    "MA": "M.G.L.",
    "MI": "MCL",
    "MN": "Minn. Stat.",
    "MS": "Miss. Code Ann.",
    "MO": "Mo. Rev. Stat.",
    "MT": "Mont. Code Ann.",
    "NE": "Neb. Rev. Stat.",
    "NV": "NRS",
    "NH": "RSA",
    "NJ": "N.J.S.A.",
    "NM": "NMSA",
    "NY": "N.Y. Ins. Law",
    "NC": "N.C. Gen. Stat.",
    "ND": "N.D.C.C.",
    "OH": "ORC",
    "OK": "Okla. Stat.",
    "OR": "ORS",
    "PA": "40 P.S.",
    "RI": "R.I. Gen. Laws",
    "SC": "S.C. Code Ann.",
    "SD": "SDCL",
    "TN": "Tenn. Code Ann.",
    "TX": "Tex. Ins. Code",
    "UT": "Utah Code Ann.",
    "VT": "Vt. Stat. Ann.",
    "VA": "Va. Code Ann.",
    "WA": "RCW",
    "WV": "W. Va. Code",
    "WI": "Wis. Stat.",
    "WY": "Wyo. Stat.",
    "DC": "D.C. Code",
    "PR": "P.R. Laws Ann.",
    "GU": "Guam Code Ann.",
    "VI": "V.I. Code Ann.",
    "AS": "Am. Samoa Code",
    "MP": "CNMI Code",
    "US": "U.S.C.",
}

# State name → 2-letter code, used as name-based fallback when jurisdiction_code is missing.
# Multi-word names must come before single-word substrings (e.g. "new jersey" before "jersey").
_STATE_NAME_TO_CODE: dict[str, str] = {
    "new hampshire": "NH",
    "new jersey": "NJ",
    "new mexico": "NM",
    "new york": "NY",
    "north carolina": "NC",
    "north dakota": "ND",
    "rhode island": "RI",
    "south carolina": "SC",
    "south dakota": "SD",
    "west virginia": "WV",
    "puerto rico": "PR",
    "virgin islands": "VI",
    "american samoa": "AS",
    "northern mariana": "MP",
    "district of columbia": "DC",
    "washington dc": "DC",
    "alabama": "AL",
    "alaska": "AK",
    "arizona": "AZ",
    "arkansas": "AR",
    "california": "CA",
    "colorado": "CO",
    "connecticut": "CT",
    "delaware": "DE",
    "florida": "FL",
    "georgia": "GA",
    "hawaii": "HI",
    "idaho": "ID",
    "illinois": "IL",
    "indiana": "IN",
    "iowa": "IA",
    "kansas": "KS",
    "kentucky": "KY",
    "louisiana": "LA",
    "maine": "ME",
    "maryland": "MD",
    "massachusetts": "MA",
    "michigan": "MI",
    "minnesota": "MN",
    "mississippi": "MS",
    "missouri": "MO",
    "montana": "MT",
    "nebraska": "NE",
    "nevada": "NV",
    "ohio": "OH",
    "oklahoma": "OK",
    "oregon": "OR",
    "pennsylvania": "PA",
    "tennessee": "TN",
    "texas": "TX",
    "utah": "UT",
    "vermont": "VT",
    "virginia": "VA",
    "washington": "WA",
    "wisconsin": "WI",
    "wyoming": "WY",
    "guam": "GU",
}


def resolve_jurisdiction_code(entity: dict) -> tuple[str, str]:
    """Return (jurisdiction_code, source) for an entity.

    source values:
      'entity'   — field present and non-blank in the entity dict (L1 returned it correctly)
      'name'     — extracted from entity name via _STATE_NAME_TO_CODE lookup table
      'fallback' — could not resolve; caller must log WARNING and proceed with generic hint

    Multi-word state names are checked before single-word ones to avoid false matches
    (e.g. "New Jersey" must not match "Jersey").
    """
    code = (entity.get("jurisdiction_code") or "").strip().upper()
    if code:
        return code, "entity"

    name = entity.get("name", "").lower()
    for state_name, state_code in _STATE_NAME_TO_CODE.items():
        if state_name in name:
            return state_code, "name"

    return "", "fallback"


def build_expansion_prompt(node: dict, node_type: str = "entity") -> str:
    """Return a single-question expansion prompt for the given node.

    ALGO-012: Template is always authoritative. The stored LLM expansion_prompt
    from L1 is no longer used. Each call asks exactly one bounded question.

    Template key resolution order:
      1. "node:{node_type}:{authority_type}" — most specific
      2. "node:entity:{authority_type}"      — entity fallback
      3. "node:entity:other"                 — generic fallback

    For source nodes (source_title, source_chapter, source_section):
      Template key is "node:{node_type}" directly.

    Resolution order for jurisdiction_code:
      1. node['jurisdiction_code'] — returned by L1 LLM (best)
      2. name-based extraction via _STATE_NAME_TO_CODE (recovery)
      3. empty string — caller logs WARNING

    Resolution order for citation_hint:
      1. node['citation_format_hint'] — returned by L1 LLM (best)
      2. JURISDICTION_CITATION_HINTS lookup by resolved jurisdiction_code (recovery)
      3. generic fallback string — caller logs WARNING
    """
    # Source-level nodes use direct node_type key
    if node_type in ("source_title", "source_chapter", "source_section"):
        template_key = f"node:{node_type}"
        template = EXPANSION_TEMPLATES.get(template_key, _EXPANSION_TEMPLATE_DEFAULT)
        parent_citation = node.get("citation") or node.get("name", "this citation")
        return template.format(
            name=node.get("name", "Unknown Source"),
            url=node.get("url", "unknown URL"),
            parent_citation=parent_citation,
            citation_hint=node.get("citation_format_hint", ""),
            jurisdiction_code=node.get("jurisdiction_code", ""),
        )

    # Entity nodes: try specific key first, then generic entity fallback
    authority_type = (node.get("authority_type") or "other").lower()
    template_key = f"node:entity:{authority_type}"
    template = EXPANSION_TEMPLATES.get(
        template_key,
        EXPANSION_TEMPLATES.get("node:entity:other", _EXPANSION_TEMPLATE_DEFAULT),
    )

    jurisdiction_code, _jcode_source = resolve_jurisdiction_code(node)
    citation_hint = (node.get("citation_format_hint") or "").strip()

    if not citation_hint and jurisdiction_code:
        citation_hint = JURISDICTION_CITATION_HINTS.get(jurisdiction_code, "")

    if not citation_hint:
        citation_hint = "the jurisdiction's standard statutory citation format"

    return template.format(
        name=node.get("name", "Unknown Entity"),
        jurisdiction=node.get("jurisdiction", "unknown"),
        jurisdiction_code=jurisdiction_code or node.get("jurisdiction", "unknown"),
        url=node.get("url", "unknown URL"),
        citation_hint=citation_hint,
        parent_citation=node.get("name", "this entity"),
    )


# ---------------------------------------------------------------------------
# Shared JSON output schema injected into L2+ expansion prompts.
# Mirrors the schema declared in user-uploaded instruction files so that
# expansion calls return the same structure as L1 sector calls.
# ---------------------------------------------------------------------------

DISCOVERY_OUTPUT_SCHEMA = """\
## OUTPUT SCHEMA
Return ONLY valid JSON with this exact structure:

{
  "administering_entities": [
    {
      "id": "kebab-case-id",
      "name": "Official Entity Name",
      "jurisdiction": "federal|state|territorial|interstate",
      "jurisdiction_code": "REQUIRED — 2-letter code: NJ, CA, TX, DC, PR, GU, VI, AS, MP or US for federal",
      "authority_type": "regulator|industry_body|sro|advisory_org|actuarial_body|trade_association|residual_market_mechanism|compact|gse|other",
      "url": "https://...",
      "governs": ["regulatory area or line of business"],
      "citation_format_hint": "Jurisdiction-specific citation format e.g. N.J.S.A., Tex. Ins. Code, Cal. Ins. Code — leave blank for non-jurisdictional entities",
      "confidence": 0.0,
      "needs_human_review": false
    }
  ],
  "sources": [
    {
      "id": "src-kebab-id",
      "name": "Source/Document Name — include the exact citation identifier in the name",
      "regulatory_body": "entity-id",
      "type": "statute|regulation|guidance|bulletin|standard|educational|other",
      "format": "html|pdf|api|structured_data|other",
      "authority": "binding|advisory|informational",
      "jurisdiction": "federal|state|territorial|interstate",
      "jurisdiction_code": "2-letter code or US",
      "url": "https://...",
      "access_method": "scrape|download|api|manual",
      "depth_hint": "title|chapter|section|leaf",
      "citation": "Full citation identifier e.g. N.J.S.A. Title 17 or N.J.S.A. 17:22A-26",
      "sub_citations": ["sibling citation IDs sharing this URL — omit if each has its own URL"],
      "confidence": 0.0,
      "needs_human_review": false
    }
  ],
  "programs": [
    {
      "id": "prog-kebab-id",
      "name": "Program Name",
      "administering_entity": "Official Provider/Agency Name",
      "geo_scope": "national|state|county|city|tribal",
      "jurisdiction": "State or Federal",
      "benefits": "Short factual summary",
      "eligibility": "Short factual summary",
      "status": "active|paused|closed|verification_pending",
      "source_urls": ["https://..."],
      "provenance_links": {"source_ids": ["src-001"]},
      "evidence_snippet": "Short supporting quote/fact",
      "confidence": 0.0,
      "needs_human_review": false
    }
  ]
}

## HARD CONSTRAINTS
- Output JSON only; no prose, no markdown fences.
- No trailing commas.
- Every URL should be as specific and direct as possible.
- NEVER invent entities, URLs, or numeric fields.
- depth_hint REQUIRED on every sources[] entry: 'title'=top-level statute/code title, 'chapter'=chapter/part/named act, 'section'=individual section, 'leaf'=bulletins/circulars/indexes/no-further-children.
- citation REQUIRED on every sources[] entry — include the full citation identifier.
- ONE LEVEL ONLY: Return only what the task asked for at this depth. Do NOT recurse further.
- Each citation identifier gets its own sources[] object. NEVER collapse multiple citations into one entry.
"""

