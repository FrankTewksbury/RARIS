from __future__ import annotations

import re
from datetime import UTC, datetime

from sqlalchemy import delete, func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models.manifest import (
    DomainCurrentGolden,
    GoldenRun,
    GoldenRunItem,
    LogicalRun,
    LogicalRunStatus,
    Manifest,
    ManifestStatus,
    Program,
    ProgramGeoScope,
)
from app.services.ensemble_service import _is_program_richer, _normalize_merge_key


def _slugify_domain(domain: str) -> str:
    slug = re.sub(r"[^a-z0-9]+", "-", (domain or "").strip().lower())
    slug = slug.strip("-")
    return slug[:40] or "domain"


def _logical_status_from_manifest(status: ManifestStatus | str) -> LogicalRunStatus:
    raw = status.value if isinstance(status, ManifestStatus) else str(status)
    if raw in {ManifestStatus.approved.value, ManifestStatus.active.value}:
        return LogicalRunStatus.reviewed
    if raw == ManifestStatus.archived.value:
        return LogicalRunStatus.rejected
    return LogicalRunStatus.candidate


async def ensure_logical_runs(
    db: AsyncSession,
    manifest_ids: list[str] | None = None,
) -> None:
    manifest_stmt = select(Manifest)
    if manifest_ids:
        manifest_stmt = manifest_stmt.where(Manifest.id.in_(manifest_ids))
    manifests = (await db.execute(manifest_stmt)).scalars().all()
    if not manifests:
        return

    existing_ids = set(
        (
            await db.execute(
                select(LogicalRun.run_id).where(LogicalRun.run_id.in_([m.id for m in manifests]))
            )
        ).scalars().all()
    )

    for manifest in manifests:
        if manifest.id in existing_ids:
            continue
        db.add(
            LogicalRun(
                run_id=manifest.id,
                manifest_id=manifest.id,
                domain=manifest.domain,
                status=_logical_status_from_manifest(manifest.status),
            )
        )
    await db.commit()


async def create_logical_run_for_manifest(db: AsyncSession, manifest: Manifest) -> None:
    existing = await db.get(LogicalRun, manifest.id)
    if existing:
        return
    db.add(
        LogicalRun(
            run_id=manifest.id,
            manifest_id=manifest.id,
            domain=manifest.domain,
            status=LogicalRunStatus.candidate,
        )
    )
    await db.commit()


async def set_logical_run_status(
    db: AsyncSession,
    run_id: str,
    status: LogicalRunStatus,
) -> None:
    logical_run = await db.get(LogicalRun, run_id)
    if not logical_run:
        manifest = await db.get(Manifest, run_id)
        if not manifest:
            return
        await create_logical_run_for_manifest(db, manifest)
        logical_run = await db.get(LogicalRun, run_id)
        if not logical_run:
            return
    logical_run.status = status
    await db.commit()


async def list_logical_runs(
    db: AsyncSession,
    *,
    domain: str | None = None,
) -> list[LogicalRun]:
    await ensure_logical_runs(db)
    stmt = select(LogicalRun).order_by(LogicalRun.created_at.desc())
    if domain:
        stmt = stmt.where(LogicalRun.domain == domain)
    return (await db.execute(stmt)).scalars().all()


async def promote_to_golden(
    db: AsyncSession,
    *,
    domain: str,
    source_run_ids: list[str],
    accepted_by: str,
    notes: str,
    strategy: str = "pick_richest",
) -> dict:
    source_run_ids = [run_id for run_id in source_run_ids if run_id]
    if not source_run_ids:
        raise ValueError("source_run_ids cannot be empty")

    await ensure_logical_runs(db, source_run_ids)

    manifests = (
        await db.execute(select(Manifest).where(Manifest.id.in_(source_run_ids)))
    ).scalars().all()
    found_manifest_ids = {manifest.id for manifest in manifests}
    missing = [run_id for run_id in source_run_ids if run_id not in found_manifest_ids]
    if missing:
        raise ValueError(f"Unknown source_run_ids: {', '.join(missing)}")

    programs = (
        await db.execute(select(Program).where(Program.manifest_id.in_(source_run_ids)))
    ).scalars().all()

    grouped: dict[str, dict] = {}
    for program in programs:
        merge_key = _normalize_merge_key(program.name)
        if not merge_key:
            continue
        slot = grouped.get(merge_key)
        if slot is None:
            grouped[merge_key] = {
                "best": program,
                "source_run_ids": {program.manifest_id},
            }
            continue
        slot["source_run_ids"].add(program.manifest_id)
        if _is_program_richer(program, slot["best"]):
            slot["best"] = program

    version = int(
        (
            await db.execute(
                select(func.count()).select_from(GoldenRun).where(GoldenRun.domain == domain)
            )
        ).scalar_one()
    ) + 1
    timestamp = datetime.now(UTC).strftime("%Y%m%d%H%M%S")
    golden_run_id = f"golden-{_slugify_domain(domain)}-v{version:03d}-{timestamp}"

    golden_run = GoldenRun(
        id=golden_run_id,
        domain=domain,
        version=version,
        source_run_ids=source_run_ids,
        accepted_by=accepted_by,
        notes=notes or None,
        strategy=strategy,
        item_count=len(grouped),
    )
    db.add(golden_run)

    by_geo_scope: dict[str, int] = {}
    for merge_key, data in grouped.items():
        best: Program = data["best"]
        item = GoldenRunItem(
            golden_run_id=golden_run_id,
            domain=domain,
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
            confidence=best.confidence,
            needs_human_review=best.needs_human_review,
            source_run_ids=sorted(data["source_run_ids"]),
            found_by_count=len(data["source_run_ids"]),
            ensemble_confidence=min(
                1.0, best.confidence + (0.1 * (len(data["source_run_ids"]) - 1))
            ),
        )
        db.add(item)
        geo_key = best.geo_scope.value
        by_geo_scope[geo_key] = by_geo_scope.get(geo_key, 0) + 1

    current_pointer = await db.get(DomainCurrentGolden, domain)
    if current_pointer:
        current_pointer.golden_run_id = golden_run_id
        current_pointer.updated_at = datetime.now(UTC)
    else:
        db.add(DomainCurrentGolden(domain=domain, golden_run_id=golden_run_id))

    logical_runs = (
        await db.execute(select(LogicalRun).where(LogicalRun.run_id.in_(source_run_ids)))
    ).scalars().all()
    for logical_run in logical_runs:
        logical_run.status = LogicalRunStatus.golden_promoted
        logical_run.promoted_to_golden_run_id = golden_run_id

    await db.commit()

    total_input = len(programs)
    unique_output = len(grouped)
    return {
        "golden_run_id": golden_run_id,
        "domain": domain,
        "version": version,
        "total_input": total_input,
        "unique_output": unique_output,
        "duplicates_removed": total_input - unique_output,
        "new_added": unique_output,
        "updated": 0,
        "by_geo_scope": by_geo_scope,
    }


