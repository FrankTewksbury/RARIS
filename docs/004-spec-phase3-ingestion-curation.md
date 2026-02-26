---
type: spec
created: 2026-02-25
source: claude-code
description: Phase 3 — Ingestion & Curation Engine, format adapters, semantic chunking, indexing
tags: [raris, phase3, spec, "#status/backlog", "#priority/important"]
---

# Phase 3 — Ingestion & Curation Engine Specification

## Overview

Phase 3 transforms raw acquired content from the staging layer into structured,
enriched, queryable knowledge. Ingestion and curation are unified — every document
passes through extraction, enrichment, validation, and approval before it becomes
queryable. The output is a hybrid-indexed corpus with full provenance chains.

---

## A. Internal Document Model

Every ingested document is normalized into a common representation regardless of
original format.

```python
class InternalDocument:
    id: str                       # doc-{manifest_id}-{source_id}
    manifest_id: str
    source_id: str
    staged_document_id: str

    # Extracted content
    title: str
    sections: list[Section]       # hierarchical section tree
    full_text: str                # concatenated plain text
    tables: list[Table]           # extracted tables
    metadata: DocumentMetadata

    # Curation state
    status: CurationStatus        # raw → enriched → validated → approved → indexed
    quality_score: float          # 0.0-1.0, set by quality gates
    curation_notes: list[str]
    curated_at: datetime | None
    curated_by: str | None

class Section:
    id: str                       # sec-001, sec-001-001 (nested)
    heading: str
    level: int                    # 1 = top-level, 2 = subsection, etc.
    text: str
    children: list[Section]
    parent_id: str | None

class Table:
    id: str
    caption: str | None
    headers: list[str]
    rows: list[list[str]]
    section_id: str | None        # which section contains this table

class DocumentMetadata:
    jurisdiction: str
    regulatory_body: str
    effective_date: str | None
    authority_level: str          # binding | advisory | informational
    document_type: str            # statute | regulation | guidance | standard | educational | guide
    applicability_scope: list[str]
    classification_tags: list[str]
    cross_references: list[str]   # resolved source IDs
    supersedes: list[str]
    superseded_by: list[str]
```

### Curation Status Flow

```
raw → enriched → validated → approved → indexed
 │        │          │           │          │
 │        │          │           │          └─ In hybrid index, queryable
 │        │          │           └─ Human or auto-approved
 │        │          └─ Passed all quality gates
 │        └─ Metadata extracted, relationships linked
 └─ Freshly ingested from adapter
```

---

## B. Ingestion Adapters

Each adapter implements a common interface and handles one format family.

### Adapter Interface

```python
from abc import ABC, abstractmethod

class IngestionAdapter(ABC):
    @abstractmethod
    async def ingest(self, staged_doc: StagedDocument) -> InternalDocument:
        """Transform a staged document into an InternalDocument."""
        ...

    @abstractmethod
    def supports(self, content_type: str) -> bool:
        """Return True if this adapter handles the given content type."""
        ...
```

### 1. HTML Adapter

- **Input:** `text/html` staged content
- **Processing:**
  - Strip boilerplate (navigation, footers, sidebars) using structural heuristics
  - Extract heading hierarchy (h1-h6) into Section tree
  - Extract tables into Table objects
  - Preserve lists, blockquotes, and definition lists
  - Extract internal links as potential cross-references
- **Libraries:** BeautifulSoup4, readability-lxml

### 2. PDF Adapter

- **Input:** `application/pdf` staged content
- **Processing:**
  - Extract text with layout preservation (column detection, reading order)
  - Identify heading hierarchy from font size/weight changes
  - Extract tables using cell boundary detection
  - Handle multi-column layouts common in regulatory documents
  - OCR fallback for scanned documents
- **Libraries:** pdfplumber, pytesseract (OCR fallback)

### 3. Legal XML Adapter

- **Input:** `application/xml`, `text/xml` staged content (USLM, Akoma Ntoso)
- **Processing:**
  - Parse native XML structure directly into Section tree
  - Map XML element types to document model (section, subsection, paragraph, table)
  - Extract cross-references from XML link elements
  - Preserve amendment history metadata
- **Libraries:** lxml

### 4. Guide Adapter

- **Input:** Structured guides (GSE seller/servicer guides, multi-chapter HTML)
- **Processing:**
  - Reconstruct chapter → section → subsection hierarchy
  - Handle numbered section systems (e.g., B3-4.1-01)
  - Preserve cross-chapter references
  - Extract policy requirements vs. commentary
- **Libraries:** BeautifulSoup4, custom parsers

### 5. Plaintext Adapter

- **Input:** `text/plain` fallback
- **Processing:**
  - Heuristic heading detection (ALL CAPS lines, numbered sections)
  - Paragraph segmentation by blank lines
  - Minimal structure extraction
- **Libraries:** Standard library

---

## C. Curation Pipeline

Applied to every `InternalDocument` after adapter extraction.

### Step 1: Metadata Extraction

- Auto-tag jurisdiction from source manifest entry
- Extract effective dates from document text (pattern matching + LLM)
- Determine applicability scope (which entities, products, or activities)
- Attribute to regulatory body from manifest

### Step 2: Relationship Linking

