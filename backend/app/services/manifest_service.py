from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models.manifest import (
    CoverageAssessment,
    Manifest,
    ManifestStatus,
    Source,
)
from app.schemas.manifest import (
    CoverageAssessmentResponse,
    DomainMapResponse,
    ManifestDetail,
    ManifestSummary,
    RegulatoryBodyResponse,
    SourceCreate,
    SourceResponse,
    SourceUpdate,
)


async def get_manifest(db: AsyncSession, manifest_id: str) -> ManifestDetail | None:
    result = await db.execute(
        select(Manifest)
        .options(
            selectinload(Manifest.sources),
            selectinload(Manifest.regulatory_bodies),
            selectinload(Manifest.coverage_assessment).selectinload(
                CoverageAssessment.known_gaps
            ),
        )
        .where(Manifest.id == manifest_id)
    )
    manifest = result.scalar_one_or_none()
    if not manifest:
        return None

    sources = [
        SourceResponse(
            id=s.id,
            name=s.name,
            regulatory_body=s.regulatory_body_id,
            type=s.type.value,
            format=s.format.value,
            authority=s.authority.value,
            jurisdiction=s.jurisdiction.value,
            url=s.url,
            access_method=s.access_method.value,
            update_frequency=s.update_frequency,
            last_known_update=s.last_known_update,
            estimated_size=s.estimated_size,
            scraping_notes=s.scraping_notes,
            confidence=s.confidence,
            needs_human_review=s.needs_human_review,
            review_notes=s.review_notes,
            classification_tags=s.classification_tags or [],
            relationships=s.relationships or {},
        )
        for s in manifest.sources
    ]

    bodies = [
        RegulatoryBodyResponse(
            id=b.id,
            name=b.name,
            jurisdiction=b.jurisdiction.value,
            authority_type=b.authority_type.value,
            url=b.url,
            governs=b.governs or [],
        )
        for b in manifest.regulatory_bodies
    ]

    coverage = None
    if manifest.coverage_assessment:
        ca = manifest.coverage_assessment
        coverage = CoverageAssessmentResponse(
            total_sources=ca.total_sources,
            by_jurisdiction=ca.by_jurisdiction or {},
            by_type=ca.by_type or {},
            completeness_score=ca.completeness_score,
            known_gaps=[
                {
                    "description": g.description,
                    "severity": g.severity.value,
                    "mitigation": g.mitigation,
                }
                for g in ca.known_gaps
            ],
        )

    return ManifestDetail(
        id=manifest.id,
        domain=manifest.domain,
        status=manifest.status.value,
        created=manifest.created_at,
        sources_count=len(sources),
        coverage_score=manifest.completeness_score,
        sources=sources,
        domain_map=DomainMapResponse(
            regulatory_bodies=bodies,
            jurisdiction_hierarchy=manifest.jurisdiction_hierarchy or [],
        ),
        coverage_assessment=coverage,
    )


async def list_manifests(db: AsyncSession) -> list[ManifestSummary]:
    result = await db.execute(
        select(Manifest)
        .options(selectinload(Manifest.sources))
        .order_by(Manifest.created_at.desc())
    )
    manifests = result.scalars().all()
    return [
        ManifestSummary(
            id=m.id,
            domain=m.domain,
            status=m.status.value,
            created=m.created_at,
            sources_count=len(m.sources) if m.sources else 0,
            coverage_score=m.completeness_score,
        )
        for m in manifests
    ]


async def update_source(
    db: AsyncSession, manifest_id: str, source_id: str, update: SourceUpdate
) -> SourceResponse | None:
    result = await db.execute(
        select(Source).where(
            Source.manifest_id == manifest_id, Source.id == source_id
        )
    )
    source = result.scalar_one_or_none()
    if not source:
        return None

    update_data = update.model_dump(exclude_unset=True)
    for field, value in update_data.items():
        if field == "type":
            from app.models.manifest import SourceType
            setattr(source, field, SourceType(value))
        elif field == "format":
            from app.models.manifest import SourceFormat
            setattr(source, field, SourceFormat(value))
        elif field == "authority":
            from app.models.manifest import AuthorityLevel
            setattr(source, field, AuthorityLevel(value))
        elif field == "access_method":
            from app.models.manifest import AccessMethod
            setattr(source, field, AccessMethod(value))
        else:
            setattr(source, field, value)

    await db.commit()
    await db.refresh(source)

    return SourceResponse(
        id=source.id,
        name=source.name,
        regulatory_body=source.regulatory_body_id,
        type=source.type.value,
        format=source.format.value,
        authority=source.authority.value,
        jurisdiction=source.jurisdiction.value,
        url=source.url,
        access_method=source.access_method.value,
        update_frequency=source.update_frequency,
        last_known_update=source.last_known_update,
        estimated_size=source.estimated_size,
        scraping_notes=source.scraping_notes,
        confidence=source.confidence,
        needs_human_review=source.needs_human_review,
        review_notes=source.review_notes,
        classification_tags=source.classification_tags or [],
        relationships=source.relationships or {},
    )


