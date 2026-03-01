---
type: project-proposal
project: RORI
version: 0.1-draft
created: 2026-02-13
status: draft-for-review
authors: [Frank, Candi]
---

# RORI — Research On Regulatory for Industry(s)

## Project Proposal — Draft for Review

---

## 1. Executive Summary

RORI is a general-purpose regulatory research and analysis engine designed to ingest, curate, and reason over large corpuses of regulatory, compliance, and policy data across industries and jurisdictions. The platform provides agent-based retrieval with tunable depth and completeness, enabling users and downstream AI systems to accurately retrieve, compare, and synthesize regulatory intelligence without reliance on web scraping.

The core thesis is simple: regulatory data is vast, fragmented, constantly evolving, and buried across thousands of sources with wildly different formats and semantics. No single AI model can reliably internalize all of it. RORI solves this by building a curated, auditable knowledge layer that agents can query with precision — and that humans can trust.

---

## 2. Problem Statement

Organizations across industries face a common challenge: regulatory and compliance information is scattered across federal, state, and municipal sources in disparate formats — PDFs, legal text, guidance documents, seller/servicer guides, directives, and standards. The cost of manual research is high, the risk of missing applicable regulations is real, and the pace of regulatory change makes point-in-time snapshots unreliable.

Existing approaches fall short in several ways:

- **Web scraping** is brittle, legally gray, and produces noisy results that degrade AI inference quality.
- **General-purpose LLMs** hallucinate regulatory specifics, lack citation provenance, and cannot be audited.
- **Static document repositories** require manual curation and don't support semantic reasoning, gap analysis, or cross-corpus comparison.

RORI addresses these gaps by creating a purpose-built regulatory knowledge platform with curated ingestion, structured indexing, agent-based retrieval, and auditability at every layer.

---

## 3. Vision and Product Scope

### 3.1 What RORI Is

A platform that enables three primary capabilities:

**Curated Ingestion and Repository Management** — Ingest large, heterogeneous corpuses of regulatory data (statutes, rules, guidance, standards, educational materials) into a structured, semantically indexed repository. The data will be of disparate types, categories, and semantics. The ingestion and curation pipeline is foundational — accuracy of the agent depends entirely on the quality of what it has to work with.

**Agent-Based Retrieval with Tunable Precision** — An agentic query layer that retrieves regulatory information with guaranteed accuracy, but allows the caller to dial the completeness and depth of response based on circumstance. A quick applicability check and a full regulatory audit require different levels of exhaustiveness — the agent should handle both.

**Cross-Corpus Analysis and Synthesis** — The ability to compare, gap-analyze, and synthesize across two or more corpuses of data, producing well-defined plans and actionable findings. Examples include comparing a new cyber directive against NIST standards, or quality-checking work product against a requirements rubric.

### 3.2 Primary Use Modalities

**Agent-as-Platform (Primary)** — RORI is an agent-based platform first. The core value is the agent's ability to reason over curated regulatory data and return accurate, citable, auditable answers.

**Developer Integration** — Developers incorporate RORI's agent into their own AI agentic workflows to retrieve regulations specific to an industry, region, and circumstance. RORI serves as a reliable context source within a broader AI inference pipeline — a structured alternative to web scraping.

**Packaged End-User Applications** — The agent is paired with a front-end and pre-configured for specific use cases: document comparison, compliance gap analysis, rubric-based quality checks, or regulatory research assistants for specific industries.

### 3.3 Illustrative Industry Verticals (Staged Rollout)

The platform is industry-agnostic by design, but will be validated through progressively complex verticals:

1. **Mortgage / First-Time Homebuyers** — Federal and state mortgage regulations, CFPB guidance, GSE (Fannie Mae, Freddie Mac) seller/servicer guides, educational material for first-time buyers.
2. **Insurance (Broker/Agent Focus)** — Insurance regulation across US states, focused on brokers and agents generating comprehensive coverage proposals. Highly jurisdictional, requiring state-by-state mapping.
3. **Medical / Gig Platforms for Clinicians** — Regulations impacting gig-work platforms that connect clinicians with healthcare opportunities. Intersection of labor law, medical licensing, telehealth regulations, and platform compliance.
4. **Fine-Grained Expansion** — As the agent proves out, extend into progressively granular regulatory domains — potentially as deep as municipal building codes, local zoning ordinances, or industry-specific sub-regulatory guidance.

---

## 4. Core Principles and Non-Negotiables

These principles govern every architectural and product decision:

**Accuracy** — The agent must be correct. Regulatory information cannot be "mostly right." Every response must be traceable to its source material. Hallucination is a disqualifying failure mode.

**Consistency** — The same query against the same corpus must produce the same result. Stochastic variation in retrieval is unacceptable for regulatory use cases. Results must be repeatable and deterministic enough to withstand audit.

**Completeness** — The agent must know what it knows and what it doesn't. When asked for all applicable regulations, it must be able to confidently enumerate them — or clearly flag gaps in coverage. Partial answers must be labeled as such.

**Auditability** — Every answer must carry provenance: which source documents, which sections, which version, when ingested, when last verified. This platform must be defensible under regulatory scrutiny.

**Tunability** — Not every query requires the same depth. The platform must support a spectrum from lightweight applicability checks to exhaustive regulatory audits, controlled by the caller.

---

## 5. Critical Areas of Focus

### 5.1 Ingestion and Curation Pipeline

This is the foundation. Without high-quality, well-structured data in the repository, the agent cannot perform. Key challenges:

