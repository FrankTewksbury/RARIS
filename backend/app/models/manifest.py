import enum
from datetime import datetime

from sqlalchemy import Boolean, DateTime, Enum, Float, ForeignKey, Integer, String, Text, func
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


class ManifestStatus(enum.StrEnum):
    generating = "generating"
    pending_review = "pending_review"
    approved = "approved"
    active = "active"
    archived = "archived"


class SourceType(enum.StrEnum):
    statute = "statute"
    regulation = "regulation"
    guidance = "guidance"
    standard = "standard"
    educational = "educational"
    guide = "guide"


class SourceFormat(enum.StrEnum):
    html = "html"
    pdf = "pdf"
    legal_xml = "legal_xml"
    api = "api"
    structured_data = "structured_data"


class AuthorityLevel(enum.StrEnum):
    binding = "binding"
    advisory = "advisory"
    informational = "informational"


class Jurisdiction(enum.StrEnum):
    federal = "federal"
    state = "state"
    municipal = "municipal"


class AccessMethod(enum.StrEnum):
    scrape = "scrape"
    download = "download"
    api = "api"
    manual = "manual"


class AuthorityType(enum.StrEnum):
    regulator = "regulator"
    gse = "gse"
    sro = "sro"
    industry_body = "industry_body"


class GapSeverity(enum.StrEnum):
    high = "high"
    medium = "medium"
    low = "low"


class Manifest(Base):
    __tablename__ = "manifests"

    id: Mapped[str] = mapped_column(String(100), primary_key=True)
    domain: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    created_by: Mapped[str] = mapped_column(String(100), default="domain-discovery-agent-v1")
    version: Mapped[int] = mapped_column(Integer, default=1)
    status: Mapped[ManifestStatus] = mapped_column(
        Enum(ManifestStatus), default=ManifestStatus.generating
    )
    completeness_score: Mapped[float] = mapped_column(Float, default=0.0)
    jurisdiction_hierarchy: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    review_history: Mapped[list | None] = mapped_column(JSONB, default=list)

    # Relationships
    regulatory_bodies: Mapped[list["RegulatoryBody"]] = relationship(
        back_populates="manifest", cascade="all, delete-orphan"
    )
    sources: Mapped[list["Source"]] = relationship(
        back_populates="manifest", cascade="all, delete-orphan"
    )
    coverage_assessment: Mapped["CoverageAssessment | None"] = relationship(
        back_populates="manifest", cascade="all, delete-orphan", uselist=False
    )


class RegulatoryBody(Base):
    __tablename__ = "regulatory_bodies"

    id: Mapped[str] = mapped_column(String(100), primary_key=True)
    manifest_id: Mapped[str] = mapped_column(ForeignKey("manifests.id"), primary_key=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    jurisdiction: Mapped[Jurisdiction] = mapped_column(Enum(Jurisdiction))
    authority_type: Mapped[AuthorityType] = mapped_column(Enum(AuthorityType))
    url: Mapped[str] = mapped_column(Text, nullable=False)
    governs: Mapped[list | None] = mapped_column(JSONB, default=list)

    manifest: Mapped["Manifest"] = relationship(back_populates="regulatory_bodies")


class Source(Base):
    __tablename__ = "sources"

    id: Mapped[str] = mapped_column(String(100), primary_key=True)
    manifest_id: Mapped[str] = mapped_column(ForeignKey("manifests.id"), primary_key=True)
    name: Mapped[str] = mapped_column(Text, nullable=False)
    regulatory_body_id: Mapped[str] = mapped_column(String(100), nullable=False)
    type: Mapped[SourceType] = mapped_column(Enum(SourceType))
    format: Mapped[SourceFormat] = mapped_column(Enum(SourceFormat))
    authority: Mapped[AuthorityLevel] = mapped_column(Enum(AuthorityLevel))
    jurisdiction: Mapped[Jurisdiction] = mapped_column(Enum(Jurisdiction))
    url: Mapped[str] = mapped_column(Text, nullable=False)
    access_method: Mapped[AccessMethod] = mapped_column(Enum(AccessMethod))
    update_frequency: Mapped[str | None] = mapped_column(String(50), nullable=True)
    last_known_update: Mapped[str | None] = mapped_column(String(50), nullable=True)
    estimated_size: Mapped[str | None] = mapped_column(String(20), nullable=True)
    scraping_notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    confidence: Mapped[float] = mapped_column(Float, default=0.0)
    needs_human_review: Mapped[bool] = mapped_column(Boolean, default=False)
    review_notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    classification_tags: Mapped[list | None] = mapped_column(JSONB, default=list)
    relationships: Mapped[dict | None] = mapped_column(JSONB, default=dict)

    manifest: Mapped["Manifest"] = relationship(back_populates="sources")


class CoverageAssessment(Base):
    __tablename__ = "coverage_assessments"

    manifest_id: Mapped[str] = mapped_column(
        ForeignKey("manifests.id"), primary_key=True
    )
    total_sources: Mapped[int] = mapped_column(Integer, default=0)
    by_jurisdiction: Mapped[dict | None] = mapped_column(JSONB, default=dict)
    by_type: Mapped[dict | None] = mapped_column(JSONB, default=dict)
    completeness_score: Mapped[float] = mapped_column(Float, default=0.0)

    manifest: Mapped["Manifest"] = relationship(back_populates="coverage_assessment")
    known_gaps: Mapped[list["KnownGap"]] = relationship(
        back_populates="coverage_assessment", cascade="all, delete-orphan"
    )


class KnownGap(Base):
    __tablename__ = "known_gaps"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    manifest_id: Mapped[str] = mapped_column(
        ForeignKey("coverage_assessments.manifest_id")
    )
    description: Mapped[str] = mapped_column(Text, nullable=False)
    severity: Mapped[GapSeverity] = mapped_column(Enum(GapSeverity))
    mitigation: Mapped[str | None] = mapped_column(Text, nullable=True)

    coverage_assessment: Mapped["CoverageAssessment"] = relationship(
        back_populates="known_gaps"
    )
