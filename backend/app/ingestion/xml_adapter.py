"""Legal XML ingestion adapter — USLM, Akoma Ntoso, generic XML."""

from lxml import etree

from app.ingestion.base import (
    ExtractedDocument,
    ExtractedSection,
    ExtractedTable,
    IngestionAdapter,
)

# USLM namespace
_USLM_NS = {"uslm": "https://xml.house.gov/schemas/uslm/1.0"}

# Akoma Ntoso namespace
_AKN_NS = {"akn": "http://docs.oasis-open.org/legaldocml/ns/akn/3.0"}


class XmlAdapter(IngestionAdapter):
    def supports(self, content_type: str) -> bool:
        ct = content_type.lower()
        return "xml" in ct

    async def ingest(self, content: str | bytes, source_url: str = "") -> ExtractedDocument:
        if isinstance(content, str):
            content = content.encode("utf-8")

        root = etree.fromstring(content)
        ns = _detect_schema(root)

        if ns == "uslm":
            return _parse_uslm(root)
        if ns == "akn":
            return _parse_akn(root)
        return _parse_generic_xml(root)


def _detect_schema(root: etree._Element) -> str:
    """Detect XML schema from root namespace."""
    tag = root.tag if root.tag else ""
    if "house.gov" in tag or "uslm" in tag:
        return "uslm"
    if "legaldocml" in tag or "akomaNtoso" in tag.lower():
        return "akn"
    return "generic"


def _parse_uslm(root: etree._Element) -> ExtractedDocument:
    """Parse USLM (US Legislative Markup) XML."""
    title = ""
    title_el = root.find(".//{*}title") or root.find(".//{*}heading")
    if title_el is not None and title_el.text:
        title = title_el.text.strip()

    sections, seq = _extract_uslm_sections(root, 0)
    tables = _extract_xml_tables(root)
    full_text = _get_all_text(root)
    cross_refs = _extract_xml_refs(root)

    return ExtractedDocument(
        title=title,
        sections=sections,
        full_text=full_text,
        tables=tables,
        cross_references=cross_refs,
    )


def _extract_uslm_sections(
    el: etree._Element, seq: int, level: int = 1
) -> tuple[list[ExtractedSection], int]:
    """Recursively extract sections from USLM elements."""
    sections: list[ExtractedSection] = []

    for child in el:
        tag = etree.QName(child.tag).localname if child.tag else ""

        if tag in ("section", "title", "subtitle", "chapter", "subchapter", "part", "subpart"):
            heading_el = child.find("{*}heading") or child.find("{*}num")
            heading = ""
            if heading_el is not None:
                heading = _get_all_text(heading_el).strip()

            text = _get_direct_text(child)
            children, seq = _extract_uslm_sections(child, seq + 1, level + 1)

            sections.append(ExtractedSection(
                id=f"sec-{seq:03d}",
                heading=heading or f"({tag})",
                level=level,
                text=text,
                children=children,
            ))
            seq += 1
        elif tag in ("content", "paragraph", "subsection"):
            text = _get_all_text(child).strip()
            if text:
                if sections:
                    sections[-1].text += "\n" + text
                else:
                    sections.append(ExtractedSection(
                        id=f"sec-{seq:03d}",
                        heading=f"({tag})",
                        level=level,
                        text=text,
                    ))
                    seq += 1

    return sections, seq


def _parse_akn(root: etree._Element) -> ExtractedDocument:
    """Parse Akoma Ntoso XML."""
    title = ""
    doc_title = root.find(".//{*}docTitle")
    if doc_title is not None:
        title = _get_all_text(doc_title).strip()

    body = root.find(".//{*}body") or root
    sections, _ = _extract_akn_sections(body, 0)
    tables = _extract_xml_tables(root)
    full_text = _get_all_text(root)
    cross_refs = _extract_xml_refs(root)

    return ExtractedDocument(
        title=title,
        sections=sections,
        full_text=full_text,
        tables=tables,
        cross_references=cross_refs,
    )


def _extract_akn_sections(
    el: etree._Element, seq: int, level: int = 1
) -> tuple[list[ExtractedSection], int]:
    """Recursively extract from Akoma Ntoso body."""
    sections: list[ExtractedSection] = []

    for child in el:
        tag = etree.QName(child.tag).localname if child.tag else ""

        if tag in ("section", "article", "chapter", "part", "title", "division"):
            heading_el = child.find("{*}heading") or child.find("{*}num")
            heading = _get_all_text(heading_el).strip() if heading_el is not None else f"({tag})"
            text = _get_direct_text(child)
            children, seq = _extract_akn_sections(child, seq + 1, level + 1)

            sections.append(ExtractedSection(
                id=f"sec-{seq:03d}",
                heading=heading,
                level=level,
                text=text,
                children=children,
            ))
            seq += 1

    return sections, seq


def _parse_generic_xml(root: etree._Element) -> ExtractedDocument:
    """Fallback for unknown XML schemas."""
    title = ""
    for tag_name in ("title", "name", "heading"):
        el = root.find(f".//{tag_name}")
        if el is None:
            el = root.find(f".//{{*}}{tag_name}")
        if el is not None and el.text:
            title = el.text.strip()
            break

    full_text = _get_all_text(root)
    sections = [ExtractedSection(
        id="sec-000",
        heading=title or "(Document)",
        level=1,
        text=full_text,
    )]
    tables = _extract_xml_tables(root)

    return ExtractedDocument(
        title=title,
        sections=sections,
        full_text=full_text,
        tables=tables,
    )


def _extract_xml_tables(root: etree._Element) -> list[ExtractedTable]:
    """Extract table elements from XML."""
    tables: list[ExtractedTable] = []
    for i, tbl in enumerate(root.iter("{*}table")):
        headers: list[str] = []
        rows: list[list[str]] = []

        for row_el in tbl.iter("{*}tr", "{*}row"):
            cells = [_get_all_text(c).strip() for c in row_el]
            if cells:
                if not headers:
                    headers = cells
                else:
                    rows.append(cells)

        if rows:
            tables.append(ExtractedTable(
                id=f"tbl-{i:03d}",
                caption=None,
                headers=headers,
                rows=rows,
            ))
    return tables


def _extract_xml_refs(root: etree._Element) -> list[str]:
    """Extract cross-reference URIs from XML."""
    refs: set[str] = set()
    for el in root.iter("{*}ref", "{*}a"):
        href = el.get("href") or el.get("{http://www.w3.org/1999/xlink}href") or ""
        if href.startswith(("http://", "https://")):
            refs.add(href)
    return list(refs)


def _get_all_text(el: etree._Element) -> str:
    """Get all text content from an element and its children."""
    return "".join(el.itertext())


def _get_direct_text(el: etree._Element) -> str:
    """Get only direct child text (not from nested sections)."""
    parts: list[str] = []
    if el.text:
        parts.append(el.text.strip())
    for child in el:
        tag = etree.QName(child.tag).localname if child.tag else ""
        if tag not in ("section", "chapter", "part", "title", "article", "division"):
            parts.append(_get_all_text(child).strip())
        if child.tail:
            parts.append(child.tail.strip())
    return "\n".join(p for p in parts if p)
