"""Adapter registry — routes content types to the correct ingestion adapter."""

from app.ingestion.base import IngestionAdapter
from app.ingestion.guide_adapter import GuideAdapter
from app.ingestion.html_adapter import HtmlAdapter
from app.ingestion.pdf_adapter import PdfAdapter
from app.ingestion.plaintext_adapter import PlaintextAdapter
from app.ingestion.xml_adapter import XmlAdapter

_html = HtmlAdapter()
_pdf = PdfAdapter()
_xml = XmlAdapter()
_guide = GuideAdapter()
_plaintext = PlaintextAdapter()


def get_adapter(content_type: str, source_format: str = "") -> IngestionAdapter:
    """Select the appropriate adapter for the given content type and source format.

    Args:
        content_type: MIME type of the staged content (e.g. "text/html").
        source_format: The source's declared format from the manifest
                      (e.g. "guide", "legal_xml"). Takes priority when set.
    """
    fmt = source_format.lower()

    # Explicit format overrides take priority
    if fmt == "guide":
        return _guide
    if fmt == "legal_xml":
        return _xml

    ct = content_type.lower()

    if "html" in ct:
        return _html
    if "pdf" in ct:
        return _pdf
    if "xml" in ct:
        return _xml

    # Fallback
    return _plaintext
