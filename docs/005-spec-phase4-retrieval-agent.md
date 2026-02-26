---
type: spec
created: 2026-02-25
source: claude-code
description: Phase 4 — Retrieval Engine, Agent Core, citation provenance, cross-corpus analysis
tags: [raris, phase4, spec, "#status/backlog", "#priority/important"]
---

# Phase 4 — Retrieval & Agent Layer Specification

## Overview

Phase 4 is the intelligence layer. It provides agent-based retrieval with tunable
depth, full citation provenance, cross-corpus analysis, and a developer API. Every
claim in an agent response traces back through a citation chain:
response → chunk → document → source → manifest.

---

## A. Retrieval Engine

### Hybrid Search Pipeline

```
User Query
    │
    ├──▶ Dense Search (pgvector)      → top-K by cosine similarity
    ├──▶ Sparse Search (tsvector)     → top-K by BM25 relevance
    └──▶ Metadata Filter (JSONB)      → jurisdiction, type, body constraints
              │
              ▼
        Reciprocal Rank Fusion (RRF)
              │
              ▼
        Re-Ranking (LLM or cross-encoder)
              │
              ▼
        Scored Results with provenance
```

### Search Parameters

```python
class SearchRequest:
    query: str                           # Natural language query
    filters: SearchFilters | None        # Optional metadata filters
    top_k: int = 20                      # Number of results
    search_mode: SearchMode = "hybrid"   # hybrid | semantic | lexical
    rerank: bool = True                  # Apply LLM re-ranking

class SearchFilters:
    jurisdiction: list[str] | None       # ["federal", "state"]
    document_type: list[str] | None      # ["statute", "regulation"]
    regulatory_body: list[str] | None    # ["naic", "cms"]
    authority_level: list[str] | None    # ["binding"]
    date_range: tuple[str, str] | None   # (start_date, end_date)
    tags: list[str] | None              # classification tags

class SearchResult:
    chunk_id: str
    document_id: str
    source_id: str
    manifest_id: str
    section_path: str                    # "Part 1026 > §1026.37(a)"
    text: str                           # chunk text
    score: float                        # combined relevance score
    provenance: CitationChain           # full provenance chain
```

### Reciprocal Rank Fusion

```python
def rrf_score(dense_rank: int, sparse_rank: int, k: int = 60) -> float:
    return 1 / (k + dense_rank) + 1 / (k + sparse_rank)
```

### Re-Ranking

- LLM-based relevance scoring: given query + chunk, score 0-10
- Cross-encoder model as alternative (faster, cheaper for high-volume)
- Configurable via `RERANK_METHOD` env var: `llm` | `cross-encoder` | `none`

---

## B. Agent Core

The orchestrating agent that plans retrieval strategy, executes queries,
synthesizes results, and threads citations.

### Response Depth Levels

| Level | Name | Description | Token Budget |
|-------|------|-------------|-------------|
| 1 | Quick Check | Yes/no applicability with top citation | ~200 |
| 2 | Summary | Key points with supporting citations | ~500 |
| 3 | Analysis | Detailed analysis with full citation chains | ~1500 |
| 4 | Exhaustive | Comprehensive regulatory audit, all sources | ~4000 |

### Agent Pipeline

```
User Query + Depth Level
         │
         ▼
  ┌──────────────┐
  │ Query Planner │ ─── Decomposes complex queries into sub-queries
  └──────┬───────┘
         │
         ▼
  ┌──────────────┐
  │ Retrieval     │ ─── Executes search(es) against hybrid index
  │ Executor      │     May run multiple searches for complex queries
  └──────┬───────┘
         │
         ▼
  ┌──────────────┐
  │ Evidence      │ ─── Groups and evaluates retrieved chunks
  │ Assembler     │     Identifies gaps, redundancies
  └──────┬───────┘
         │
         ▼
  ┌──────────────┐
  │ Response      │ ─── Synthesizes answer at requested depth
  │ Synthesizer   │     Threads inline citations
  └──────┬───────┘
         │
         ▼
  ┌──────────────┐
  │ Citation      │ ─── Validates and formats citation chains
  │ Validator     │     Ensures every claim has provenance
  └──────────────┘
         │
         ▼
  Cited Response
```

### Agent System Prompt (Template)

```
You are a regulatory analysis agent. Answer the user's query using ONLY the
retrieved regulatory sources provided below. Every factual claim must include
an inline citation in the format [SOURCE_ID §section].

Depth level: {depth_level}
{depth_instructions}

Retrieved sources:
{retrieved_chunks}

Rules:
- Never fabricate regulatory content
- If retrieved sources don't cover the query, say so explicitly
- Flag conflicting sources and note the conflict
- Distinguish binding authority from advisory guidance
```

---

## C. Citation Provenance

Every claim traces through the full chain.

### Citation Chain Model

