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
# V6 Adaptive Expansion — Per-Node Prompt Routing
# ---------------------------------------------------------------------------
# Maps entity authority_type to a tailored depth-expansion question template.
# At L2+ the engine uses the entity's stored expansion_prompt (generated by the
# LLM during L1) or falls back to these templates when none was provided.
# Placeholders: {name}, {jurisdiction}, {url}

EXPANSION_TEMPLATES: dict[str, str] = {
    "regulator": (
        "You are examining the regulatory body: {name} ({url}).\n"
        "Jurisdiction: {jurisdiction_code}. Use {citation_hint} citation format.\n\n"
        "YOUR TASK: Produce an exhaustive, citation-level inventory of every insurance "
        "statute, administrative code chapter, regulation, bulletin, and circular "
        "administered or published by this body.\n\n"
        "DEPTH RULES — follow these exactly:\n"
        "1. For each top-level statute title or code title, emit ONE sources[] entry "
        "   with the full title citation (e.g. '{citation_hint} Title 17').\n"
        "2. Then emit a SEPARATE sources[] entry for EVERY individual chapter, part, "
        "   article, or named act within that title "
        "   (e.g. '{citation_hint} 17:22A-26 — Producer Licensing Act', "
        "   '{citation_hint} 17:33A — Fraud Prevention Act', "
        "   '{citation_hint} 17B:27 — Group Health Insurance', etc.).\n"
        "3. For administrative code, emit ONE entry per code title AND one per "
        "   chapter/subchapter (e.g. 'N.J.A.C. 11:2-17 — Claims Handling Regulations').\n"
        "4. For bulletins and circulars, emit the index/landing page as one entry.\n"
        "5. NEVER collapse multiple citations into a single entry. "
        "   Each citation identifier gets its own sources[] object.\n"
        "6. Use the sub_citations field to list related sibling citations "
        "   that share the same parent URL when individual URLs are unavailable.\n\n"
        "Include the specific {citation_hint} identifier in the 'name' field of every entry. "
        "Provide the most direct official URL available for each citation."
    ),
    "industry_body": (
        "You are examining the industry/standards body: {name} ({url}).\n"
        "List EVERY model law, accreditation standard, published guideline, "
        "best-practice document, certification requirement, and advisory circular "
        "published by this body. Include document identifiers and direct access URLs."
    ),
    "sro": (
        "You are examining the self-regulatory organization: {name} ({url}).\n"
        "List EVERY rule, standard, examination requirement, enforcement action "
        "database, and published guideline issued by this SRO. "
        "Include rule identifiers and direct URLs."
    ),
    "gse": (
        "You are examining the federal/quasi-governmental body: {name} ({url}).\n"
        "List EVERY federal statute, CFR section, Federal Register notice, "
        "regulatory guidance document, and annual report administered by this body. "
        "Include specific legal citations (e.g., CFR title/part) and direct URLs."
    ),
    "advisory_org": (
        "You are examining the advisory/rating organization: {name} ({url}).\n"
        "List EVERY advisory filing, rating methodology, statistical plan, "
        "circular, and published standard issued by this body. "
        "Include document identifiers and direct URLs."
    ),
    "actuarial_body": (
        "You are examining the actuarial standards body: {name} ({url}).\n"
        "List EVERY Actuarial Standard of Practice (ASOP), practice note, "
        "exposure draft, and published guidance document. "
        "Include document identifiers and direct URLs."
    ),
    "trade_association": (
        "You are examining the trade association: {name} ({url}).\n"
        "List EVERY published standard, regulatory position paper, model legislation, "
        "best-practice guide, and member certification program. "
        "Include document identifiers and direct URLs."
    ),
    "residual_market_mechanism": (
        "You are examining the residual market mechanism: {name} ({url}).\n"
        "Jurisdiction: {jurisdiction_code}.\n"
        "List EVERY governing statute, plan of operation, administrative rule, "
        "rate filing, and operational bulletin for this mechanism. "
        "Include citation identifiers and direct URLs."
    ),
    "compact": (
        "You are examining the interstate compact: {name} ({url}).\n"
        "List EVERY compact provision, uniform standard, filing requirement, "
        "and participating state adoption record. "
        "Include document identifiers and direct URLs."
    ),
    "other": (
        "You are examining the regulatory entity: {name} ({url}).\n"
        "List ALL regulatory documents, statutes, standards, guidelines, bulletins, "
        "and published materials issued or administered by this entity. "
        "Include document identifiers and URLs. Jurisdiction: {jurisdiction_code}."
    ),
}

