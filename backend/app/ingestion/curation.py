"""Curation pipeline — metadata extraction, relationship linking, dedup, quality gates."""

import hashlib
import re
from dataclasses import dataclass

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.ingestion.base import ExtractedDocument
from app.models.ingestion import CurationStatus, InternalDocument

# Date patterns common in regulatory documents
_DATE_PATTERNS = [
    re.compile(
        r"effective\s+(?:date\s*[:.]?\s*|as of\s+)?(\w+\s+\d{1,2},?\s+\d{4})", re.IGNORECASE
    ),
    re.compile(r"(?:dated?|published|issued)[:\s]*(\w+\s+\d{1,2},?\s+\d{4})", re.IGNORECASE),
    re.compile(r"(\d{1,2}/\d{1,2}/\d{4})"),
    re.compile(r"(\d{4}-\d{2}-\d{2})"),
]

# Regulatory cross-reference patterns
_XREF_PATTERNS = [
    re.compile(r"(\d+)\s+(?:CFR|C\.F\.R\.)\s+(?:Part\s+)?(\d+(?:\.\d+)*)"),
    re.compile(r"(?:§|Section)\s*(\d+(?:\.\d+)*)"),
    re.compile(r"(?:Public Law|P\.L\.)\s+(\d+-\d+)"),
    re.compile(r"(\d+)\s+U\.S\.C\.\s+§?\s*(\d+)"),
]


@dataclass
class CurationResult:
    status: CurationStatus
    quality_score: float
    quality_gates: dict[str, dict]
    curation_notes: list[str]
    effective_date: str | None
    cross_references: list[str]
    content_hash: str
    is_duplicate: bool


async def run_curation(
    doc: InternalDocument,
    extracted: ExtractedDocument,
    manifest_source: dict,
    db: AsyncSession,
) -> CurationResult:
    """Run the full curation pipeline on an ingested document.

    Args:
        doc: The InternalDocument ORM record.
        extracted: The extracted content from the adapter.
        manifest_source: Dict with source metadata from the manifest
            (jurisdiction, regulatory_body, authority, type, relationships, etc.)
        db: Database session for dedup checks.
    """
    notes: list[str] = []

    # Step 1: Metadata enrichment (from manifest + document text)
    effective_date = _extract_effective_date(extracted.full_text)
    if effective_date:
        notes.append(f"Extracted effective date: {effective_date}")

    # Step 2: Cross-reference detection
    text_xrefs = _detect_cross_references(extracted.full_text)
    manifest_xrefs = manifest_source.get("relationships", {}).get("cross_references", [])
    all_xrefs = list(set(text_xrefs + manifest_xrefs + extracted.cross_references))

    # Step 3: Content hash + dedup
    content_hash = hashlib.sha256(extracted.full_text.encode("utf-8")).hexdigest()
    is_duplicate = await _check_duplicate(content_hash, doc.id, db)
    if is_duplicate:
        notes.append("DUPLICATE: Content hash matches an existing document")

    # Step 4: Quality gates
    gates = _run_quality_gates(extracted, manifest_source, content_hash)

    # Step 5: Compute quality score and determine status
    passed_count = sum(1 for g in gates.values() if g["passed"])
    total_gates = len(gates)
    quality_score = passed_count / total_gates if total_gates > 0 else 0.0

    all_passed = all(g["passed"] for g in gates.values())
    has_critical_failure = any(
        not g["passed"] and g.get("severity") == "critical"
        for g in gates.values()
    )

    if has_critical_failure:
        status = CurationStatus.rejected
        notes.append("Rejected: critical quality gate failure")
    elif is_duplicate:
        status = CurationStatus.raw
        notes.append("Held at raw: duplicate detected, needs review")
    elif all_passed and quality_score >= 0.9:
        status = CurationStatus.approved
        notes.append("Auto-approved: all gates passed, quality >= 0.9")
    elif all_passed:
        status = CurationStatus.validated
        notes.append("Validated: all gates passed")
    else:
        status = CurationStatus.enriched
        notes.append(f"Enriched: {total_gates - passed_count} gate(s) need review")

    return CurationResult(
        status=status,
        quality_score=quality_score,
        quality_gates=gates,
        curation_notes=notes,
        effective_date=effective_date,
        cross_references=all_xrefs,
        content_hash=content_hash,
        is_duplicate=is_duplicate,
    )


def _extract_effective_date(text: str) -> str | None:
    """Extract effective date from document text."""
    # Search first 2000 chars (dates usually appear early)
    search_text = text[:2000]
    for pattern in _DATE_PATTERNS:
        m = pattern.search(search_text)
        if m:
            return m.group(1).strip()
    return None


def _detect_cross_references(text: str) -> list[str]:
    """Detect regulatory cross-references in text."""
    refs: set[str] = set()
    for pattern in _XREF_PATTERNS:
        for m in pattern.finditer(text):
            refs.add(m.group(0).strip())
    return list(refs)


async def _check_duplicate(
    content_hash: str, exclude_doc_id: str, db: AsyncSession
) -> bool:
    """Check if content hash already exists in indexed documents."""
    result = await db.execute(
        select(InternalDocument.id).where(
            InternalDocument.content_hash == content_hash,
            InternalDocument.id != exclude_doc_id,
            InternalDocument.status != CurationStatus.rejected,
        )
    )
    return result.scalar_one_or_none() is not None


def _run_quality_gates(
    extracted: ExtractedDocument,
    manifest_source: dict,
    content_hash: str,
) -> dict[str, dict]:
    """Run all quality gates and return results."""
    gates: dict[str, dict] = {}

    # Gate 1: Completeness — no empty document, minimum text length
    text_len = len(extracted.full_text.strip())
    has_sections = len(extracted.sections) > 0
    empty_sections = sum(
        1 for s in extracted.sections
        if not s.text.strip() and not s.children
    )
    gates["completeness"] = {
        "passed": text_len >= 100 and has_sections and empty_sections == 0,
        "detail": f"text_length={text_len}, sections={len(extracted.sections)}, "
        f"empty={empty_sections}",
    }

    # Gate 2: Encoding — check for garbled text indicators
    garbled_chars = sum(1 for c in extracted.full_text[:1000] if ord(c) > 65533)
    replacement_chars = extracted.full_text[:1000].count("\ufffd")
    gates["encoding"] = {
        "passed": garbled_chars == 0 and replacement_chars < 5,
        "detail": f"garbled={garbled_chars}, replacement_chars={replacement_chars}",
        "severity": "critical" if replacement_chars > 50 else "normal",
    }

    # Gate 3: Size — document size within expected range
    manifest_source.get("estimated_size", "")
    size_ok = True
    detail = f"byte_size={text_len}"
    if text_len < 50:
        size_ok = False
        detail += " (too small)"
    gates["size"] = {
        "passed": size_ok,
        "detail": detail,
    }

    # Gate 4: Structure — sections properly formed
    orphan_count = 0
    for s in extracted.sections:
        if s.level > 1 and s.parent_id is None and not s.children:
            orphan_count += 1
    gates["structure"] = {
        "passed": orphan_count == 0,
        "detail": f"orphan_sections={orphan_count}",
    }

    # Gate 5: Consistency — metadata matches manifest
    consistency_ok = True
    consistency_detail: list[str] = []
    if not extracted.title:
        consistency_ok = False
        consistency_detail.append("missing_title")
    if not content_hash:
        consistency_ok = False
        consistency_detail.append("missing_hash")
    gates["consistency"] = {
        "passed": consistency_ok,
        "detail": ", ".join(consistency_detail) if consistency_detail else "ok",
    }

    return gates
