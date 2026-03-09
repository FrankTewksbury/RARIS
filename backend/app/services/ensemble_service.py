from __future__ import annotations

from datetime import UTC, datetime

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.manifest import GoldenProgram, Program, ProgramGeoScope


def _normalize_merge_key(name: str) -> str:
    return (name or "").strip().lower()


def _record_richness(
    *,
    jurisdiction: str | None,
    benefits: str | None,
    eligibility: str | None,
    evidence_snippet: str | None,
    source_urls: list | None,
    provenance_links: dict | None,
    confidence: float,
) -> tuple[int, float]:
    score = 0
    if jurisdiction:
        score += 1
    if benefits:
        score += 1
    if eligibility:
        score += 1
    if evidence_snippet:
        score += 1
    if source_urls:
        score += 1
    if provenance_links:
        score += 1
    return score, confidence


def _is_program_richer(candidate: Program, baseline: Program | GoldenProgram) -> bool:
    c_score = _record_richness(
        jurisdiction=candidate.jurisdiction,
        benefits=candidate.benefits,
        eligibility=candidate.eligibility,
        evidence_snippet=candidate.evidence_snippet,
        source_urls=candidate.source_urls,
        provenance_links=candidate.provenance_links,
        confidence=candidate.confidence,
    )
    b_score = _record_richness(
        jurisdiction=baseline.jurisdiction,
        benefits=baseline.benefits,
        eligibility=baseline.eligibility,
        evidence_snippet=baseline.evidence_snippet,
        source_urls=baseline.source_urls,
        provenance_links=baseline.provenance_links,
        confidence=baseline.confidence,
    )
    return c_score > b_score


async def merge_manifests(
    db: AsyncSession, manifest_ids: list[str]
) -> dict:
    manifest_ids = [m for m in manifest_ids if m]
    if not manifest_ids:
        return {
            "total_input": 0,
            "unique_output": 0,
            "duplicates_removed": 0,
            "new_added": 0,
            "updated": 0,
            "by_geo_scope": {},
        }

    result = await db.execute(
        select(Program).where(Program.manifest_id.in_(manifest_ids))
    )
    programs = result.scalars().all()
    total_input = len(programs)
    if not programs:
        return {
            "total_input": 0,
            "unique_output": 0,
            "duplicates_removed": 0,
            "new_added": 0,
            "updated": 0,
            "by_geo_scope": {},
        }

    grouped: dict[str, dict] = {}
    for p in programs:
        merge_key = _normalize_merge_key(p.name)
        if not merge_key:
            continue
        slot = grouped.get(merge_key)
        if slot is None:
            grouped[merge_key] = {
                "best": p,
                "manifest_ids": {p.manifest_id},
            }
            continue
        slot["manifest_ids"].add(p.manifest_id)
        if _is_program_richer(p, slot["best"]):
            slot["best"] = p

    merge_keys = list(grouped.keys())
    existing_result = await db.execute(
        select(GoldenProgram).where(GoldenProgram.merge_key.in_(merge_keys))
    )
    existing_rows = existing_result.scalars().all()
    existing_map = {row.merge_key: row for row in existing_rows}

    new_added = 0
    updated = 0
    by_geo_scope: dict[str, int] = {}
    now = datetime.now(UTC)

    for merge_key, data in grouped.items():
        best: Program = data["best"]
        manifest_set = set(data["manifest_ids"])
        existing = existing_map.get(merge_key)

        if existing:
            manifest_set.update(existing.source_manifest_ids or [])
            if _is_program_richer(best, existing):
                existing.canonical_id = best.canonical_id
                existing.name = best.name
                existing.administering_entity = best.administering_entity
                existing.geo_scope = best.geo_scope
                existing.jurisdiction = best.jurisdiction
                existing.benefits = best.benefits
                existing.eligibility = best.eligibility
                existing.status = best.status
                existing.last_verified = best.last_verified
                existing.evidence_snippet = best.evidence_snippet
                existing.source_urls = best.source_urls or []
                existing.provenance_links = best.provenance_links or {}
                existing.confidence = max(existing.confidence, best.confidence)
                existing.needs_human_review = (
                    existing.needs_human_review or best.needs_human_review
                )
            else:
                existing.confidence = max(existing.confidence, best.confidence)
                existing.needs_human_review = (
                    existing.needs_human_review or best.needs_human_review
                )
                if best.source_urls:
                    merged_urls = list({*(existing.source_urls or []), *best.source_urls})
                    existing.source_urls = merged_urls
                if best.provenance_links:
                    merged_links = dict(existing.provenance_links or {})
                    merged_links.update(best.provenance_links or {})
                    existing.provenance_links = merged_links

            existing.source_manifest_ids = sorted(manifest_set)
            existing.found_by_count = len(manifest_set)
            existing.ensemble_confidence = min(
                1.0, existing.confidence + (0.1 * (existing.found_by_count - 1))
            )
            existing.merged_at = now
            target_geo = existing.geo_scope.value
            updated += 1
        else:
            found_by_count = len(manifest_set)
            confidence = best.confidence
            ensemble_confidence = min(1.0, confidence + (0.1 * (found_by_count - 1)))
            row = GoldenProgram(
                merge_key=merge_key,
                canonical_id=best.canonical_id,
                name=best.name,
                administering_entity=best.administering_entity,
                geo_scope=best.geo_scope,
                jurisdiction=best.jurisdiction,
                benefits=best.benefits,
                eligibility=best.eligibility,
                status=best.status,
                last_verified=best.last_verified,
                evidence_snippet=best.evidence_snippet,
                source_urls=best.source_urls or [],
                provenance_links=best.provenance_links or {},
                confidence=confidence,
                needs_human_review=best.needs_human_review,
                source_manifest_ids=sorted(manifest_set),
                found_by_count=found_by_count,
                ensemble_confidence=ensemble_confidence,
                merged_at=now,
            )
            db.add(row)
            target_geo = best.geo_scope.value
            new_added += 1

        by_geo_scope[target_geo] = by_geo_scope.get(target_geo, 0) + 1

    await db.commit()

    unique_output = len(grouped)
    return {
        "total_input": total_input,
        "unique_output": unique_output,
        "duplicates_removed": total_input - unique_output,
        "new_added": new_added,
        "updated": updated,
        "by_geo_scope": by_geo_scope,
    }