```python
class CitationChain:
    chunk_id: str                 # The specific chunk cited
    chunk_text: str               # Relevant excerpt
    section_path: str             # "12 CFR 1026 > Subpart E > §1026.37(a)"
    document_id: str              # Internal document ID
    document_title: str
    source_id: str                # Manifest source ID
    source_url: str               # Original URL
    regulatory_body: str
    jurisdiction: str
    authority_level: str          # binding | advisory | informational
    manifest_id: str
    confidence: float             # Source confidence from manifest
```

### Inline Citation Format

```
The lender must provide a Loan Estimate within three business days of receiving
a completed application [src-001 §1026.19(e)(1)(iii)]. This requirement applies
to all consumer-purpose mortgage loans [src-001 §1026.1(c)], with limited
exceptions for certain types of credit [src-001 §1026.3].
```

---

## D. Cross-Corpus Analysis

Compare documents, policies, or requirements across regulatory sources.

### Analysis Types

| Type | Input | Output |
|------|-------|--------|
| Gap Analysis | Policy document + regulatory corpus | Missing compliance areas |
| Conflict Detection | Two regulatory sources | Conflicting requirements |
| Coverage Mapping | Domain description + corpus | Coverage score + gaps |
| Change Impact | Updated regulation + existing corpus | Affected documents |

### Analysis Request

```python
class AnalysisRequest:
    analysis_type: str            # gap | conflict | coverage | change_impact
    primary_document: str         # Document ID or uploaded text
    comparison_scope: SearchFilters  # Which corpus segments to compare against
    depth: int = 3               # Analysis depth level
```

### Analysis Response

```python
class AnalysisResponse:
    findings: list[Finding]
    summary: str
    coverage_score: float | None
    citations: list[CitationChain]

class Finding:
    category: str                 # gap | conflict | coverage | impact
    severity: str                 # high | medium | low
    description: str
    primary_citation: CitationChain
    comparison_citation: CitationChain | None
    recommendation: str
```

---

## E. Developer API

REST API for programmatic access to retrieval and analysis.

### Endpoints

| Method | Path | Description |
|--------|------|-------------|
| POST | `/api/query` | Submit a query with depth and filters |
| GET | `/api/query/{id}` | Get query result (for async queries) |
| POST | `/api/query/stream` | SSE stream for real-time response generation |
| POST | `/api/analysis` | Submit a cross-corpus analysis request |
| GET | `/api/analysis/{id}` | Get analysis result |
| GET | `/api/corpus/stats` | Corpus statistics (documents, chunks, coverage) |
| GET | `/api/corpus/sources` | List indexed sources with metadata |
| GET | `/api/citations/{chunk_id}` | Get full citation chain for a chunk |

### Authentication

- API key authentication via `Authorization: Bearer <key>` header
- Rate limiting: configurable per key (default 60 requests/minute)
- Usage tracking per key

---

## F. React UI — Query Interface

### Components

#### 1. Query Input
- Natural language text area
- Depth selector: Quick Check / Summary / Analysis / Exhaustive
- Filter panel: jurisdiction, document type, regulatory body, date range
- "Ask" button with streaming response

#### 2. Response Panel
- Streaming response with inline citations (highlighted, clickable)
- Depth indicator showing current level
- Token usage counter
- Copy and export buttons

#### 3. Citation Explorer
- Click any inline citation to expand the full chain
- Shows: chunk text → section path → document → source → manifest
- "View in context" button to see the chunk within its full document

#### 4. Sources Panel
- List of all sources cited in the response
- Grouped by regulatory body
- Authority level indicators (binding vs advisory)
- Link to original source URL

#### 5. Analysis View
- Upload or select primary document for comparison
- Select analysis type and comparison scope
- Findings table with severity badges
- Side-by-side citation comparison

---

## G. Evaluation Framework Extensions

### Retrieval Metrics

| Metric | Target | Description |
|--------|--------|-------------|
| Precision@10 | ≥0.80 | Fraction of top-10 results that are relevant |
| Recall@20 | ≥0.90 | Fraction of relevant results in top-20 |
| MRR | ≥0.70 | Mean Reciprocal Rank of first relevant result |
| Citation Accuracy | ≥0.95 | Fraction of citations pointing to correct source |
| Response Faithfulness | ≥0.95 | Fraction of claims supported by cited sources |

### Evaluation Harness

- Ground truth query-answer pairs for Insurance domain
- Automated scoring using LLM-as-judge for relevance and faithfulness
- A/B comparison across LLM providers and retrieval configurations

---

## H. Acceptance Criteria

- [ ] Hybrid retrieval returns accurate results with Precision@10 ≥ 0.80
- [ ] Agent produces responses at all 4 depth levels with appropriate detail
- [ ] Every factual claim has a valid citation chain (response → chunk → document → source)
- [ ] Cross-corpus analysis identifies gaps and conflicts between regulatory sources
- [ ] Developer API serves queries with authentication and rate limiting
- [ ] Query Interface streams responses with clickable inline citations
- [ ] Citation Accuracy ≥ 0.95 on Insurance domain evaluation set
- [ ] Response Faithfulness ≥ 0.95 (no unsupported claims)
