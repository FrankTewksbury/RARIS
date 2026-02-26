"""Tests for curation pipeline — quality gates and metadata extraction."""

from app.ingestion.base import ExtractedDocument, ExtractedSection
from app.ingestion.curation import (
    _detect_cross_references,
    _extract_effective_date,
    _run_quality_gates,
)


def _make_extracted(text: str = "A" * 200, title: str = "Test", sections: int = 1):
    secs = [
        ExtractedSection(id=f"sec-{i:03d}", heading=f"Section {i}", level=1, text=text)
        for i in range(sections)
    ]
    return ExtractedDocument(title=title, sections=secs, full_text=text, tables=[])


class TestEffectiveDateExtraction:
    def test_extracts_effective_date(self):
        text = "This regulation is effective January 1, 2025 and applies to all lenders."
        date = _extract_effective_date(text)
        assert date is not None
        assert "2025" in date

    def test_extracts_iso_date(self):
        text = "Published on 2024-06-15 in the Federal Register."
        date = _extract_effective_date(text)
        assert date == "2024-06-15"

    def test_no_date_returns_none(self):
        text = "This is a general regulatory overview."
        date = _extract_effective_date(text)
        assert date is None


class TestCrossReferenceDetection:
    def test_detects_cfr_references(self):
        text = "See 12 CFR 1026.37 for disclosure requirements."
        refs = _detect_cross_references(text)
        assert len(refs) > 0
        assert any("CFR" in r for r in refs)

    def test_detects_section_symbols(self):
        text = "As defined in § 1026.2(a)(1)."
        refs = _detect_cross_references(text)
        assert len(refs) > 0

    def test_detects_usc_references(self):
        text = "Pursuant to 15 U.S.C. § 1601."
        refs = _detect_cross_references(text)
        assert len(refs) > 0


class TestQualityGates:
    def test_all_gates_pass(self):
        doc = _make_extracted()
        gates = _run_quality_gates(doc, {}, "abc123")
        assert all(g["passed"] for g in gates.values())

    def test_empty_text_fails_completeness(self):
        doc = _make_extracted(text="Short", sections=1)
        gates = _run_quality_gates(doc, {}, "abc123")
        assert not gates["completeness"]["passed"]

    def test_no_title_fails_consistency(self):
        doc = _make_extracted(title="")
        gates = _run_quality_gates(doc, {}, "abc123")
        assert not gates["consistency"]["passed"]

    def test_garbled_text_fails_encoding(self):
        garbled = "\ufffd" * 100 + "A" * 200
        doc = _make_extracted(text=garbled)
        gates = _run_quality_gates(doc, {}, "abc123")
        assert not gates["encoding"]["passed"]

    def test_tiny_text_fails_size(self):
        doc = ExtractedDocument(
            title="T",
            sections=[ExtractedSection(id="s", heading="H", level=1, text="tiny")],
            full_text="tiny",
            tables=[],
        )
        gates = _run_quality_gates(doc, {}, "abc123")
        assert not gates["size"]["passed"]
