"""Export endpoints — downloadable data in JSON/CSV format."""

import csv
import io
import logging

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import StreamingResponse
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.database import get_db
from app.models.manifest import CoverageAssessment, Manifest
from app.models.retrieval import QueryRecord

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/export", tags=["export"])


@router.get("/manifest/{manifest_id}")
async def export_manifest(manifest_id: str, db: AsyncSession = Depends(get_db)):
    """Export a manifest with all sources as a JSON download."""
    result = await db.execute(
        select(Manifest)
        .where(Manifest.id == manifest_id)
        .options(
            selectinload(Manifest.sources),
            selectinload(Manifest.regulatory_bodies),
            selectinload(Manifest.coverage_assessment)
            .selectinload(CoverageAssessment.known_gaps),
        )
    )
    manifest = result.scalar_one_or_none()
    if not manifest:
        raise HTTPException(status_code=404, detail="Manifest not found")

    data = {
        "id": manifest.id,
        "domain": manifest.domain,
        "status": str(manifest.status),
        "version": manifest.version,
        "completeness_score": manifest.completeness_score,
        "created_at": str(manifest.created_at) if manifest.created_at else None,
        "regulatory_bodies": [
            {
                "id": rb.id,
                "name": rb.name,
                "jurisdiction": str(rb.jurisdiction),
                "authority_type": str(rb.authority_type),
                "url": rb.url,
            }
            for rb in manifest.regulatory_bodies
        ],
        "sources": [
            {
                "id": s.id,
                "name": s.name,
                "type": str(s.type),
                "format": str(s.format),
                "authority": str(s.authority),
                "jurisdiction": str(s.jurisdiction),
                "url": s.url,
                "access_method": str(s.access_method),
                "confidence": s.confidence,
                "needs_human_review": s.needs_human_review,
            }
            for s in manifest.sources
        ],
    }

    if manifest.coverage_assessment:
        ca = manifest.coverage_assessment
        data["coverage_assessment"] = {
            "total_sources": ca.total_sources,
            "completeness_score": ca.completeness_score,
            "by_jurisdiction": ca.by_jurisdiction,
            "by_type": ca.by_type,
            "known_gaps": [
                {
                    "description": g.description,
                    "severity": str(g.severity),
                    "mitigation": g.mitigation,
                }
                for g in ca.known_gaps
            ],
        }

    import json

    content = json.dumps(data, indent=2, default=str)
    return StreamingResponse(
        io.BytesIO(content.encode()),
        media_type="application/json",
        headers={
            "Content-Disposition": f'attachment; filename="manifest-{manifest_id}.json"'
        },
    )


@router.get("/queries")
async def export_queries(db: AsyncSession = Depends(get_db)):
    """Export query history as CSV download."""
    result = await db.execute(
        select(QueryRecord).order_by(QueryRecord.created_at.desc())
    )
    records = result.scalars().all()

    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow([
        "id", "query", "depth", "status", "sources_count",
        "token_count", "created_at", "completed_at",
    ])

    for r in records:
        writer.writerow([
            r.id, r.query, r.depth, r.status, r.sources_count,
            r.token_count, str(r.created_at) if r.created_at else "",
            str(r.completed_at) if r.completed_at else "",
        ])

    content = output.getvalue()
    return StreamingResponse(
        io.BytesIO(content.encode()),
        media_type="text/csv",
        headers={
            "Content-Disposition": 'attachment; filename="query-history.csv"'
        },
    )


@router.get("/corpus/summary")
async def export_corpus_summary(db: AsyncSession = Depends(get_db)):
    """Export corpus statistics as JSON download."""
    from app.ingestion.indexer import get_index_stats

    stats = await get_index_stats(db)

    import json

    content = json.dumps(stats, indent=2, default=str)
    return StreamingResponse(
        io.BytesIO(content.encode()),
        media_type="application/json",
        headers={
            "Content-Disposition": 'attachment; filename="corpus-summary.json"'
        },
    )
