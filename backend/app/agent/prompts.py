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

LANDSCAPE_MAPPER_PROMPT = """Analyze the following regulatory domain and identify ALL relevant
regulatory bodies organized by jurisdiction level.

Domain: {domain_description}

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

For each body, find at least 1-3 key regulatory sources. For major federal agencies,
find more (3-5). Focus on the most important, authoritative documents.

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
