"""Vertical pipeline orchestrator — drives discovery → acquisition → ingestion."""

import logging

from sqlalchemy.ext.asyncio import AsyncSession

from app.acquisition.orchestrator import AcquisitionOrchestrator
from app.agent.discovery import DomainDiscoveryAgent
from app.ingestion.orchestrator import IngestionOrchestrator
from app.llm.registry import get_provider
from app.models.manifest import Manifest, ManifestStatus
from app.models.vertical import PipelinePhase
from app.services import acquisition_service, ingestion_service, vertical_service

logger = logging.getLogger(__name__)


async def run_discovery(db: AsyncSession, vertical_id: str) -> str:
    """Run domain discovery for a vertical. Returns the manifest ID."""
    detail = await vertical_service.get_vertical(db, vertical_id)
    if not detail:
        raise ValueError(f"Vertical {vertical_id} not found")

    await vertical_service.update_phase(db, vertical_id, PipelinePhase.discovering)

    # Build discovery domain description from vertical config
    scope = detail.scope
    domain_text = detail.domain_description
    if scope.lines_of_business:
        domain_text += f"\nLines of business: {', '.join(scope.lines_of_business)}"
    if scope.jurisdictions:
        domain_text += f"\nJurisdictions: {', '.join(scope.jurisdictions)}"
    if scope.exclusions:
        domain_text += f"\nExclusions: {', '.join(scope.exclusions)}"

    # Generate manifest ID
    from datetime import UTC, datetime

    timestamp = datetime.now(UTC).strftime("%Y%m%d%H%M%S")
    slug = detail.name[:30].lower().replace(" ", "-").replace("/", "-")
    manifest_id = f"raris-{slug}-{timestamp}"

    # Create manifest record
    manifest = Manifest(
        id=manifest_id,
        domain=detail.domain_description,
        status=ManifestStatus.generating,
        created_by=f"vertical-{vertical_id}",
    )
    db.add(manifest)
    await db.commit()

    # Run discovery agent
    try:
        provider = get_provider(detail.llm_provider)
        agent = DomainDiscoveryAgent(llm=provider, db=db, manifest_id=manifest_id)
        async for _event in agent.run(domain_text):
            pass  # Consume events (no SSE in pipeline mode)

        await vertical_service.update_phase(
            db, vertical_id, PipelinePhase.discovered, manifest_id=manifest_id
        )
        await vertical_service.refresh_metrics(db, vertical_id)

        # Auto-approve manifest for pipeline mode
        manifest = await db.get(Manifest, manifest_id)
        if manifest and manifest.status == ManifestStatus.pending_review:
            manifest.status = ManifestStatus.approved
            await db.commit()

    except Exception as exc:
        logger.exception("Discovery failed for vertical %s", vertical_id)
        await vertical_service.update_phase(
            db, vertical_id, PipelinePhase.failed,
            manifest_id=manifest_id, error=str(exc),
        )
        raise

    return manifest_id


async def run_acquisition(db: AsyncSession, vertical_id: str) -> str:
    """Run acquisition for a vertical. Returns the acquisition ID."""
    detail = await vertical_service.get_vertical(db, vertical_id)
    if not detail:
        raise ValueError(f"Vertical {vertical_id} not found")
    if not detail.manifest_id:
        raise ValueError(f"Vertical {vertical_id} has no manifest — run discovery first")

    # Ensure manifest is approved
    manifest = await db.get(Manifest, detail.manifest_id)
    if not manifest:
        raise ValueError(f"Manifest {detail.manifest_id} not found")
    if manifest.status not in (ManifestStatus.approved, ManifestStatus.active):
        manifest.status = ManifestStatus.approved
        await db.commit()

    await vertical_service.update_phase(db, vertical_id, PipelinePhase.acquiring)

    try:
        run = await acquisition_service.create_acquisition_run(db, detail.manifest_id)
        if not run:
            raise ValueError("Failed to create acquisition run")

        orchestrator = AcquisitionOrchestrator(db=db, acquisition_id=run.id)
        async for _event in orchestrator.run():
            pass  # Consume events

        await vertical_service.update_phase(
            db, vertical_id, PipelinePhase.acquired, acquisition_id=run.id
        )
        await vertical_service.refresh_metrics(db, vertical_id)

        return run.id

    except Exception as exc:
        logger.exception("Acquisition failed for vertical %s", vertical_id)
        await vertical_service.update_phase(
            db, vertical_id, PipelinePhase.failed, error=str(exc)
        )
        raise


async def run_ingestion(db: AsyncSession, vertical_id: str) -> str:
    """Run ingestion for a vertical. Returns the ingestion ID."""
    detail = await vertical_service.get_vertical(db, vertical_id)
    if not detail:
        raise ValueError(f"Vertical {vertical_id} not found")
    if not detail.acquisition_id:
        raise ValueError(f"Vertical {vertical_id} has no acquisition — run acquisition first")

    await vertical_service.update_phase(db, vertical_id, PipelinePhase.ingesting)

    try:
        run = await ingestion_service.create_ingestion_run(db, detail.acquisition_id)
        if not run:
            raise ValueError("Failed to create ingestion run")

        orchestrator = IngestionOrchestrator(db=db, ingestion_run_id=run.id)
        async for _event in orchestrator.run():
            pass  # Consume events

        await vertical_service.update_phase(
            db, vertical_id, PipelinePhase.indexed, ingestion_id=run.id
        )
        await vertical_service.refresh_metrics(db, vertical_id)

        return run.id

    except Exception as exc:
        logger.exception("Ingestion failed for vertical %s", vertical_id)
        await vertical_service.update_phase(
            db, vertical_id, PipelinePhase.failed, error=str(exc)
        )
        raise
