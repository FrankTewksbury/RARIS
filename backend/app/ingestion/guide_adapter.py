"""Guide adapter — structured multi-chapter HTML guides (GSE seller/servicer guides)."""

import re

from bs4 import BeautifulSoup, Tag

from app.ingestion.base import (
    ExtractedDocument,
    ExtractedSection,
    ExtractedTable,
    IngestionAdapter,
)

# GSE-style section numbering: B3-4.1-01, A1-2.03, etc.
_GSE_SECTION_RE = re.compile(r"^[A-Z]\d+-[\d\.]+(?:-\d+)?")
# Generic numbered sections: 1.2.3, 2.1, etc.
_NUMBERED_RE = re.compile(r"^\d+(?:\.\d+)+")


class GuideAdapter(IngestionAdapter):
    def supports(self, content_type: str) -> bool:
        # Guide format is signaled by the source's format field, not MIME type.
        # This adapter is selected explicitly by the registry for guide-format sources.
        return False

    async def ingest(self, content: str | bytes, source_url: str = "") -> ExtractedDocument:
        if isinstance(content, bytes):
            content = content.decode("utf-8", errors="replace")

        soup = BeautifulSoup(content, "lxml")

        # Strip boilerplate
        for tag_name in ("nav", "footer", "header", "aside", "script", "style"):
            for el in soup.find_all(tag_name):
                el.decompose()

        title = ""
        title_tag = soup.find("title")
        if title_tag:
            title = title_tag.get_text(strip=True)

        # Extract tables
        tables: list[ExtractedTable] = []
        for i, tbl_el in enumerate(soup.find_all("table")):
            tbl = _extract_table(tbl_el, f"tbl-{i:03d}")
            if tbl:
                tables.append(tbl)
            tbl_el.decompose()

        body = soup.find("body") or soup
        sections = _build_guide_sections(body)
        full_text = body.get_text(separator="\n", strip=True)

        # Extract cross-references
        cross_refs: list[str] = []
        for a in soup.find_all("a", href=True):
            href = a["href"]
            if href.startswith(("http://", "https://")) and href != source_url:
                cross_refs.append(href)

        return ExtractedDocument(
            title=title,
            sections=sections,
            full_text=full_text,
            tables=tables,
            cross_references=list(set(cross_refs)),
        )


def _build_guide_sections(body: Tag) -> list[ExtractedSection]:
    """Build sections recognizing guide-style numbering and headings."""
    sections: list[ExtractedSection] = []
    current_text: list[str] = []
    seq = 0

    for el in body.descendants:
        if not isinstance(el, Tag):
            continue

        tag = el.name.lower() if el.name else ""

        # Check for heading tags or guide-numbered elements
        is_heading = tag in ("h1", "h2", "h3", "h4", "h5", "h6")
        text = el.get_text(strip=True) if is_heading else ""

        if not is_heading and tag in ("p", "div", "span"):
            inner = el.get_text(strip=True)
            if inner and (_GSE_SECTION_RE.match(inner) or _NUMBERED_RE.match(inner)):
                if len(inner) < 120:
                    is_heading = True
                    text = inner

        if is_heading and text:
            # Flush
            if current_text and sections:
                sections[-1].text += "\n" + "\n".join(current_text)
                current_text = []
            elif current_text:
                sections.append(ExtractedSection(
                    id=f"sec-{seq:03d}",
                    heading="(Introduction)",
                    level=0,
                    text="\n".join(current_text),
                ))
                seq += 1
                current_text = []

            level = _determine_level(tag, text)
            sections.append(ExtractedSection(
                id=f"sec-{seq:03d}",
                heading=text[:200],
                level=level,
                text="",
            ))
            seq += 1
        elif tag in ("p", "li", "blockquote", "dd", "dt"):
            t = el.get_text(strip=True)
            if t:
                current_text.append(t)

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


def _determine_level(tag: str, text: str) -> int:
    """Determine heading level from tag and content."""
    if tag in ("h1", "h2", "h3", "h4", "h5", "h6"):
        return int(tag[1])

    # GSE sections: depth from number of separators
    m = _GSE_SECTION_RE.match(text)
    if m:
        parts = m.group().replace("-", ".").split(".")
        return min(len(parts), 4)

    m = _NUMBERED_RE.match(text)
    if m:
        parts = m.group().split(".")
        return min(len(parts), 4)

    return 2


def _extract_table(table_el: Tag, table_id: str) -> ExtractedTable | None:
    """Extract table from HTML."""
    headers: list[str] = []
    rows: list[list[str]] = []

    caption_el = table_el.find("caption")
    caption = caption_el.get_text(strip=True) if caption_el else None

    thead = table_el.find("thead")
    if thead:
        for th in thead.find_all(["th", "td"]):
            headers.append(th.get_text(strip=True))

    for tr in table_el.find_all("tr"):
        cells = [td.get_text(strip=True) for td in tr.find_all(["td", "th"])]
        if cells:
            if not headers and all(tr.find_all("th")):
                headers = cells
            else:
                rows.append(cells)

    if not rows:
        return None

    return ExtractedTable(id=table_id, caption=caption, headers=headers, rows=rows)
