"""Plaintext ingestion adapter — heuristic structure extraction from plain text."""

import re

from app.ingestion.base import (
    ExtractedDocument,
    ExtractedSection,
    IngestionAdapter,
)

# Heading patterns for regulatory plain text
_NUMBERED_HEADING = re.compile(r"^(?:§\s*)?(\d+(?:\.\d+)*)\s+[A-Z]")
_ALLCAPS_LINE = re.compile(r"^[A-Z][A-Z\s\-\.,;:]{4,}$")
_PART_HEADING = re.compile(
    r"^(?:PART|CHAPTER|SECTION|TITLE|ARTICLE|SUBPART|APPENDIX)\s+[\dIVXA-Z]+",
    re.IGNORECASE,
)


class PlaintextAdapter(IngestionAdapter):
    def supports(self, content_type: str) -> bool:
        ct = content_type.lower()
        return "text/plain" in ct or "text/csv" not in ct and ct == "text"

    async def ingest(self, content: str | bytes, source_url: str = "") -> ExtractedDocument:
        if isinstance(content, bytes):
            content = content.decode("utf-8", errors="replace")

        lines = content.split("\n")
        title = _extract_title(lines)
        sections = _build_sections(lines)

        return ExtractedDocument(
            title=title,
            sections=sections,
            full_text=content,
            tables=[],
        )


def _extract_title(lines: list[str]) -> str:
    """First non-empty line as title."""
    for line in lines[:10]:
        stripped = line.strip()
        if stripped:
            return stripped[:200]
    return ""


def _build_sections(lines: list[str]) -> list[ExtractedSection]:
    """Build sections from plain text using heuristic heading detection."""
    sections: list[ExtractedSection] = []
    current_text: list[str] = []
    seq = 0

    for line in lines:
        stripped = line.strip()

        if not stripped:
            current_text.append("")
            continue

        if _is_heading(stripped):
            # Flush
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
    """Heuristic heading detection."""
    if len(line) > 120:
        return False
    if _PART_HEADING.match(line):
        return True
    if _NUMBERED_HEADING.match(line):
        return True
    if _ALLCAPS_LINE.match(line) and len(line) > 3:
        return True
    return False


def _estimate_level(heading: str) -> int:
    """Estimate heading level."""
    h = heading.upper()
    if h.startswith(("TITLE", "PART")):
        return 1
    if h.startswith(("CHAPTER", "SUBPART")):
        return 2
    if h.startswith(("SECTION", "§", "ARTICLE")):
        return 3
    if _NUMBERED_HEADING.match(heading):
        m = _NUMBERED_HEADING.match(heading)
        if m:
            depth = len(m.group(1).split("."))
            return min(depth, 4)
    return 2
