"""Base adapter interface for ingestion."""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field


@dataclass
class ExtractedSection:
    id: str
    heading: str
    level: int
    text: str
    children: list["ExtractedSection"] = field(default_factory=list)
    parent_id: str | None = None


@dataclass
class ExtractedTable:
    id: str
    caption: str | None
    headers: list[str]
    rows: list[list[str]]
    section_id: str | None = None


@dataclass
class ExtractedDocument:
    title: str
    sections: list[ExtractedSection]
    full_text: str
    tables: list[ExtractedTable]
    cross_references: list[str] = field(default_factory=list)


class IngestionAdapter(ABC):
    @abstractmethod
    async def ingest(self, content: str | bytes, source_url: str = "") -> ExtractedDocument:
        """Transform raw content into an ExtractedDocument."""
        ...

    @abstractmethod
    def supports(self, content_type: str) -> bool:
        """Return True if this adapter handles the given content type."""
        ...