async def add_source(
    db: AsyncSession, manifest_id: str, create: SourceCreate
) -> SourceResponse | None:
    # Check manifest exists
    manifest = await db.get(Manifest, manifest_id)
    if not manifest:
        return None

    # Generate next source ID
    result = await db.execute(
        select(Source).where(Source.manifest_id == manifest_id)
    )
    existing = result.scalars().all()
    next_num = len(existing) + 1
    source_id = f"src-{next_num:03d}"

    source = Source(
        id=source_id,
        manifest_id=manifest_id,
        name=create.name,
        regulatory_body_id=create.regulatory_body,
        type=SourceType(create.type),
        format=SourceFormat(create.format),
        authority=AuthorityLevel(create.authority),
        jurisdiction=Jurisdiction(create.jurisdiction),
        url=create.url,
        access_method=AccessMethod(create.access_method),
        update_frequency=create.update_frequency,
        estimated_size=create.estimated_size,
        scraping_notes=create.scraping_notes,
        confidence=create.confidence,
        needs_human_review=create.needs_human_review,
        classification_tags=create.classification_tags,
    )
    db.add(source)
    await db.commit()
    await db.refresh(source)

    return SourceResponse(
        id=source.id,
        name=source.name,
        regulatory_body=source.regulatory_body_id,
        type=source.type.value,
        format=source.format.value,
        authority=source.authority.value,
        jurisdiction=source.jurisdiction.value,
        url=source.url,
        access_method=source.access_method.value,
        update_frequency=source.update_frequency,
        last_known_update=source.last_known_update,
        estimated_size=source.estimated_size,
        scraping_notes=source.scraping_notes,
        confidence=source.confidence,
        needs_human_review=source.needs_human_review,
        review_notes=source.review_notes,
        classification_tags=source.classification_tags or [],
        relationships=source.relationships or {},
    )


# Import enums for add_source
from app.models.manifest import (  # noqa: E402
    AccessMethod,
    AuthorityLevel,
    Jurisdiction,
    SourceFormat,
    SourceType,
)


async def approve_manifest(
    db: AsyncSession, manifest_id: str, reviewer: str, notes: str
) -> dict | None:
    result = await db.execute(
        select(Manifest)
        .options(selectinload(Manifest.sources))
        .where(Manifest.id == manifest_id)
    )
    manifest = result.scalar_one_or_none()
    if not manifest:
        return None

    # Check all sources needing review have been reviewed
    unreviewed = [s for s in manifest.sources if s.needs_human_review]
    if unreviewed:
        return {
            "error": f"{len(unreviewed)} sources still need human review",
            "unreviewed_source_ids": [s.id for s in unreviewed],
        }

    now = datetime.now(UTC)
    manifest.status = ManifestStatus.approved
    review_history = manifest.review_history or []
    review_history.append({
        "date": now.isoformat(),
        "reviewer": reviewer,
        "action": "approved",
        "notes": notes,
    })
    manifest.review_history = review_history
    await db.commit()

    return {
        "manifest_id": manifest.id,
        "status": "approved",
        "approved_at": now.isoformat(),
    }


async def reject_manifest(
    db: AsyncSession, manifest_id: str, reviewer: str, notes: str
) -> dict | None:
    manifest = await db.get(Manifest, manifest_id)
    if not manifest:
        return None

    manifest.status = ManifestStatus.pending_review
    review_history = manifest.review_history or []
    review_history.append({
        "date": datetime.now(UTC).isoformat(),
        "reviewer": reviewer,
        "action": "rejected",
        "notes": notes,
    })
    manifest.review_history = review_history
    await db.commit()

    return {
        "manifest_id": manifest.id,
        "status": "pending_review",
        "rejection_notes": notes,
    }
