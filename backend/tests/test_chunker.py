"""Tests for semantic chunker."""


from app.ingestion.base import ExtractedSection
from app.ingestion.chunker import chunk_document, count_tokens


class TestChunker:
    def test_single_small_section(self):
        sections = [
            ExtractedSection(
                id="sec-000",
                heading="Introduction",
                level=1,
                text="This is a short introduction to the regulation.",
            )
        ]
        chunks = chunk_document(sections, "doc-test", min_tokens=5, max_tokens=100)
        assert len(chunks) == 1
        assert chunks[0].section_path == "Introduction"
        assert chunks[0].token_count > 0

    def test_large_section_splits(self):
        long_text = "This is a test sentence. " * 200
        sections = [
            ExtractedSection(
                id="sec-000",
                heading="Long Section",
                level=1,
                text=long_text,
            )
        ]
        chunks = chunk_document(sections, "doc-test", min_tokens=10, max_tokens=50)
        assert len(chunks) > 1

    def test_nested_sections(self):
        sections = [
            ExtractedSection(
                id="sec-000",
                heading="Part 1",
                level=1,
                text="Part 1 intro text.",
                children=[
                    ExtractedSection(
                        id="sec-001",
                        heading="Section A",
                        level=2,
                        text="Section A content goes here.",
                    ),
                    ExtractedSection(
                        id="sec-002",
                        heading="Section B",
                        level=2,
                        text="Section B content goes here.",
                    ),
                ],
            )
        ]
        chunks = chunk_document(sections, "doc-test", min_tokens=5, max_tokens=100)
        assert len(chunks) >= 2
        paths = [c.section_path for c in chunks]
        assert any("Section A" in p for p in paths)
        assert any("Section B" in p for p in paths)

    def test_preserves_section_hierarchy_in_path(self):
        sections = [
            ExtractedSection(
                id="sec-000",
                heading="Title 12",
                level=1,
                text="",
                children=[
                    ExtractedSection(
                        id="sec-001",
                        heading="Part 1026",
                        level=2,
                        text="Regulation content here.",
                    ),
                ],
            )
        ]
        chunks = chunk_document(sections, "doc-test", min_tokens=5, max_tokens=100)
        assert len(chunks) >= 1
        assert "Title 12" in chunks[0].section_path
        assert "Part 1026" in chunks[0].section_path


class TestTokenCounting:
    def test_count_tokens(self):
        count = count_tokens("Hello world")
        assert count == 2

    def test_count_tokens_longer(self):
        count = count_tokens("This is a longer sentence with more tokens.")
        assert count > 5
