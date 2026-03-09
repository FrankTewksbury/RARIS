"""Tests for domain-scoped golden run snapshots."""

import pytest

from app.config import settings
from app.models.manifest import Manifest, ManifestStatus, Program, ProgramGeoScope, ProgramStatus
from tests.conftest import TestSession


@pytest.fixture(autouse=True)
def _disable_rate_limit(monkeypatch):
    monkeypatch.setattr(settings, "rate_limit_rpm", 0)


async def _insert_manifest_with_programs(manifest_id: str, domain: str, names: list[str]) -> None:
    async with TestSession() as db:
        manifest = Manifest(
            id=manifest_id,
            domain=domain,
            status=ManifestStatus.approved,
        )
        db.add(manifest)
        for idx, name in enumerate(names, start=1):
            db.add(
                Program(
                    id=f"{manifest_id}-prog-{idx}",
                    manifest_id=manifest_id,
                    canonical_id=f"{manifest_id}-canon-{idx}",
                    name=name,
                    administering_entity=f"Entity {idx}",
                    geo_scope=ProgramGeoScope.state,
                    jurisdiction="State",
                    benefits="Benefit",
                    eligibility="Eligibility",
                    status=ProgramStatus.active,
                    source_urls=[f"https://example.com/{manifest_id}/{idx}"],
                    provenance_links={"source_ids": [f"src-{idx:03d}"]},
                    confidence=0.8,
                    needs_human_review=False,
                )
            )
        await db.commit()


@pytest.mark.asyncio
async def test_promote_golden_run_creates_snapshot_and_current_pointer(client):
    await _insert_manifest_with_programs("run-dpa-001", "DPA", ["Alpha", "Bravo"])
    await _insert_manifest_with_programs("run-dpa-002", "DPA", ["Alpha", "Charlie"])

    resp = await client.post(
        "/api/golden-runs/promote",
        json={
            "domain": "DPA",
            "source_run_ids": ["run-dpa-001", "run-dpa-002"],
            "accepted_by": "tester",
            "notes": "best so far",
        },
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["domain"] == "DPA"
    assert data["version"] == 1
    assert data["unique_output"] == 3
    golden_run_id = data["golden_run_id"]

    current = await client.get("/api/golden-runs/current", params={"domain": "DPA"})
    assert current.status_code == 200
    current_data = current.json()
    assert current_data["golden_run_id"] == golden_run_id
    assert current_data["is_current"] is True

    programs = await client.get("/api/golden-programs", params={"domain": "DPA", "limit": 10})
    assert programs.status_code == 200
    programs_data = programs.json()
    assert programs_data["total"] == 3
    assert {p["golden_run_id"] for p in programs_data["programs"]} == {golden_run_id}
    assert {p["domain"] for p in programs_data["programs"]} == {"DPA"}

    logical_runs = await client.get("/api/manifests/logical-runs", params={"domain": "DPA"})
    assert logical_runs.status_code == 200
    statuses = {run["run_id"]: run["status"] for run in logical_runs.json()["runs"]}
    assert statuses["run-dpa-001"] == "golden_promoted"
    assert statuses["run-dpa-002"] == "golden_promoted"


@pytest.mark.asyncio
async def test_golden_run_history_is_append_only_and_recallable(client):
    await _insert_manifest_with_programs("run-ins-001", "Insurance", ["Alpha", "Bravo"])
    await _insert_manifest_with_programs("run-ins-002", "Insurance", ["Bravo", "Charlie"])

    first = await client.post(
        "/api/golden-runs/promote",
        json={
            "domain": "Insurance",
            "source_run_ids": ["run-ins-001", "run-ins-002"],
            "accepted_by": "tester",
        },
    )
    assert first.status_code == 200
    first_id = first.json()["golden_run_id"]
    assert first.json()["version"] == 1

    second = await client.post(
        "/api/golden-runs/promote",
        json={
            "domain": "Insurance",
            "source_run_ids": ["run-ins-002"],
            "accepted_by": "tester",
            "notes": "narrower rerun",
        },
    )
    assert second.status_code == 200
    second_id = second.json()["golden_run_id"]
    assert second.json()["version"] == 2
    assert second_id != first_id

    runs = await client.get("/api/golden-runs/runs", params={"domain": "Insurance"})
    assert runs.status_code == 200
    runs_data = runs.json()["runs"]
    assert len(runs_data) == 2
    current_runs = [run for run in runs_data if run["is_current"]]
    assert len(current_runs) == 1
    assert current_runs[0]["golden_run_id"] == second_id

    first_snapshot = await client.get(f"/api/golden-runs/runs/{first_id}")
    assert first_snapshot.status_code == 200
    first_program_names = {program["name"] for program in first_snapshot.json()["programs"]}
    assert first_program_names == {"Alpha", "Bravo", "Charlie"}

    second_programs = await client.get(
        "/api/golden-programs",
        params={"golden_run_id": second_id, "limit": 10},
    )
    assert second_programs.status_code == 200
    second_names = {program["name"] for program in second_programs.json()["programs"]}
    assert second_names == {"Bravo", "Charlie"}