# Fallback when authority_type is missing or unrecognized
_EXPANSION_TEMPLATE_DEFAULT = EXPANSION_TEMPLATES["other"]


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


def build_expansion_prompt(entity: dict) -> str:
    """Return a depth-appropriate expansion question for the given entity.

    Resolution order for jurisdiction_code:
      1. entity['jurisdiction_code'] — returned by L1 LLM (best)
      2. name-based extraction via _STATE_NAME_TO_CODE (recovery)
      3. empty string — caller logs WARNING

    Resolution order for citation_hint:
      1. entity['citation_format_hint'] — returned by L1 LLM (best)
      2. JURISDICTION_CITATION_HINTS lookup by resolved jurisdiction_code (recovery)
      3. generic fallback string — caller logs WARNING

    Called when the entity does not carry a stored expansion_prompt from L1.
    """
    authority_type = (entity.get("authority_type") or "other").lower()
    template = EXPANSION_TEMPLATES.get(authority_type, _EXPANSION_TEMPLATE_DEFAULT)

    jurisdiction_code, _jcode_source = resolve_jurisdiction_code(entity)
    citation_hint = (entity.get("citation_format_hint") or "").strip()

    if not citation_hint and jurisdiction_code:
        citation_hint = JURISDICTION_CITATION_HINTS.get(jurisdiction_code, "")

    if not citation_hint:
        citation_hint = "the jurisdiction's standard statutory citation format"

    return template.format(
        name=entity.get("name", "Unknown Entity"),
        jurisdiction=entity.get("jurisdiction", "unknown"),
        jurisdiction_code=jurisdiction_code or entity.get("jurisdiction", "unknown"),
        url=entity.get("url", "unknown URL"),
        citation_hint=citation_hint,
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
      "citation_format_hint": "Jurisdiction-specific statutory citation format e.g. N.J.S.A., Tex. Ins. Code, Cal. Ins. Code — leave blank for non-jurisdictional entities",
      "confidence": 0.0,
      "needs_human_review": false,
      "expansion_prompt": "A specific follow-up question to ask this entity at the next depth to discover all its statutes, regulations, codes, and guidelines. Tailor to entity type and jurisdiction."
    }
  ],
  "sources": [
    {
      "id": "src-kebab-id",
      "name": "Source/Document Name — include the exact citation identifier e.g. N.J.S.A. 17B:27 — Group Health Insurance",
      "regulatory_body": "entity-id",
      "type": "statute|regulation|guidance|bulletin|standard|educational|other",
      "format": "html|pdf|api|structured_data|other",
      "authority": "binding|advisory|informational",
      "jurisdiction": "federal|state|territorial|interstate",
      "url": "https://...",
      "access_method": "scrape|download|api|manual",
      "sub_citations": ["List sibling citation IDs that share this URL, e.g. N.J.S.A. 17B:25, N.J.S.A. 17B:26 — omit if each has its own URL"],
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
- For each entity, write an expansion_prompt describing exactly what to ask next to get its full regulatory inventory.
- CITATION DEPTH RULE: For statutes and administrative code, emit a SEPARATE sources[] entry for EVERY individual title, chapter, part, article, and named act. NEVER collapse multiple citation identifiers into a single entry. Each citation (e.g. N.J.S.A. 17B:27, N.J.A.C. 11:2-17) must be its own sources[] object with its own name and url.
- Use sub_citations[] only when multiple sibling sections genuinely share the same URL and cannot each have individual URLs.
"""

