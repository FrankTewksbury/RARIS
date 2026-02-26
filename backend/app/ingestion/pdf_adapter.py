"""PDF ingestion adapter — extracts structure from PDF documents."""

import re
from io import BytesIO

import pdfplumber

from app.ingestion.base import (
    ExtractedDocument,
    ExtractedSection,
    ExtractedTable,
    IngestionAdapter,
)

# Heuristic: lines that are short, uppercase, or bold-like are potential headings
_HEADING_PATTERN = re.compile(
    r"^(?:"
    r"(?:PART|CHAPTER|SECTION|ARTICLE|TITLE|SUBPART)\s+[\dIVXA-Z]+"  # Numbered headers
    r"|(?:§\s*\d+[\.\d]*)"  # Section symbols
    r"|(?:[A-Z][A-Z\s\-]{4,})"  # ALL CAPS lines
    r")",
    re.MULTILINE,
)


class PdfAdapter(IngestionAdapter):
    def supports(self, content_type: str) -> bool:
        return "pdf" in content_type.lower()

    async def ingest(self, content: str | bytes, source_url: str = "") -> ExtractedDocument:
        if isinstance(content, str):
            content = content.encode("utf-8")

        pdf = pdfplumber.open(BytesIO(content))
        pages_text: list[str] = []
        tables: list[ExtractedTable] = []
        tbl_seq = 0

        for page in pdf.pages:
            # Extract text
            text = page.extract_text() or ""
            pages_text.append(text)

            # Extract tables
            for tbl_data in page.extract_tables() or []:
                if not tbl_data or len(tbl_data) < 2:
                    continue
                headers = [str(c or "") for c in tbl_data[0]]
                rows = [[str(c or "") for c in row] for row in tbl_data[1:]]
                tables.append(ExtractedTable(
                    id=f"tbl-{tbl_seq:03d}",
                    caption=None,
                    headers=headers,
                    rows=rows,
                ))
                tbl_seq += 1

        pdf.close()

        full_text = "\n\n".join(pages_text)
        title = _extract_title(pages_text)
        sections = _build_sections_from_text(full_text)

        return ExtractedDocument(
            title=title,
            sections=sections,
            full_text=full_text,
            tables=tables,
        )


def _extract_title(pages: list[str]) -> str:
    """Heuristic title extraction from first page."""
    if not pages:
        return ""
    first_page = pages[0].strip()
    lines = [line.strip() for line in first_page.split("\n") if line.strip()]
    if lines:
        # First non-empty line is often the title
        return lines[0][:200]
    return ""


def _build_sections_from_text(text: str) -> list[ExtractedSection]:
    """Build sections from plain text using heading heuristics."""
    lines = text.split("\n")
    sections: list[ExtractedSection] = []
    current_text: list[str] = []
    seq = 0

    for line in lines:
        stripped = line.strip()
        if not stripped:
            current_text.append("")
            continue

        if _is_heading(stripped):
            # Flush accumulated text
            if current_text and sections:
                sections[-1].text += "\n" + "\n".join(current_text)
                current_text = []
            elif current_text:
                sections.append(ExtractedSection(
                    id=f"sec-{seq:03d}",
                    heading="(Preamble)",
                    level=0,
                    text="\n".join(current_text),
                ))
                seq += 1
                current_text = []

            level = _estimate_level(stripped)
            sections.append(ExtractedSection(
                id=f"sec-{seq:03d}",
                heading=stripped[:200],
                level=level,
                text="",
            ))
            seq += 1
        else:
            current_text.append(stripped)

    # Flush remaining
    if current_text:
        if sections:
            sections[-1].text += "\n" + "\n".join(current_text)
        else:
            sections.append(ExtractedSection(
                id=f"sec-{seq:03d}",
                heading="(Document)",
                level=0,
                text="\n".join(current_text),
            ))

    return sections


def _is_heading(line: str) -> bool:
    """Heuristic: short lines that match heading patterns."""
    if len(line) > 120:
        return False
    if _HEADING_PATTERN.match(line):
        return True
    # All caps short line
    if line == line.upper() and len(line) > 3 and len(line) < 80:
        return True
    return False


def _estimate_level(heading: str) -> int:
    """Estimate heading level from text patterns."""
    h = heading.upper()
    if h.startswith(("TITLE", "PART")):
        return 1
    if h.startswith(("CHAPTER", "SUBPART")):
        return 2
    if h.startswith(("SECTION", "§")):
        return 3
    if h.startswith("ARTICLE"):
        return 2
    return 2
