---
type: development-plan
project: RORI
version: 1.1
created: 2026-02-13
updated: 2026-02-13
status: approved
authors: [Frank, Candi]
changelog:
  - version: 1.1
    date: 2026-02-13
    summary: Added Collection & Research swim lane (collect/*) with web scraping infrastructure, file system ingestion, AI-assisted research discovery, source corroboration, and FTHB regulatory seed manifest. Sourced from K4X Regulatory Reference (K4X-REG-001).
  - version: 1.0
    date: 2026-02-13
    summary: Initial macro development plan.
---

# RORI — Macro Development Plan v1.1

## Research On Regulatory for Industry(s)

---

## Purpose

This document defines the macro development plan for RORI — a curated regulatory knowledge platform with agent-based retrieval. It is organized into phases with discrete components, each intended to be developed as a feature branch off of `main` in GitHub. Contributors pick up a branch, develop it, and submit a pull request back to main.

The plan follows the staged delivery approach defined in the RORI Project Proposal and is designed to produce manageable, well-scoped units of work.

---

## Branch Naming Convention

All branches follow the pattern: `phase{N}/{component-name}` or `{swim-lane}/{component-name}`

Examples: `phase0/research-retrieval-algorithms`, `phase1/ingestion-pipeline`, `collect/web-scraping-infra`

---

## Swim Lane Overview

The plan is organized into two parallel tracks:

**Phased Development (phase0–phase3):** The core platform — research, engine, retrieval, agent, API, verticals, and scale. Components are sequenced with dependencies.

**Collection & Research (collect/*):** The data acquisition machinery — web scraping, file system ingestion, AI-assisted research discovery, and source corroboration. This swim lane runs in parallel with Phase 1 and feeds directly into the ingestion pipeline. It is where raw regulatory data is found, fetched, validated, and staged for processing.

These tracks converge at `phase1/ingestion-pipeline` — the collection swim lane produces staged documents, and the ingestion pipeline processes them into the indexed repository.

---

## Collection & Research Swim Lane (`collect/*`)

This swim lane builds the active data collection layer — the machinery that finds, fetches, corroborates, and stages regulatory source material. Without this, the platform has nothing to index.

The collection system is guided by a **Research Manifest** — a versioned, human-reviewed document that defines what sources to target, where they live, and how to access them. The manifest is seeded with known primary sources and expanded through AI-assisted deep research. No source enters the scraping or ingestion pipeline without appearing on an approved manifest.

**Dependency:** Requires `phase0/first-vertical-corpus-acquisition` (the initial cataloging effort that identifies what to collect). Can begin development in parallel with Phase 0 research branches and must be operational before Phase 1 ingestion pipeline testing begins.

---

### `collect/research-manifest-system`

The research manifest is the steering mechanism for all data collection. It is a versioned, structured document (or database) that catalogs every regulatory source RORI targets — including its URL or access method, format, jurisdiction, update frequency, and approval status.

**How it works:**
1. **Seed** — Start with known primary sources (statutes, CFR citations, agency guidance, GSE guides). The FTHB seed manifest (see Appendix A) provides the initial target list.
2. **Expand** — AI-assisted research (see `collect/ai-research-discovery`) proposes additional sources discovered through web search, citation chasing, and cross-reference analysis.
3. **Review** — A human reviews proposed additions. Only approved sources move to "active" status.
4. **Maintain** — Sources are versioned. When a source URL changes, a document is superseded, or a new regulation takes effect, the manifest is updated.

**Deliverables:**
- Manifest data model (source URL, format, jurisdiction, regulatory domain, update frequency, approval status, last fetched, last verified)
- CLI or UI for adding, reviewing, and approving manifest entries
- Version history for manifest changes
- Export format for downstream consumption by scraping and ingestion systems
- FTHB seed manifest populated from K4X-REG-001 reference (see Appendix A)

---

### `collect/web-scraping-infra`

Automated, scheduled web scraping from authorized targets. Uses a managed scraping service (e.g., ScrapingAnt) to handle rotation, rate limiting, and JavaScript rendering. Only scrapes sources that appear on an approved research manifest.

**Target categories for FTHB vertical:**
- Federal regulatory sources (.gov) — CFPB, HUD, FTC, DOJ
- Government-Sponsored Enterprises — Fannie Mae, Freddie Mac seller/servicer guides
- State regulatory sources — State insurance commissioners, state housing finance agencies, state attorney general offices
- Authorized .org sources — Industry associations, HUD-approved counseling network resources

**Deliverables:**
- Scraping service integration (ScrapingAnt or equivalent)
- Target management — pull active targets from research manifest
- Scheduling engine — configurable per-source scrape frequency
- Change detection — compare fetched content against last-known version, flag changes
- Output staging — scraped documents land in a staging area for ingestion pipeline pickup
- Rate limiting and politeness controls (respect robots.txt, configurable delays)
- Error handling and retry logic
- Scrape audit log (what was fetched, when, HTTP status, content hash)

---

### `collect/filesystem-ingestion`

Watched directory / file system mount where documents can be dropped for automatic ingestion. Supports bulk import of regulatory documents that are obtained outside of web scraping — e.g., PDFs downloaded manually, FOIA responses, documents received from partners, GSE guide archives.

**Deliverables:**
- Watched directory configuration (mount points, polling frequency)
- File type detection and validation
- Metadata extraction from filename conventions or sidecar files
- Deduplication against existing staged documents
- Staging area integration (same staging area as web scraping output)
- Bulk import CLI for one-time large corpus loads
- Import audit log (what was imported, source path, timestamp, file hash)

---

### `collect/ai-research-discovery`

AI-assisted research to expand the research manifest beyond known sources. Uses web search and LLMs to proactively discover regulatory sources that the seed manifest doesn't cover — finding what we don't know we're missing.

**How it works:**
1. **Prompt-driven search** — Given a regulatory domain (e.g., "RESPA settlement procedures"), the system runs web searches and LLM queries to discover primary sources, guidance documents, enforcement actions, and interpretive letters.
2. **Citation chasing** — Given a known regulation (e.g., 12 C.F.R. Part 1024), the system follows citation chains to find related regulations, amendments, and guidance that cross-reference it.
3. **Research manifest proposal** — Discovered sources are compiled into a research manifest proposal with metadata (URL, format, jurisdiction, relevance assessment, confidence score).
4. **Human review gate** — Nothing enters the approved manifest without human review. The proposal is a recommendation, not an action.

**Deliverables:**
- Research prompt templates per regulatory domain
- Web search integration for source discovery
- LLM-based citation chain analysis
- Research manifest proposal format (structured output with confidence scores)
- Human review workflow (approve, reject, flag for further research)
- Discovery audit trail (what was searched, what was found, what was recommended, what was approved)

---

### `collect/source-corroboration`

Deep research to validate and cross-reference sources before they enter the repository. A source appearing on a government website is necessary but not sufficient — RORI must verify that the version is current, that it hasn't been superseded, and that the platform's interpretation aligns with authoritative secondary sources.

**How it works:**
1. **Currency verification** — Check that the fetched version is the most current. Compare against Federal Register notices, agency update logs, and supersession references.
2. **Cross-reference validation** — For each primary source, find at least one corroborating secondary source (legal commentary, agency FAQ, enforcement guidance) that confirms the interpretation.
3. **Supersession detection** — Identify whether a regulation has been amended, superseded, or recodified since last fetch.
4. **Conflict flagging** — When sources disagree (e.g., a state law extends a federal protection), flag the conflict for human review with both sources cited.

**Deliverables:**
- Currency check automation (compare fetched content against known latest version indicators)
- Cross-reference search for corroborating sources
- Supersession detection logic
- Conflict detection and flagging
- Corroboration report per source (verified/unverified/conflicting, with evidence)
- Integration with research manifest (update source status based on corroboration results)

---

### `collect/fthb-corpus-targeting`

The FTHB-specific execution of the collection swim lane. Applies the research manifest, scraping infrastructure, and corroboration pipeline to the First-Time Homebuyer regulatory domain. This is where the general collection machinery meets the specific vertical.

**Regulatory domains (from K4X-REG-001):**
- HUD Housing Counseling Program (24 C.F.R. Part 214)
- Fair Housing Act (42 U.S.C. §§ 3601–3619)
- RESPA (12 U.S.C. §§ 2601–2617; Regulation X)
- ECOA (15 U.S.C. §§ 1691–1691f; Regulation B)
- GLBA (15 U.S.C. §§ 6801–6809; FTC Safeguards Rule)
- FCRA (15 U.S.C. §§ 1681–1681x)
- GSE Seller/Servicer Guides (Fannie Mae, Freddie Mac)
- State and local requirements (fair housing extensions, DPA programs, state privacy laws)
- CFPB guidance on AI in financial services

**Deliverables:**
- FTHB seed manifest fully populated with primary source URLs and access methods
- Scraping schedules configured per source (daily for CFPB, weekly for GSE guides, monthly for CFR)
- Corroboration runs completed for all seed sources
- Gap analysis: what regulatory areas are covered vs. what's missing
- Staged corpus ready for Phase 1 ingestion pipeline

---

## Phase 0: Foundation & Research

This phase resolves the open questions from the project proposal before application code is written. Branches in this phase produce decision documents, evaluation frameworks, and the project skeleton — not application code.

### `phase0/project-scaffold`

Monorepo structure, CI/CD pipeline (GitHub Actions), linting, formatting, branch protection rules, contributing guide. Establishes the folder convention and ensures any contributor can clone and orient themselves immediately.

**Deliverables:**
- Repository layout and workspace configuration
- CI/CD pipelines (lint, test, build)
- Branch protection rules on `main`
- CONTRIBUTING.md with branch workflow documentation
- Pre-commit hooks

---

### `phase0/research-retrieval-algorithms`

Deep research into state-of-the-art retrieval for legal and regulatory text. Covers hybrid retrieval (dense vector + sparse/lexical + structured metadata filtering), re-ranking models tuned for precision, and deterministic retrieval modes for audit repeatability.

**Deliverables:**
- Architecture Decision Record (ADR) with findings and recommendation
- Comparative analysis of retrieval approaches for regulatory text
- Benchmark references and prior art

---

### `phase0/research-chunking-strategies`

Research into chunking approaches that preserve semantic integrity of regulatory text. Legal and regulatory text is heavily nested and cross-referential — standard chunking destroys context. This branch evaluates hierarchical, section-aware, and cross-reference-preserving chunking strategies.

**Deliverables:**
- ADR with findings and recommendation
- Sample chunking outputs against representative regulatory documents
- Evaluation criteria for chunk quality

---

### `phase0/research-repository-architecture`

Evaluate the storage layer: vector DB, knowledge graph, hybrid, or combination. Determine what storage and indexing combination best serves regulatory data with complex hierarchical relationships — supersession chains, applicability hierarchies, jurisdiction trees, effective date ranges.

**Deliverables:**
- ADR with findings and recommendation
- Storage architecture diagram
- Evaluation matrix of candidate technologies

---

### `phase0/research-agent-framework`

Evaluate agentic orchestration patterns for tunable-depth regulatory reasoning. Covers tool-use patterns, planning, self-correction, and citation threading. Determine which framework(s) best support the spectrum from quick applicability checks to exhaustive regulatory audits.

**Deliverables:**
- ADR with findings and recommendation
- Framework comparison matrix
- Prototype interaction patterns (pseudocode or diagrams)

---

### `phase0/evaluation-framework`

Define how RORI rigorously measures accuracy, completeness, consistency, and repeatability. Build a test harness and benchmark suite. RORI's non-negotiables (accuracy, consistency, completeness, auditability) must be measurable from day one.

**Deliverables:**
- Evaluation methodology document
- Test harness scaffold
- Benchmark dataset definition (what constitutes a passing score)
- Metrics definitions and measurement approach

---

### `phase0/first-vertical-corpus-acquisition`

Identify, catalog, and begin acquiring the Mortgage/First-Time Homebuyer regulatory corpus: CFPB guidance, federal mortgage statutes, GSE (Fannie Mae, Freddie Mac) seller/servicer guides, state-level regulations, educational materials. This is a data sourcing effort, not an engineering one, but it gates everything in Phase 1 and feeds the research manifest for the collection swim lane.

**Deliverables:**
- Source catalog with URLs, formats, and access methods
- Licensing and usage rights assessment per source
- Sample documents acquired and staged for ingestion testing
- Corpus coverage map (what's available vs. what's needed)
- Initial research manifest seed entries for `collect/research-manifest-system`

---

## Phase 1: Core Engine — Single Vertical (Mortgage/Homebuyer)

Build the working system end-to-end against the first vertical. Every component is validated against real regulatory data using the evaluation framework from Phase 0. The collection swim lane feeds staged documents into the ingestion pipeline.

### `phase1/ingestion-pipeline`

The foundation of everything. Handles disparate document types (PDFs, HTML, legal XML, structured guides, unstructured guidance letters). Accepts staged documents from both the collection swim lane (web scraping, file system ingestion) and manual imports. Must be robust and extensible — every future vertical flows through this pipeline.

**Deliverables:**
- Document type detection and routing
- Text extraction for each supported format
- Structure preservation (headings, sections, tables, lists)
- Staging area integration (pickup from collection swim lane output)
- Error handling and ingestion reporting
- Extensibility pattern for new document types

---

### `phase1/curation-enrichment`

Metadata extraction and enrichment: jurisdiction tagging, effective dates, applicability scope, supersession chains. Deduplication and conflict resolution across overlapping sources. Quality gates and validation checks. This is where raw regulatory documents become structured, queryable knowledge.

**Deliverables:**
- Metadata extraction pipeline (jurisdiction, dates, applicability, supersession)
- Deduplication logic
- Quality gate definitions and validation rules
- Enrichment audit trail (what was added, by what process)

---

### `phase1/semantic-chunking`

Implements the chunking strategy selected in Phase 0. Section-aware, hierarchy-preserving, cross-reference-maintaining chunking optimized for regulatory text. The quality of retrieval depends entirely on the quality of chunking.

**Deliverables:**
- Chunking implementation per ADR recommendation
- Cross-reference link preservation
- Hierarchy metadata attached to each chunk
- Validation against evaluation framework benchmarks

---

### `phase1/indexing-layer`

Build the hybrid index per the Phase 0 repository architecture decision. Dense vector embeddings, sparse/lexical index, structured metadata index. Support for graph-based regulatory relationships if the ADR called for it.

**Deliverables:**
- Index creation pipeline
- Embedding generation for regulatory chunks
- Metadata index for structured queries (jurisdiction, date, applicability)
- Graph index for regulatory relationships (if applicable per ADR)

---

### `phase1/retrieval-engine`

The core retrieval system: hybrid search, re-ranking, confidence scoring, coverage estimation. Must support deterministic retrieval modes for audit repeatability. This is the query engine that the agent layer calls into.

**Deliverables:**
- Hybrid search implementation (vector + lexical + metadata)
- Re-ranking pipeline
- Confidence scoring per result
- Coverage estimation ("how much of the applicable corpus did we search?")
- Deterministic retrieval mode for audit scenarios
- Evaluation framework benchmark results

---

### `phase1/agent-core`

The agent layer that orchestrates retrieval, reasoning, and synthesis. Tunable response depth (quick lookup vs. exhaustive analysis). Citation threading throughout the response chain. Guardrails against hallucination — every claim must be grounded in a source. Context window management for large corpuses.

**Deliverables:**
- Agent orchestration implementation per ADR
- Tunable depth parameter (applicability check through full audit)
- Multi-step reasoning for complex regulatory queries
- Hallucination guardrails (no unsupported assertions)
- Context window management strategy

---

### `phase1/citation-provenance`

End-to-end citation provenance from source document to section to version to ingestion timestamp to agent response. Every answer must carry its audit trail. This is a non-negotiable.

**Deliverables:**
- Provenance data model
- Citation attachment at every stage (ingestion, chunking, retrieval, generation)
- Provenance query API ("show me the source chain for this claim")
- Audit report generation

---

### `phase1/version-control-regulatory`

Change tracking for living regulatory documents. Version history, supersession detection, effective date management. Regulatory data evolves constantly — the system must handle updates without breaking existing citations or audit trails.

**Deliverables:**
- Document version tracking
- Supersession chain detection and linking
- Effective date management (what was in effect on date X?)
- Re-ingestion workflow for updated documents
- Citation stability (old citations remain valid even after updates)

---

### `phase1/developer-api-alpha`

Clean API surface for agent invocation with tunable parameters (depth, scope, jurisdiction filters, confidence thresholds). Alpha-grade developer integration — enough for third-party AI pipelines to use RORI as a context source.

**Deliverables:**
- REST API endpoints for agent invocation
- Request/response schema with tunable parameters
- Authentication and basic access control
- API documentation
- Example integration patterns

---

## Phase 2: Multi-Vertical & Advanced Capabilities

Onboard additional verticals and build the differentiating cross-corpus capabilities.

### `phase2/vertical-insurance`

Onboard the Insurance vertical: state-by-state insurance regulation corpus, broker/agent compliance requirements. Exercises the ingestion pipeline with a highly jurisdictional dataset (50 states, each with different rules).

**Deliverables:**
- Insurance corpus acquisition and cataloging
- Ingestion pipeline validation with insurance-specific document formats
- Jurisdiction mapping (state-by-state)
- Evaluation framework benchmarks for insurance vertical

---

### `phase2/vertical-medical-gig`

Onboard the Medical/Gig Platform vertical: labor law, medical licensing, telehealth regulations, platform compliance. Tests the system at the intersection of multiple regulatory domains.

**Deliverables:**
- Medical/Gig corpus acquisition and cataloging
- Multi-domain intersection handling (labor + medical + telehealth + platform)
- Evaluation framework benchmarks for this vertical

---

### `phase2/cross-corpus-comparison`

Document-to-document comparison engine. Compare a new directive against an existing standard, a policy against a requirements set. Structured diff output showing alignments, gaps, and conflicts.

**Deliverables:**
- Comparison engine implementation
- Structured diff output format (alignments, gaps, conflicts)
- Multi-corpus query support
- Comparison result provenance

---

### `phase2/gap-analysis-engine`

Given a requirements corpus and a compliance posture, identify what's covered, what's missing, and what's partially addressed. Produces structured gap reports with prioritized findings.

**Deliverables:**
- Gap detection logic
- Coverage scoring
- Prioritized gap report generation
- Remediation guidance linkage

---

### `phase2/rubric-quality-assessment`

Assess work product against a regulatory rubric or requirements checklist. Score coverage, flag deficiencies, produce actionable remediation guidance.

**Deliverables:**
- Rubric definition format
- Scoring engine
- Deficiency flagging with source references
- Remediation output

---

### `phase2/synthesis-output`

Transform analysis results into structured deliverables: compliance plans, gap reports, requirement matrices, action item lists.

**Deliverables:**
- Output template system
- Compliance plan generation
- Requirement matrix generation
- Export formats (structured data, human-readable reports)

---

### `phase2/multilingual-support`

Multilingual ingestion and indexing, cross-language retrieval, translation-aware semantic matching, jurisdiction-language mapping.

**Deliverables:**
- Multilingual ingestion pipeline
- Cross-language retrieval
- Translation-aware semantic matching
- Jurisdiction-language mapping configuration

---

### `phase2/packaged-application`

A front-end paired with the agent, pre-configured for specific use cases (regulatory research assistant, compliance gap analyzer, document comparison tool). The first end-user experience on top of the platform.

**Deliverables:**
- Front-end application
- Pre-configured use case workflows
- User authentication and session management

---

### `phase2/api-hardened`

Production-grade API: rate limiting, access control, usage metering, SDK/integration patterns for common agentic frameworks.

**Deliverables:**
- Rate limiting
- Granular access control
- Usage metering and billing hooks
- SDK or integration library
- Production API documentation

---

## Phase 3: Scale & Fine-Grained Expansion

### `phase3/fine-grained-verticals`

Municipal codes, local zoning ordinances, sub-regulatory guidance. Tests the platform at maximum granularity and volume.

**Deliverables:**
- Fine-grained corpus acquisition and ingestion
- Scale validation at high document volumes

---

### `phase3/change-monitoring`

Proactive regulatory change monitoring: detect when source documents are updated, assess impact on existing analysis, trigger re-evaluation alerts.

**Deliverables:**
- Source monitoring and change detection
- Impact assessment engine
- Alert and notification system

---

### `phase3/performance-at-scale`

Optimization for large corpus volumes, concurrent queries, and multi-tenant workloads.

**Deliverables:**
- Performance benchmarks
- Query optimization
- Caching strategies
- Multi-tenant isolation

---

### `phase3/vertical-marketplace`

Plug-in model for vertical-specific configurations. Allows third parties to contribute ingestion configs, chunking rules, and domain-specific enrichment for new regulatory domains.

**Deliverables:**
- Plugin specification format
- Marketplace infrastructure
- Contribution and certification workflow

---

## Sequencing & Dependencies

### Critical Path

```
phase0/project-scaffold
    ├──> Phase 0 research branches (ALL parallelizable)
    │         └──> phase0/first-vertical-corpus-acquisition ──┐
    │                                                         │
    │    ┌────────────────────────────────────────────────────┘
    │    │
    │    ├──> collect/research-manifest-system
    │    │         └──> collect/web-scraping-infra
    │    │         └──> collect/ai-research-discovery
    │    │         └──> collect/source-corroboration
    │    │         └──> collect/fthb-corpus-targeting ─────────┐
    │    │                                                     │
    │    └──> collect/filesystem-ingestion ────────────────────┤
    │                                                          │
    │    ┌─────────────────────────────────────────────────────┘
    │    │   (Staged documents ready)
    │    │
    │    └──> phase1/ingestion-pipeline
    │              └──> phase1/curation-enrichment
    │                        └──> phase1/semantic-chunking
    │                                  └──> phase1/indexing-layer
    │                                            └──> phase1/retrieval-engine
    │                                                      └──> phase1/agent-core
    │                                                                └──> phase1/developer-api-alpha
```

### Parallel Work Opportunities

**Phase 0:** All research branches (`research-retrieval-algorithms`, `research-chunking-strategies`, `research-repository-architecture`, `research-agent-framework`) can be worked simultaneously by different contributors. `evaluation-framework` and `first-vertical-corpus-acquisition` can also run in parallel.

**Collection swim lane:** Once `first-vertical-corpus-acquisition` produces the seed catalog, all collection branches can begin development. `research-manifest-system` should land first, then `web-scraping-infra`, `filesystem-ingestion`, `ai-research-discovery`, and `source-corroboration` can be developed in parallel. `fthb-corpus-targeting` is the integration branch that exercises them all together.

**Phase 1:** Once `indexing-layer` lands, `citation-provenance` and `version-control-regulatory` can be developed alongside `retrieval-engine` and `agent-core`.

**Phase 2:** All vertical onboarding branches (`vertical-insurance`, `vertical-medical-gig`) can run in parallel once the Phase 1 pipeline is proven. Cross-corpus capabilities (`cross-corpus-comparison`, `gap-analysis-engine`, `rubric-quality-assessment`, `synthesis-output`) can also be developed in parallel.

---

## Branch Lifecycle

1. **Create** — Branch from `main` using naming convention `phase{N}/{component-name}` or `collect/{component-name}`
2. **Develop** — Work the component per the deliverables listed above
3. **Test** — Validate against evaluation framework (Phase 1+)
4. **PR** — Submit pull request to `main` with documentation
5. **Review** — Peer review and approval
6. **Merge** — Squash merge to `main`

---

## Appendix A: FTHB Regulatory Seed Manifest

Initial primary source targets for the First-Time Homebuyer vertical, derived from K4X Regulatory & Compliance Reference (K4X-REG-001 v1.0).

### Federal Statutes and Regulations

| Regulatory Domain | Citation | Primary Source |
|---|---|---|
| HUD Housing Counseling | 24 C.F.R. Part 214 | ecfr.gov, HUD.gov Housing Counseling program pages |
| Fair Housing Act | 42 U.S.C. §§ 3601–3619 | uscode.house.gov, HUD.gov Fair Housing pages |
| RESPA | 12 U.S.C. §§ 2601–2617 | uscode.house.gov, CFPB Regulation X pages |
| RESPA Regulation X | 12 C.F.R. Part 1024 | ecfr.gov, consumerfinance.gov |
| ECOA | 15 U.S.C. §§ 1691–1691f | uscode.house.gov, CFPB Regulation B pages |
| ECOA Regulation B | 12 C.F.R. Part 1002 | ecfr.gov, consumerfinance.gov |
| GLBA | 15 U.S.C. §§ 6801–6809 | uscode.house.gov |
| FTC Safeguards Rule | 16 C.F.R. Part 314 | ecfr.gov, ftc.gov |
| FCRA | 15 U.S.C. §§ 1681–1681x | uscode.house.gov, consumerfinance.gov |

### Agency Guidance and Enforcement

| Source | URL Pattern | Content Type |
|---|---|---|
| CFPB Guidance & Rules | consumerfinance.gov/policy-compliance/ | Guidance, bulletins, enforcement actions |
| CFPB Mortgage Resources | consumerfinance.gov/owning-a-home/ | Consumer guidance, educational material |
| CFPB AI/Chatbot Guidance | consumerfinance.gov (search: AI, chatbot) | Enforcement signals, advisory opinions |
| HUD Housing Counseling | hud.gov/program_offices/housing/sfh/hcc | Program rules, agency requirements, HCS docs |
| HUD-9902 Reporting | hud.gov (search: 9902) | Reporting formats, XML schemas |
| FTC Privacy Guidance | ftc.gov/legal-library/ | Safeguards Rule guidance, enforcement |
| DOJ Fair Housing | justice.gov/crt/fair-housing | Enforcement actions, settlement agreements |

### GSE Seller/Servicer Guides

| Source | URL Pattern | Content Type |
|---|---|---|
| Fannie Mae Selling Guide | singlefamily.fanniemae.com/originating-underwriting | Full guide, updates, announcements |
| Fannie Mae Servicing Guide | singlefamily.fanniemae.com/servicing | Full guide, updates |
| Freddie Mac Seller/Servicer Guide | guide.freddiemac.com | Full guide, bulletins |
| Fannie Mae HomeReady | fanniemae.com (search: HomeReady) | Program requirements |
| Freddie Mac Home Possible | freddiemac.com (search: Home Possible) | Program requirements |

### State and Local (Initial Targets — Expand via AI Research Discovery)

| Source Category | Discovery Method | Priority |
|---|---|---|
| State fair housing statutes | AI research discovery + manual review | High |
| State housing finance agencies | Known URLs per state (50 targets) | High |
| State DPA program guides | AI research discovery per state | Medium |
| State data privacy laws (CCPA, etc.) | Known citations + AI expansion | Medium |
| Municipal DPA programs | AI research discovery per metro area | Lower (Phase 2+) |

### Corroboration Sources

| Source | Purpose |
|---|---|
| Federal Register (federalregister.gov) | Verify currency, find amendments and proposed rules |
| Congress.gov | Track legislative changes to underlying statutes |
| Legal commentary (law review articles, bar association guides) | Corroborate interpretation of regulatory requirements |
| Agency FAQs and interpretive letters | Validate practical application of rules |

---

*v1.1 — Updated 2026-02-13 — Frank & Candi*
*Changelog: Added Collection & Research swim lane and FTHB Regulatory Seed Manifest (Appendix A)*
