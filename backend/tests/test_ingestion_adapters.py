"""Tests for ingestion adapters."""

import pytest

from app.ingestion.guide_adapter import GuideAdapter
from app.ingestion.html_adapter import HtmlAdapter
from app.ingestion.pdf_adapter import PdfAdapter
from app.ingestion.plaintext_adapter import PlaintextAdapter
from app.ingestion.registry import get_adapter
from app.ingestion.xml_adapter import XmlAdapter


@pytest.fixture
def sample_html():
    return """
    <html>
    <head><title>Test Regulation</title></head>
    <body>
        <nav>Skip this</nav>
        <h1>PART 1026 — TRUTH IN LENDING</h1>
        <p>This regulation implements the Truth in Lending Act.</p>
        <h2>Subpart A — General</h2>
        <p>Section 1026.1 Authority, purpose, coverage, organization.</p>
        <h3>§ 1026.2 Definitions</h3>
        <p>As used in this part, effective January 1, 2025:</p>
        <table>
            <thead><tr><th>Term</th><th>Definition</th></tr></thead>
            <tbody>
                <tr><td>Creditor</td><td>A person who regularly extends credit.</td></tr>
                <tr><td>Consumer</td><td>A natural person.</td></tr>
            </tbody>
        </table>
        <a href="https://example.com/cfr">See 12 CFR 1026</a>
        <footer>Government footer</footer>
    </body>
    </html>
    """


@pytest.fixture
def sample_xml():
    return """<?xml version="1.0"?>
    <document>
        <title>Sample Regulation</title>
        <section>
            <heading>Part 100</heading>
            <content>This is the main content.</content>
            <section>
                <heading>Subpart A</heading>
                <content>Subpart content here.</content>
            </section>
        </section>
    </document>
    """


@pytest.fixture
def sample_plaintext():
    return """TITLE 12 — BANKS AND BANKING

PART 1026 — TRUTH IN LENDING

GENERAL PROVISIONS

Section 1026.1 Authority.
This regulation implements the Truth in Lending Act (15 U.S.C. 1601 et seq.).

DEFINITIONS AND RULES OF CONSTRUCTION

Section 1026.2 Definitions.
As used in this part:
(a) Creditor means a person who regularly extends credit.
(b) Consumer means a natural person.
"""


class TestHtmlAdapter:
    @pytest.mark.asyncio
    async def test_supports(self):
        adapter = HtmlAdapter()
        assert adapter.supports("text/html")
        assert adapter.supports("text/html; charset=utf-8")
        assert not adapter.supports("application/pdf")

    @pytest.mark.asyncio
    async def test_ingest_extracts_title(self, sample_html):
        adapter = HtmlAdapter()
        doc = await adapter.ingest(sample_html)
        assert doc.title == "Test Regulation"

    @pytest.mark.asyncio
    async def test_ingest_extracts_sections(self, sample_html):
        adapter = HtmlAdapter()
        doc = await adapter.ingest(sample_html)
        assert len(doc.sections) > 0
        headings = [s.heading for s in doc.sections]
        assert any("PART 1026" in h for h in headings)

    @pytest.mark.asyncio
    async def test_ingest_extracts_tables(self, sample_html):
        adapter = HtmlAdapter()
        doc = await adapter.ingest(sample_html)
        assert len(doc.tables) == 1
        assert doc.tables[0].headers == ["Term", "Definition"]
        assert len(doc.tables[0].rows) == 2

    @pytest.mark.asyncio
    async def test_ingest_strips_boilerplate(self, sample_html):
        adapter = HtmlAdapter()
        doc = await adapter.ingest(sample_html)
        assert "Skip this" not in doc.full_text
        assert "Government footer" not in doc.full_text

    @pytest.mark.asyncio
    async def test_ingest_extracts_cross_references(self, sample_html):
        adapter = HtmlAdapter()
        doc = await adapter.ingest(sample_html, source_url="https://law.gov")
        assert "https://example.com/cfr" in doc.cross_references


class TestXmlAdapter:
    @pytest.mark.asyncio
    async def test_supports(self):
        adapter = XmlAdapter()
        assert adapter.supports("application/xml")
        assert adapter.supports("text/xml")
        assert not adapter.supports("text/html")

    @pytest.mark.asyncio
    async def test_ingest_generic_xml(self, sample_xml):
        adapter = XmlAdapter()
        doc = await adapter.ingest(sample_xml)
        assert doc.title == "Sample Regulation"
        assert len(doc.full_text) > 0


class TestPlaintextAdapter:
    @pytest.mark.asyncio
    async def test_supports(self):
        adapter = PlaintextAdapter()
        assert adapter.supports("text/plain")
        assert not adapter.supports("text/html")

    @pytest.mark.asyncio
    async def test_ingest_builds_sections(self, sample_plaintext):
        adapter = PlaintextAdapter()
        doc = await adapter.ingest(sample_plaintext)
        assert len(doc.sections) > 0
        assert doc.title.startswith("TITLE 12")

    @pytest.mark.asyncio
    async def test_ingest_full_text(self, sample_plaintext):
        adapter = PlaintextAdapter()
        doc = await adapter.ingest(sample_plaintext)
        assert "Truth in Lending Act" in doc.full_text


class TestRegistry:
    def test_html_routing(self):
        adapter = get_adapter("text/html")
        assert isinstance(adapter, HtmlAdapter)

    def test_pdf_routing(self):
        adapter = get_adapter("application/pdf")
        assert isinstance(adapter, PdfAdapter)

    def test_xml_routing(self):
        adapter = get_adapter("application/xml")
        assert isinstance(adapter, XmlAdapter)

    def test_plaintext_fallback(self):
        adapter = get_adapter("text/plain")
        assert isinstance(adapter, PlaintextAdapter)

    def test_guide_format_override(self):
        adapter = get_adapter("text/html", source_format="guide")
        assert isinstance(adapter, GuideAdapter)

    def test_legal_xml_format_override(self):
        adapter = get_adapter("text/html", source_format="legal_xml")
        assert isinstance(adapter, XmlAdapter)