- Handling disparate document types (PDFs, HTML, legal XML, structured guides, unstructured guidance letters)
- Semantic chunking that preserves regulatory context, hierarchy, and cross-references
- Metadata extraction and enrichment (jurisdiction, effective dates, applicability, supersession chains)
- Version control and change tracking for living regulatory documents
- Deduplication and conflict resolution across overlapping sources
- Quality gates and validation for ingested data

### 5.2 Indexing and Retrieval Architecture

The retrieval layer must achieve accuracy and repeatability that can stand up to audit and regulatory scrutiny. This demands research into the latest algorithms and techniques:

- Hybrid retrieval strategies (dense vector search + sparse/lexical search + structured metadata filtering)
- Advanced chunking strategies optimized for legal and regulatory text (hierarchical, overlapping, section-aware)
- Re-ranking models tuned for regulatory precision
- Citation-grounded generation — the agent should never produce a claim it cannot cite
- Confidence scoring and coverage estimation
- Deterministic retrieval modes for audit repeatability
- Graph-based representations for regulatory relationships (supersession, dependency, applicability hierarchies)

### 5.3 Agent Architecture

The agent layer orchestrates retrieval, reasoning, and synthesis:

- Agentic orchestration framework selection (tool-use patterns, planning, self-correction)
- Tunable response depth (quick lookup vs. exhaustive analysis)
- Multi-step reasoning for gap analysis and cross-corpus comparison
- Source attribution and citation threading throughout the response chain
- Guardrails against hallucination and unsupported assertions
- Context window management for large regulatory corpuses

### 5.4 Cross-Corpus Analysis and Synthesis

A differentiating capability — not just retrieval, but comparative reasoning:

- Document-to-document comparison (directive vs. standard, policy vs. requirement)
- Gap analysis engines (what's required vs. what's covered)
- Rubric-based quality assessment
- Synthesis into structured output (compliance plans, gap reports, requirement matrices)

### 5.5 Developer Integration and API Surface

RORI as a building block for other AI systems:

- Clean API surface for agent invocation with tunable parameters
- Context manifold integration — providing structured regulatory context to external AI inference engines
- SDK or integration patterns for common agentic frameworks
- Rate limiting, access control, and usage metering

### 5.6 Multilingual Support (Stage 2)

Regulatory data is not English-only. Stage 2 must address:

- Multilingual ingestion and indexing
- Cross-language retrieval (query in one language, retrieve from another)
- Translation-aware semantic matching
- Jurisdiction-language mapping

---

## 6. Staged Delivery Approach

### Stage 0 — Foundation and Research
- Deep research into state-of-the-art indexing, retrieval, and RAG techniques for legal/regulatory text
- Architecture decision records for repository type, chunking strategy, retrieval approach
- Define evaluation framework for accuracy, consistency, and completeness
- Scaffold the project structure and development workflow

### Stage 1 — Core Engine (Single Vertical)
- Build ingestion and curation pipeline (first vertical: Mortgage/Homebuyer)
- Implement core indexing and retrieval architecture
- Build agent layer with tunable depth
- Validate accuracy, consistency, and auditability against the first corpus
- Developer API surface (alpha)

### Stage 2 — Multi-Vertical and Advanced Capabilities
- Onboard second and third verticals (Insurance, Medical/Gig)
- Cross-corpus comparison and gap analysis
- Multilingual support
- Packaged end-user application(s)
- Hardened API and integration patterns

### Stage 3 — Scale and Fine-Grained Expansion
- Fine-grained regulatory domains (municipal codes, sub-regulatory guidance)
- Performance optimization at scale
- Advanced agent capabilities (proactive regulatory change monitoring, impact analysis)
- Marketplace or plug-in model for vertical-specific configurations

---

## 7. Open Questions and Research Needs

These must be resolved in Stage 0:

1. **Repository architecture** — Vector DB, knowledge graph, hybrid? What combination of storage and indexing best serves regulatory data with complex hierarchical relationships?
2. **Chunking strategy** — What chunking approaches preserve the semantic integrity of regulatory text (which is heavily cross-referential and hierarchical)?
3. **Retrieval algorithms** — What is the current state of the art for high-precision retrieval over legal/regulatory text? How do we achieve audit-grade repeatability?
4. **Evaluation methodology** — How do we rigorously measure accuracy, completeness, and consistency? What benchmarks exist for regulatory retrieval?
5. **Agent framework** — Which agentic orchestration patterns best support tunable depth and multi-step regulatory reasoning?
6. **Provenance and citation** — What are best practices for maintaining end-to-end citation provenance from source document through to agent response?
7. **Regulatory change management** — How do we handle the continuous evolution of regulatory documents? Version tracking, supersession, effective date management?

---

## 8. Success Criteria

- Agent retrieval accuracy measurably exceeds general-purpose LLM baselines on regulatory queries
- Results are repeatable — same query, same corpus, same answer
- Every claim in an agent response is traceable to a specific source, section, and version
- Cross-corpus gap analysis produces actionable, structured output
- Developer integration is clean enough to serve as a context source in third-party AI pipelines
- The system can withstand a simulated audit of its retrieval provenance

---

## 9. What This Document Is Not

This is not a technical architecture document, a sprint plan, or a detailed requirements specification. Those will follow. This is the project proposal — the "why," the "what," and the boundaries of the problem space. It is intended to align stakeholders, frame the research agenda, and provide a foundation for the architectural decisions that come next.

---

*Draft v0.1 — Created 2026-02-13 — For review and iteration before formal document production.*