- Resolve cross-references from manifest `relationships` field
- Detect in-text citations to other regulatory sources (e.g., "See 12 CFR 1026.1")
- Validate supersession chains against manifest data
- Link to related documents in the same corpus

### Step 3: Deduplication

- Content hash comparison against existing indexed documents
- Semantic similarity check for near-duplicates (e.g., same regulation published on different sites)
- Flag duplicates for review rather than auto-removing

### Step 4: Quality Gates

| Gate | Check | Action on Failure |
|------|-------|-------------------|
| Completeness | No empty sections, minimum text length | Flag for review |
| Consistency | Metadata matches manifest entry | Auto-correct or flag |
| Structure | Sections properly nested, no orphans | Flag for review |
| Encoding | Valid UTF-8, no garbled text | Reject, re-acquire |
| Size | Document size within expected range | Flag if >3x or <0.1x expected |

### Step 5: Status Transition

- Documents passing all quality gates → `validated`
- Auto-approval for documents with quality_score ≥ 0.9 and no flags
- Manual approval queue for flagged documents
- Approved documents proceed to indexing

---

## D. Semantic Chunking

Regulatory text requires structure-aware chunking that preserves context.

### Chunking Strategy

- **Section-based splitting:** Each Section becomes one or more chunks
- **Size target:** 500-1000 tokens per chunk (tunable)
- **Overlap:** 50 tokens between adjacent chunks within the same section
- **Hierarchy preservation:** Each chunk retains its section path (e.g., "Title 12 > Part 1026 > Subpart E > §1026.37")
- **Cross-reference maintenance:** Chunks that contain cross-references store the resolved target chunk IDs

### Chunk Model

```python
class Chunk:
    id: str                       # chk-{doc_id}-{seq}
    document_id: str
    section_id: str
    section_path: str             # "Part 1026 > Subpart E > §1026.37(a)"
    text: str
    token_count: int
    position: int                 # ordinal position in document
    cross_references: list[str]   # chunk IDs this chunk references
    embedding: list[float] | None # populated during indexing
```

---

## E. Indexing Layer

Hybrid index supporting multiple retrieval strategies.

### Index Components

| Index | Technology | Purpose |
|-------|-----------|---------|
| **Dense vector** | pgvector (PostgreSQL extension) | Semantic similarity search |
| **Sparse lexical** | PostgreSQL full-text search (tsvector) | Keyword and exact phrase matching |
| **Metadata** | PostgreSQL JSONB + GIN index | Filtered search by jurisdiction, type, body |
| **Relationship graph** | PostgreSQL adjacency table | Cross-reference traversal |

### Embedding Model

- Default: OpenAI `text-embedding-3-large` (3072 dimensions)
- Configurable via `EMBEDDING_MODEL` env var
- Batch embedding with rate limiting
- Embedding cache to avoid re-computing on re-ingestion

---

## F. FastAPI Endpoint Specifications

| Method | Path | Description |
|--------|------|-------------|
| POST | `/api/ingestion/run` | Start ingestion for an acquisition run's staged documents |
| GET | `/api/ingestion/{id}` | Get ingestion run status |
| GET | `/api/ingestion/{id}/stream` | SSE stream of ingestion progress |
| GET | `/api/ingestion/{id}/documents` | List all documents with curation status |
| GET | `/api/documents/{doc_id}` | Get full document with sections and metadata |
| PATCH | `/api/documents/{doc_id}/approve` | Approve a document for indexing |
| PATCH | `/api/documents/{doc_id}/reject` | Reject a document, flag for re-acquisition |
| GET | `/api/index/stats` | Index health: total chunks, coverage, freshness |

---

## G. React UI — Curation Dashboard

### Components

#### 1. Ingestion Run Panel
- Select acquisition run to ingest
- "Start Ingestion" button
- Progress bar with per-format breakdown

#### 2. Document Pipeline View
- Kanban-style columns: Raw → Enriched → Validated → Approved → Indexed
- Document cards with source name, type, quality score
- Drag to approve or filter by status

#### 3. Quality Gate Results
- Per-document breakdown of gate pass/fail
- Expandable details showing specific failures
- Bulk approve for documents passing all gates

#### 4. Document Viewer
- Full document view with section tree navigation
- Highlighted cross-references (clickable)
- Metadata panel with extracted fields
- Chunk boundaries visualized in the text

#### 5. Index Health Panel
- Total documents and chunks indexed
- Coverage by jurisdiction and document type
- Embedding freshness (time since last re-index)
- Search quality sampling (random queries with relevance scores)

---

## H. Acceptance Criteria

- [ ] All 5 ingestion adapters (HTML, PDF, Legal XML, Guide, Plaintext) implemented and tested
- [ ] Curation pipeline enriches documents with metadata, relationships, and quality scores
- [ ] Quality gates catch at least 3 known failure modes (empty sections, encoding issues, size anomalies)
- [ ] Semantic chunking preserves section hierarchy and cross-references
- [ ] Hybrid index (vector + lexical + metadata) supports combined queries
- [ ] Insurance corpus fully ingested, curated, and indexed
- [ ] Curation Dashboard shows document pipeline status and quality gate results
- [ ] ≥95% of staged documents successfully ingested (Ingestion Success metric)