async def list_golden_programs(
    db: AsyncSession,
    *,
    offset: int = 0,
    limit: int = 50,
    geo_scope: str | None = None,
) -> tuple[list[GoldenProgram], int]:
    base_stmt = select(GoldenProgram)
    count_stmt = select(func.count()).select_from(GoldenProgram)

    if geo_scope:
        try:
            enum_geo_scope = ProgramGeoScope(geo_scope)
        except ValueError:
            enum_geo_scope = None
        if enum_geo_scope:
            base_stmt = base_stmt.where(GoldenProgram.geo_scope == enum_geo_scope)
            count_stmt = count_stmt.where(GoldenProgram.geo_scope == enum_geo_scope)

    total = (await db.execute(count_stmt)).scalar_one()
    rows = (
        await db.execute(
            base_stmt.order_by(
                GoldenProgram.ensemble_confidence.desc(),
                GoldenProgram.name.asc(),
            ).offset(offset).limit(limit)
        )
    ).scalars().all()
    return rows, int(total)


async def golden_program_stats(db: AsyncSession) -> dict:
    total = int(
        (await db.execute(select(func.count()).select_from(GoldenProgram))).scalar_one()
    )

    geo_rows = (
        await db.execute(
            select(GoldenProgram.geo_scope, func.count())
            .group_by(GoldenProgram.geo_scope)
        )
    ).all()
    by_geo_scope = {geo.value: int(count) for geo, count in geo_rows}

    found_rows = (
        await db.execute(
            select(GoldenProgram.found_by_count, func.count())
            .group_by(GoldenProgram.found_by_count)
            .order_by(GoldenProgram.found_by_count.asc())
        )
    ).all()
    by_found_by_count = {str(count_key): int(count_val) for count_key, count_val in found_rows}

    avg_conf = (
        await db.execute(select(func.avg(GoldenProgram.ensemble_confidence)))
    ).scalar_one_or_none()
    average_ensemble_confidence = float(avg_conf or 0.0)

    return {
        "total": total,
        "by_geo_scope": by_geo_scope,
        "by_found_by_count": by_found_by_count,
        "average_ensemble_confidence": average_ensemble_confidence,
    }
