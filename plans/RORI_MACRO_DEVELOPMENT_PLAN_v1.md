---
type: development-plan
project: RORI
version: 1.0
created: 2026-02-13
status: approved
authors: [Frank, Candi]
---

# RORI — Macro Development Plan v1.0

## Research On Regulatory for Industry(s)

---

## Purpose

This document defines the macro development plan for RORI — a curated regulatory knowledge platform with agent-based retrieval. It is organized into phases with discrete components, each intended to be developed as a feature branch off of `main` in GitHub. Contributors pick up a branch, develop it, and submit a pull request back to main.

The plan follows the staged delivery approach defined in the RORI Project Proposal and is designed to produce manageable, well-scoped units of work.

---

## Branch Naming Convention

All branches follow the pattern: `phase{N}/{component-name}`

Example: `phase0/research-retrieval-algorithms`, `phase1/ingestion-pipeline`

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

Identify, catalog, and begin acquiring the Mortgage/First-Time Homebuyer regulatory corpus: CFPB guidance, federal mortgage statutes, GSE (Fannie Mae, Freddie Mac) seller/servicer guides, state-level regulations, educational materials. This is a data sourcing effort, not an engineering one, but it gates everything in Phase 1.

**Deliverables:**
- Source catalog with URLs, formats, and access methods
- Licensing and usage rights assessment per source
- Sample documents acquired and staged for ingestion testing
- Corpus coverage map (what's available vs. what's needed)

---

## Phase 1: Core Engine — Single Vertical (Mortgage/Homebuyer)

Build the working system end-to-end against the first vertical. Every component is validated against real regulatory data using the evaluation framework from Phase 0.

### `phase1/ingestion-pipeline`

The foundation of everything. Handles disparate document types (PDFs, HTML, legal XML, structured guides, unstructured guidance letters). Extracts text, preserves structure, and feeds into the curation layer. Must be robust and extensible — every future vertical flows through this pipeline.

**Deliverables:**
- Document type detection and routing
- Text extraction for each supported format
- Structure preservation (headings, sections, tables, lists)
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
- Tunable depth parameter (applicability check → full audit)
- Multi-step reasoning for complex regulatory queries
- Hallucination guardrails (no unsupported assertions)
- Context window management strategy

---

### `phase1/citation-provenance`

End-to-end citation provenance from source document → section → version → ingestion timestamp → agent response. Every answer must carry its audit trail. This is a non-negotiable.

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
    └──> Phase 0 research branches (ALL parallelizable)
              └──> phase0/first-vertical-corpus-acquisition
                        └──> phase1/ingestion-pipeline
                                  └──> phase1/curation-enrichment
                                            └──> phase1/semantic-chunking
                                                      └──> phase1/indexing-layer
                                                                └──> phase1/retrieval-engine
                                                                          └──> phase1/agent-core
                                                                                    └──> phase1/developer-api-alpha
```

### Parallel Work Opportunities

**Phase 0:** All research branches (`research-retrieval-algorithms`, `research-chunking-strategies`, `research-repository-architecture`, `research-agent-framework`) can be worked simultaneously by different contributors. `evaluation-framework` and `first-vertical-corpus-acquisition` can also run in parallel.

**Phase 1:** Once `indexing-layer` lands, `citation-provenance` and `version-control-regulatory` can be developed alongside `retrieval-engine` and `agent-core`.

**Phase 2:** All vertical onboarding branches (`vertical-insurance`, `vertical-medical-gig`) can run in parallel once the Phase 1 pipeline is proven. Cross-corpus capabilities (`cross-corpus-comparison`, `gap-analysis-engine`, `rubric-quality-assessment`, `synthesis-output`) can also be developed in parallel.

---

## Branch Lifecycle

1. **Create** — Branch from `main` using naming convention `phase{N}/{component-name}`
2. **Develop** — Work the component per the deliverables listed above
3. **Test** — Validate against evaluation framework (Phase 1+)
4. **PR** — Submit pull request to `main` with documentation
5. **Review** — Peer review and approval
6. **Merge** — Squash merge to `main`

---

*v1.0 — Created 2026-02-13 — Frank & Candi*