async def list_golden_runs(
    db: AsyncSession,
    *,
    domain: str | None = None,
) -> list[GoldenRun]:
    stmt = select(GoldenRun).order_by(GoldenRun.accepted_at.desc())
    if domain:
        stmt = stmt.where(GoldenRun.domain == domain)
    return (await db.execute(stmt)).scalars().all()


async def list_current_golden_run_ids(db: AsyncSession) -> set[str]:
    return set(
        (
            await db.execute(select(DomainCurrentGolden.golden_run_id))
        ).scalars().all()
    )


async def get_current_golden_run(
    db: AsyncSession,
    *,
    domain: str,
) -> GoldenRun | None:
    pointer = await db.get(DomainCurrentGolden, domain)
    if not pointer:
        return None
    return await db.get(GoldenRun, pointer.golden_run_id)


async def get_golden_run(
    db: AsyncSession,
    *,
    golden_run_id: str,
) -> GoldenRun | None:
    result = await db.execute(
        select(GoldenRun)
        .options(selectinload(GoldenRun.items))
        .where(GoldenRun.id == golden_run_id)
    )
    return result.scalar_one_or_none()


async def list_golden_run_items(
    db: AsyncSession,
    *,
    golden_run_id: str | None = None,
    domain: str | None = None,
    geo_scope: str | None = None,
    offset: int = 0,
    limit: int = 50,
) -> tuple[list[GoldenRunItem], int]:
    if golden_run_id:
        target_run_ids = [golden_run_id]
    elif domain:
        pointer = await db.get(DomainCurrentGolden, domain)
        if not pointer:
            return [], 0
        target_run_ids = [pointer.golden_run_id]
    else:
        target_run_ids = list(
            (
                await db.execute(select(DomainCurrentGolden.golden_run_id))
            ).scalars().all()
        )
        if not target_run_ids:
            return [], 0

    base_stmt = select(GoldenRunItem).where(GoldenRunItem.golden_run_id.in_(target_run_ids))
    count_stmt = select(func.count()).select_from(GoldenRunItem).where(
        GoldenRunItem.golden_run_id.in_(target_run_ids)
    )

    if geo_scope:
        try:
            enum_geo_scope = ProgramGeoScope(geo_scope)
        except ValueError:
            enum_geo_scope = None
        if enum_geo_scope:
            base_stmt = base_stmt.where(GoldenRunItem.geo_scope == enum_geo_scope)
            count_stmt = count_stmt.where(GoldenRunItem.geo_scope == enum_geo_scope)

    total = int((await db.execute(count_stmt)).scalar_one())
    rows = (
        await db.execute(
            base_stmt.order_by(
                GoldenRunItem.ensemble_confidence.desc(),
                GoldenRunItem.name.asc(),
            ).offset(offset).limit(limit)
        )
    ).scalars().all()
    return rows, total


async def golden_program_stats(
    db: AsyncSession,
    *,
    golden_run_id: str | None = None,
    domain: str | None = None,
) -> dict:
    rows, total = await list_golden_run_items(
        db,
        golden_run_id=golden_run_id,
        domain=domain,
        offset=0,
        limit=100000,
    )
    by_geo_scope: dict[str, int] = {}
    by_found_by_count: dict[str, int] = {}
    avg_conf = 0.0
    for row in rows:
        geo_key = row.geo_scope.value
        by_geo_scope[geo_key] = by_geo_scope.get(geo_key, 0) + 1
        found_key = str(row.found_by_count)
        by_found_by_count[found_key] = by_found_by_count.get(found_key, 0) + 1
        avg_conf += row.ensemble_confidence
    return {
        "total": total,
        "by_geo_scope": by_geo_scope,
        "by_found_by_count": by_found_by_count,
        "average_ensemble_confidence": (avg_conf / total) if total else 0.0,
    }


async def rebuild_legacy_golden_programs_cache(
    db: AsyncSession,
    *,
    domain: str,
) -> None:
    # Compatibility hook kept intentionally empty for now.
    # Existing callers are mapped to golden_run_items via API-level compatibility.
    return None


async def clear_domain_current_pointer(db: AsyncSession, *, domain: str) -> None:
    await db.execute(delete(DomainCurrentGolden).where(DomainCurrentGolden.domain == domain))
    await db.commit()
