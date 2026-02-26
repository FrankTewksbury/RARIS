"""HTML ingestion adapter — extracts structure from HTML documents."""


from bs4 import BeautifulSoup, NavigableString, Tag

from app.ingestion.base import (
    ExtractedDocument,
    ExtractedSection,
    ExtractedTable,
    IngestionAdapter,
)

# Elements to strip entirely
_STRIP_TAGS = {"nav", "footer", "header", "aside", "script", "style", "noscript", "iframe"}
_HEADING_TAGS = {"h1", "h2", "h3", "h4", "h5", "h6"}


class HtmlAdapter(IngestionAdapter):
    def supports(self, content_type: str) -> bool:
        return "html" in content_type.lower()

    async def ingest(self, content: str | bytes, source_url: str = "") -> ExtractedDocument:
        if isinstance(content, bytes):
            content = content.decode("utf-8", errors="replace")

        soup = BeautifulSoup(content, "lxml")

        # Strip boilerplate
        for tag_name in _STRIP_TAGS:
            for el in soup.find_all(tag_name):
                el.decompose()

        # Extract title
        title = ""
        title_tag = soup.find("title")
        if title_tag:
            title = title_tag.get_text(strip=True)
        if not title:
            h1 = soup.find("h1")
            if h1:
                title = h1.get_text(strip=True)

        # Extract tables first, then replace with placeholders
        tables: list[ExtractedTable] = []
        for i, table_el in enumerate(soup.find_all("table")):
            tbl = _extract_table(table_el, f"tbl-{i:03d}")
            if tbl:
                tables.append(tbl)
            table_el.decompose()

        # Build section tree from heading hierarchy
        body = soup.find("body") or soup
        sections = _build_sections(body)

        # Full text
        full_text = body.get_text(separator="\n", strip=True)

        # Extract cross-reference links
        cross_refs = []
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


def _extract_table(table_el: Tag, table_id: str) -> ExtractedTable | None:
    """Extract a table element into an ExtractedTable."""
    headers: list[str] = []
    rows: list[list[str]] = []

    # Caption
    caption_el = table_el.find("caption")
    caption = caption_el.get_text(strip=True) if caption_el else None

    # Headers from thead or first row
    thead = table_el.find("thead")
    if thead:
        for th in thead.find_all(["th", "td"]):
            headers.append(th.get_text(strip=True))

    # Body rows (skip thead rows already processed)
    tbody = table_el.find("tbody") or table_el
    for tr in tbody.find_all("tr"):
        if tr.parent and tr.parent.name == "thead":
            continue
        cells = [td.get_text(strip=True) for td in tr.find_all(["td", "th"])]
        if cells:
            if not headers and all(tr.find_all("th")):
                headers = cells
            else:
                rows.append(cells)

    if not rows:
        return None

    return ExtractedTable(
        id=table_id, caption=caption, headers=headers, rows=rows
    )


def _build_sections(body: Tag) -> list[ExtractedSection]:
    """Walk through body elements and build a section tree from headings."""
    sections: list[ExtractedSection] = []
    current_texts: list[str] = []
    seq = 0

    for el in body.children:
        if isinstance(el, NavigableString):
            text = str(el).strip()
            if text:
                current_texts.append(text)
            continue

        if not isinstance(el, Tag):
            continue

        tag_name = el.name.lower() if el.name else ""

        if tag_name in _HEADING_TAGS:
            # Flush accumulated text as a section if any
            if current_texts and sections:
                sections[-1].text += "\n" + "\n".join(current_texts)
                current_texts = []
            elif current_texts:
                sections.append(ExtractedSection(
                    id=f"sec-{seq:03d}",
                    heading="(Introduction)",
                    level=0,
                    text="\n".join(current_texts),
                ))
                seq += 1
                current_texts = []

            level = int(tag_name[1])
            heading_text = el.get_text(strip=True)
            sections.append(ExtractedSection(
                id=f"sec-{seq:03d}",
                heading=heading_text,
                level=level,
                text="",
            ))
            seq += 1
        else:
            text = el.get_text(separator="\n", strip=True)
            if text:
                current_texts.append(text)

    # Flush remaining text
    if current_texts:
        if sections:
            sections[-1].text += "\n" + "\n".join(current_texts)
        else:
            sections.append(ExtractedSection(
                id=f"sec-{seq:03d}",
                heading="(Document)",
                level=0,
                text="\n".join(current_texts),
            ))

    return _nest_sections(sections)


def _nest_sections(flat: list[ExtractedSection]) -> list[ExtractedSection]:
    """Convert flat heading list into nested hierarchy based on level."""
    if not flat:
        return []

    root: list[ExtractedSection] = []
    stack: list[ExtractedSection] = []

    for section in flat:
        # Pop stack until we find a parent with lower level
        while stack and stack[-1].level >= section.level:
            stack.pop()

        if stack:
            section.parent_id = stack[-1].id
            stack[-1].children.append(section)
        else:
            root.append(section)

        stack.append(section)

    return root
