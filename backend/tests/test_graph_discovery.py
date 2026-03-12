"""Tests for graph discovery engine (DiscoveryGraph) — V5 BFS."""

import json
import pytest
from unittest.mock import AsyncMock, MagicMock

from app.agent.graph_discovery import DiscoveryGraph, _SEED_TO_ENTITY_TYPE
from app.llm.base import Citation, LLMProvider


# ---------------------------------------------------------------------------
# MockLLM — V5 routing
# ---------------------------------------------------------------------------

class MockLLM(LLMProvider):
    """Mock LLM that returns canned JSON responses for V6 BFS engine.

    Routing logic (via complete()):
    - ENTITY EXPANSION CALL header → entity expansion call → returns programs[]
    - Otherwise (SECTOR SCOPE header) → sector discovery call → returns administering_entities[]
    """

    def __init__(self, responses: dict[str, str] | None = None):
        self._responses = responses or {}
        self._call_count = 0
        self.calls: list[dict] = []

    async def complete(self, messages, **kwargs):
        self._call_count += 1
        prompt = messages[-1]["content"] if messages else ""
        self.calls.append({"prompt": prompt[:1000], "kwargs": kwargs})

        if "## entity expansion" in prompt.lower():
            # L2 entity expansion — return programs for this entity
            return self._responses.get("expansion", json.dumps({
                "programs": [
                    {
                        "name": "Example DPA Program",
                        "administering_entity": "Example Entity",
                        "geo_scope": "state",
                        "jurisdiction": "California",
                        "benefits": "Up to $10,000 forgivable loan",
                        "eligibility": "First-time homebuyers",
                        "status": "active",
                        "evidence_snippet": "Found via official entity page",
                        "source_urls": ["https://example-entity.gov/dpa"],
                        "confidence": 0.85,
                        "needs_human_review": False,
                    }
                ],
                "sources": [
                    {
                        "id": "src-l2-001",
                        "name": "Entity Program Page",
                        "regulatory_body": "example-entity",
                        "type": "guidance",
                        "format": "html",
                        "authority": "informational",
                        "jurisdiction": "state",
                        "url": "https://example-entity.gov/dpa",
                        "access_method": "scrape",
                        "confidence": 0.85,
                        "needs_human_review": False,
                    }
                ],
            }))
        else:
            # L1 sector discovery — return administering_entities[]
            return self._responses.get("sector", json.dumps({
                "sector_key": "federal",
                "coverage_summary": {
                    "entities_found": 1,
                    "programs_found": 0,
                    "gaps": [],
                },
                "administering_entities": [
                    {
                        "id": "hud",
                        "name": "HUD",
                        "entity_type": "federal",
                        "jurisdiction": "federal",
                        "url": "https://hud.gov",
                        "governs": ["housing"],
                        "confidence": 0.95,
                        "needs_human_review": False,
                        "verification_state": "verified",
                    }
                ],
                "programs": [],
                "funding_streams": [],
                "queue_state": {
                    "visited_entities": ["hud"],
                    "visited_sources": ["https://hud.gov"],
                    "next_actions": [],
                },
            }))

    async def stream(self, messages, **kwargs):
        yield '{"programs": []}'

    async def complete_grounded(self, messages, **kwargs):
        text = await self.complete(messages, **kwargs)
        citations = [Citation(url="https://hud.gov", title="HUD")]
        return text, citations


@pytest.fixture
def mock_db():
    """Create a mock async database session."""
    db = AsyncMock()
    db.add = MagicMock()
    db.flush = AsyncMock()
    db.commit = AsyncMock()

    mock_manifest = MagicMock()
    mock_manifest.jurisdiction_hierarchy = None
    mock_manifest.coverage_summary = None
    mock_manifest.status = None
    mock_manifest.completeness_score = None
    db.get = AsyncMock(return_value=mock_manifest)

    return db


# ---------------------------------------------------------------------------
# Tests: Instantiation
# ---------------------------------------------------------------------------

class TestDiscoveryGraphInit:
    def test_instantiation(self, mock_db):
        llm = MockLLM()
        graph = DiscoveryGraph(llm=llm, db=mock_db, manifest_id="test-001")
        assert graph.manifest_id == "test-001"


# ---------------------------------------------------------------------------
# Tests: V5 SSE event structure
# ---------------------------------------------------------------------------

class TestDiscoveryGraphV5Events:
    @pytest.mark.asyncio
    async def test_run_emits_sector_start_events(self, mock_db):
        """k_depth=1 run emits sector_start for each sector."""
        llm = MockLLM()
        graph = DiscoveryGraph(llm=llm, db=mock_db, manifest_id="test-v5-001")

        events = []
        async for event in graph.run("Test manifest", k_depth=1, instruction_texts=["TEST INSTRUCTION"]):
            events.append(event)

        sector_starts = [e for e in events if e["event"] == "sector_start"]
        assert len(sector_starts) == 3  # 3 neutral runtime sectors (no sector file)

    @pytest.mark.asyncio
    async def test_run_emits_sector_complete_events(self, mock_db):
        """k_depth=1 run emits sector_complete for each sector."""
        llm = MockLLM()
        graph = DiscoveryGraph(llm=llm, db=mock_db, manifest_id="test-v5-002")

        events = []
        async for event in graph.run("Test manifest", k_depth=1, instruction_texts=["TEST INSTRUCTION"]):
            events.append(event)

        sector_completes = [e for e in events if e["event"] == "sector_complete"]
        assert len(sector_completes) == 3  # 3 neutral runtime sectors (no sector file)

    @pytest.mark.asyncio
    async def test_run_emits_l1_assembly_complete(self, mock_db):
        """k_depth=1 run emits l1_assembly_complete after all sectors."""
        llm = MockLLM()
        graph = DiscoveryGraph(llm=llm, db=mock_db, manifest_id="test-v5-003")

        events = []
        async for event in graph.run("Test manifest", k_depth=1, instruction_texts=["TEST INSTRUCTION"]):
            events.append(event)

        assembly_events = [e for e in events if e["event"] == "l1_assembly_complete"]
        assert len(assembly_events) == 1
        assert "total_entities" in assembly_events[0]["data"]
        assert "sector_count" in assembly_events[0]["data"]

    @pytest.mark.asyncio
    async def test_run_ends_with_complete_event(self, mock_db):
        """Every run ends with a complete event."""
        llm = MockLLM()
        graph = DiscoveryGraph(llm=llm, db=mock_db, manifest_id="test-v5-004")

        events = []
        async for event in graph.run("Test manifest", k_depth=1, instruction_texts=["TEST INSTRUCTION"]):
            events.append(event)

        complete_events = [e for e in events if e["event"] == "complete"]
        assert len(complete_events) == 1
        assert "coverage_summary" in complete_events[0]["data"]

    @pytest.mark.asyncio
    async def test_k_depth_2_emits_entity_expansion_events(self, mock_db):
        """k_depth=2 run emits entity_expansion_start and entity_expansion_complete."""
        llm = MockLLM()
        graph = DiscoveryGraph(llm=llm, db=mock_db, manifest_id="test-v5-005")

        events = []
        async for event in graph.run("Test manifest", k_depth=2, instruction_texts=["TEST INSTRUCTION"]):
            events.append(event)

        expansion_starts = [e for e in events if e["event"] == "entity_expansion_start"]
        expansion_completes = [e for e in events if e["event"] == "entity_expansion_complete"]

        # Each sector returns 1 entity × 6 sectors = 6 entities → 6 expansion calls
        assert len(expansion_starts) >= 1
        assert len(expansion_completes) >= 1
        assert len(expansion_starts) == len(expansion_completes)

    @pytest.mark.asyncio
    async def test_k_depth_1_skips_expansion(self, mock_db):
        """k_depth=1 run does NOT emit entity_expansion events."""
        llm = MockLLM()
        graph = DiscoveryGraph(llm=llm, db=mock_db, manifest_id="test-v5-006")

        events = []
        async for event in graph.run("Test manifest", k_depth=1, instruction_texts=["TEST INSTRUCTION"]):
            events.append(event)

        expansion_events = [
            e for e in events
            if e["event"] in ("entity_expansion_start", "entity_expansion_complete")
        ]
        assert len(expansion_events) == 0

    @pytest.mark.asyncio
    async def test_custom_sector_list(self, mock_db):
        """Custom sector list (2 sectors) produces exactly 2 sector calls."""
        llm = MockLLM()
        graph = DiscoveryGraph(llm=llm, db=mock_db, manifest_id="test-v5-007")

        custom_sectors = [
            {"key": "federal", "label": "Federal/National", "priority": 1, "search_hints": []},
            {"key": "state_hfa", "label": "State HFA", "priority": 2, "search_hints": []},
        ]

        events = []
        async for event in graph.run("Test manifest", k_depth=1, sectors=custom_sectors, instruction_texts=["TEST INSTRUCTION"]):
            events.append(event)

        sector_starts = [e for e in events if e["event"] == "sector_start"]
        assert len(sector_starts) == 2

    @pytest.mark.asyncio
    async def test_sector_failure_does_not_abort(self, mock_db):
        """A failing sector call yields sector_complete with status=failed but run continues."""
        call_count = 0

        class FailOnFirstCallLLM(LLMProvider):
            async def complete(self, messages, **kwargs):
                nonlocal call_count
                call_count += 1
                if call_count == 1:
                    raise RuntimeError("Simulated API error")
                return json.dumps({
                    "administering_entities": [],
                    "programs": [],
                    "funding_streams": [],
                    "queue_state": {"visited_entities": [], "visited_sources": [], "next_actions": []},
                })

            async def stream(self, messages, **kwargs):
                yield '{}'

            async def complete_grounded(self, messages, **kwargs):
                text = await self.complete(messages, **kwargs)
                return text, []

        llm = FailOnFirstCallLLM()
        graph = DiscoveryGraph(llm=llm, db=mock_db, manifest_id="test-v5-008")

        custom_sectors = [
            {"key": "federal", "label": "Federal", "priority": 1, "search_hints": []},
            {"key": "state_hfa", "label": "State HFA", "priority": 2, "search_hints": []},
            {"key": "municipal", "label": "Municipal", "priority": 3, "search_hints": []},
        ]

        events = []
        async for event in graph.run("Test manifest", k_depth=1, sectors=custom_sectors, instruction_texts=["TEST INSTRUCTION"]):
            events.append(event)

        # All 3 sectors should complete (one with failed status)
        sector_completes = [e for e in events if e["event"] == "sector_complete"]
        assert len(sector_completes) == 3

        failed = [e for e in sector_completes if e["data"].get("status") == "failed"]
        assert len(failed) == 1

        # Run still reaches complete
        assert any(e["event"] == "complete" for e in events)

    @pytest.mark.asyncio
    async def test_complete_event_has_seed_metrics(self, mock_db):
        """complete event includes seed_recovery_rate and seed_match_rate_by_topic."""
        llm = MockLLM()
        graph = DiscoveryGraph(llm=llm, db=mock_db, manifest_id="test-v5-009")

        events = []
        async for event in graph.run(
            "Test manifest",
            k_depth=2,
            seed_index={"cdfi": [{"name": "CDFI Grant"}]},
            seed_programs=[{"name": "CDFI Grant", "program_type": "cdfi"}],
            instruction_texts=["TEST INSTRUCTION"],
        ):
            events.append(event)

        complete = [e for e in events if e["event"] == "complete"][0]
        assert "seed_recovery_rate" in complete["data"]
        assert "seed_match_rate_by_topic" in complete["data"]

    @pytest.mark.asyncio
    async def test_uses_complete_calls(self, mock_db):
        """Engine uses complete() for all LLM calls."""
        llm = MockLLM()
        graph = DiscoveryGraph(llm=llm, db=mock_db, manifest_id="test-v5-010")

        async for _ in graph.run("Test manifest", k_depth=1, instruction_texts=["TEST INSTRUCTION"]):
            pass

        assert len(llm.calls) >= 3  # at least 3 neutral runtime sector calls

    @pytest.mark.asyncio
    async def test_sector_scope_header_injected(self, mock_db):
        """Each sector call prompt contains the SECTOR SCOPE header."""
        llm = MockLLM()
        graph = DiscoveryGraph(llm=llm, db=mock_db, manifest_id="test-v5-011")

        async for _ in graph.run("Test manifest", k_depth=1, instruction_texts=["MY INSTRUCTION"]):
            pass

        sector_calls = [
            c for c in llm.calls
            if "sector scope" in c["prompt"].lower()
        ]
        assert len(sector_calls) >= 3  # 3 neutral runtime sector calls

    @pytest.mark.asyncio
    async def test_instruction_text_passed_to_calls(self, mock_db):
        """instruction_text is included verbatim in sector call prompts."""
        llm = MockLLM()
        graph = DiscoveryGraph(llm=llm, db=mock_db, manifest_id="test-v5-012")

        marker = "UNIQUE_INSTRUCTION_MARKER_XYZ"
        async for _ in graph.run("Test manifest", k_depth=1, instruction_texts=[marker]):
            pass

        calls_with_marker = [
            c for c in llm.calls if marker in c["prompt"]
        ]
        assert len(calls_with_marker) >= 3  # 3 neutral runtime sector calls each include instruction

    @pytest.mark.asyncio
    async def test_persists_entities_and_programs(self, mock_db):
        """RegulatoryBody and Program records are added to the DB."""
        llm = MockLLM()
        graph = DiscoveryGraph(llm=llm, db=mock_db, manifest_id="test-v5-013")

        async for _ in graph.run("Test manifest", k_depth=2, instruction_texts=["TEST INSTRUCTION"]):
            pass

        # db.add should have been called for entities, sources, programs, assessment
        assert mock_db.add.call_count >= 2
        assert mock_db.commit.call_count >= 2

    @pytest.mark.asyncio
    async def test_coverage_summary_per_sector(self, mock_db):
        """coverage_summary in complete event contains per-sector entries."""
        llm = MockLLM()
        graph = DiscoveryGraph(llm=llm, db=mock_db, manifest_id="test-v5-014")

        custom_sectors = [
            {"key": "federal", "label": "Federal", "priority": 1, "search_hints": []},
            {"key": "state_hfa", "label": "State HFA", "priority": 2, "search_hints": []},
        ]

        events = []
        async for event in graph.run("Test manifest", k_depth=1, sectors=custom_sectors, instruction_texts=["TEST INSTRUCTION"]):
            events.append(event)

        complete = [e for e in events if e["event"] == "complete"][0]
        summary = complete["data"]["coverage_summary"]
        assert "federal" in summary
        assert "state_hfa" in summary
        assert "entities_found" in summary["federal"]
        assert "programs_found" in summary["federal"]


# ---------------------------------------------------------------------------
# Tests: Utility methods (preserved from V4)
# ---------------------------------------------------------------------------

class TestDiscoveryGraphUtils:
    def test_dedupe_programs_keeps_highest_confidence(self):
        programs = [
            {"name": "CalHFA MyHome", "administering_entity": "CalHFA",
             "jurisdiction": "CA", "confidence": 0.8},
            {"name": "CalHFA MyHome", "administering_entity": "CalHFA",
             "jurisdiction": "CA", "confidence": 0.9},
            {"name": "Different Program", "administering_entity": "HUD",
             "jurisdiction": "US", "confidence": 0.7},
        ]
        result = DiscoveryGraph._dedupe_programs(programs)
        assert len(result) == 2
        calhfa = [p for p in result if "CalHFA" in p["name"]][0]
        assert calhfa["confidence"] == 0.9

    def test_normalize_name(self):
        assert DiscoveryGraph._normalize_name("CalHFA My-Home!") == "calhfamyhome"
        assert DiscoveryGraph._normalize_name("") == ""

    def test_canonical_program_id(self):
        pid = DiscoveryGraph._canonical_program_id({
            "name": "MyHome Assistance",
            "administering_entity": "CalHFA",
            "jurisdiction": "California",
        })
        assert "calhfa" in pid
        assert "myhome" in pid

    def test_compute_seed_match_rates(self):
        seeds = [
            {"name": "Program A", "program_type": "cdfi"},
            {"name": "Program B", "program_type": "cdfi"},
            {"name": "Program C", "program_type": "veteran"},
        ]
        discovered = [
            {"name": "Program A"},
            {"name": "Other Program"},
        ]
        seed_index = {
            "cdfi": [{"name": "Program A"}, {"name": "Program B"}],
            "veteran": [{"name": "Program C"}],
        }
        rates = DiscoveryGraph._compute_seed_match_rates(seeds, discovered, seed_index)
        assert rates["cdfi"]["total"] == 2
        assert rates["cdfi"]["matched"] == 1
        assert rates["cdfi"]["rate"] == 0.5
        assert rates["veteran"]["matched"] == 0

    def test_event_helper(self):
        event = DiscoveryGraph._event("sector_start", sector_key="federal")
        assert event["event"] == "sector_start"
        assert event["data"]["sector_key"] == "federal"


# ---------------------------------------------------------------------------
# Tests: Seed-to-entity mapping (preserved)
# ---------------------------------------------------------------------------

class TestSeedToEntityMapping:
    def test_all_seed_types_mapped(self):
        from app.routers.manifests import _PROGRAM_TYPE_KEYWORDS
        for ptype in _PROGRAM_TYPE_KEYWORDS:
            assert ptype in _SEED_TO_ENTITY_TYPE, f"Missing mapping for {ptype}"

    def test_seed_to_entity_type_coverage(self):
        entity_types = set(_SEED_TO_ENTITY_TYPE.values())
        for required in ("federal", "state_hfa", "municipal", "employer", "tribal"):
            assert required in entity_types, (
                f"Required entity type '{required}' missing from _SEED_TO_ENTITY_TYPE values"
            )


# ---------------------------------------------------------------------------
# Multi-Prompt L1 Loop Tests
# ---------------------------------------------------------------------------

class TestMultiPromptL1Loop:
    """Tests for _run_l1_prompts() serial coordinator."""

    @pytest.mark.asyncio
    async def test_multi_prompt_fires_all_sector_passes(self, mock_db):
        """With N instruction_texts, the engine fires N full sector passes."""
        llm = MockLLM()
        graph = DiscoveryGraph(llm=llm, db=mock_db, manifest_id="test-mp-001")

        events = []
        async for event in graph.run(
            "Test manifest",
            k_depth=1,
            instruction_texts=["PROMPT ONE", "PROMPT TWO"],
        ):
            events.append(event)

        prompt_starts = [e for e in events if e["event"] == "prompt_start"]
        prompt_completes = [e for e in events if e["event"] == "prompt_complete"]
        assert len(prompt_starts) == 2
        assert len(prompt_completes) == 2

    @pytest.mark.asyncio
    async def test_multi_prompt_sector_calls_multiply(self, mock_db):
        """With N prompts and M sectors, total sector calls = N * M."""
        llm = MockLLM()
        graph = DiscoveryGraph(llm=llm, db=mock_db, manifest_id="test-mp-002")

        custom_sectors = [
            {"key": "alpha", "label": "Alpha", "priority": 1},
            {"key": "beta", "label": "Beta", "priority": 2},
        ]

        async for _ in graph.run(
            "Test manifest",
            k_depth=1,
            sectors=custom_sectors,
            instruction_texts=["PROMPT ONE", "PROMPT TWO"],
        ):
            pass

        sector_calls = [c for c in llm.calls if "SECTOR SCOPE" in c["prompt"].upper()]
        # 2 prompts x 2 sectors = 4 sector calls
        assert len(sector_calls) == 4

    @pytest.mark.asyncio
    async def test_single_prompt_backwards_compatible(self, mock_db):
        """Single instruction_texts list item is identical to old single-prompt behaviour."""
        llm = MockLLM()
        graph = DiscoveryGraph(llm=llm, db=mock_db, manifest_id="test-mp-003")

        events = []
        async for event in graph.run(
            "Test manifest",
            k_depth=1,
            instruction_texts=["SINGLE PROMPT"],
        ):
            events.append(event)

        prompt_starts = [e for e in events if e["event"] == "prompt_start"]
        assert len(prompt_starts) == 1

    @pytest.mark.asyncio
    async def test_empty_instruction_texts_raises(self, mock_db):
        """Empty instruction_texts list raises ValueError."""
        llm = MockLLM()
        graph = DiscoveryGraph(llm=llm, db=mock_db, manifest_id="test-mp-004")

        with pytest.raises(ValueError, match="instruction_texts is required"):
            async for _ in graph.run("Test manifest", k_depth=1, instruction_texts=[]):
                pass


class TestCheckpointQueue:
    """Tests for DiscoveryQueue snapshot serialization round-trip."""

    def test_to_snapshot_captures_heap_and_visited(self):
        from app.agent.discovery_queue import DiscoveryQueue

        q = DiscoveryQueue(max_depth=3, max_size=100)
        q.enqueue(target_type="entity", target_id="entity-a", priority=1, depth=0)
        q.enqueue(target_type="entity", target_id="entity-b", priority=2, depth=1)

        snap = q.to_snapshot()
        assert len(snap["queue_items"]) == 2
        assert "entity-a" in snap["visited"]
        assert "entity-b" in snap["visited"]
        assert snap["max_depth"] == 3
        assert snap["max_size"] == 100

    def test_from_snapshot_restores_queue(self):
        from app.agent.discovery_queue import DiscoveryQueue

        q = DiscoveryQueue(max_depth=3, max_size=100)
        q.enqueue(target_type="entity", target_id="entity-x", priority=1, depth=0, metadata={"name": "X Entity"})
        q.enqueue(target_type="source", target_id="source-y", priority=2, depth=1)
        snap = q.to_snapshot()

        restored = DiscoveryQueue.from_snapshot(snap)
        assert restored.size() == 2
        assert restored.is_visited("entity-x")
        assert restored.is_visited("source-y")
        assert restored.max_depth == 3

    def test_round_trip_preserves_priority_order(self):
        from app.agent.discovery_queue import DiscoveryQueue

        q = DiscoveryQueue(max_depth=3)
        q.enqueue(target_type="entity", target_id="low", priority=10, depth=0)
        q.enqueue(target_type="entity", target_id="high", priority=1, depth=0)
        snap = q.to_snapshot()

        restored = DiscoveryQueue.from_snapshot(snap)
        first = restored.pop()
        assert first is not None
        assert first.target_id == "high"  # priority=1 pops first

    def test_visited_set_prevents_reenqueue_after_restore(self):
        from app.agent.discovery_queue import DiscoveryQueue

        q = DiscoveryQueue(max_depth=3)
        q.enqueue(target_type="entity", target_id="seen-entity", priority=1, depth=0)
        snap = q.to_snapshot()

        restored = DiscoveryQueue.from_snapshot(snap)
        result = restored.enqueue(target_type="entity", target_id="seen-entity", priority=1, depth=0)
        assert result is False  # already visited

    def test_l1_boundary_checkpoint_shape(self):
        """Checkpoint dict must contain required plan-spec fields."""
        from app.agent.discovery_queue import DiscoveryQueue

        q = DiscoveryQueue(max_depth=3)
        q.enqueue(target_type="entity", target_id="ent-1", priority=1, depth=0)
        snap = q.to_snapshot()

        checkpoint = {
            "type": "l1_boundary",
            "batch_n": 0,
            "api_calls_used": 42,
            "queue_items": snap["queue_items"],
            "visited": snap["visited"],
            "written_at": "2026-03-11T00:00:00Z",
        }
        assert checkpoint["type"] == "l1_boundary"
        assert len(checkpoint["queue_items"]) == 1


class TestResumeRoute:
    """Tests for the resume route and run_resumed()."""

    @pytest.mark.asyncio
    async def test_run_resumed_emits_resume_start_and_complete(self, mock_db):
        """run_resumed() must emit resume_start and complete events."""
        from app.agent.discovery_queue import DiscoveryQueue

        q = DiscoveryQueue(max_depth=2)
        # No items — queue is empty, loop terminates immediately
        snap = q.to_snapshot()
        checkpoint = {
            "type": "l1_boundary",
            "batch_n": 0,
            "api_calls_used": 10,
            **snap,
        }

        llm = MockLLM()
        graph = DiscoveryGraph(llm=llm, db=mock_db, manifest_id="test-resume-001")

        events = []
        async for event in graph.run_resumed("Test manifest", checkpoint=checkpoint, k_depth=2):
            events.append(event)

        event_types = [e["event"] for e in events]
        assert "resume_start" in event_types
        assert "complete" in event_types

    @pytest.mark.asyncio
    async def test_run_resumed_processes_queued_items(self, mock_db):
        """run_resumed() with items in queue fires entity_expansion_start events."""
        from app.agent.discovery_queue import DiscoveryQueue

        q = DiscoveryQueue(max_depth=2)
        q.enqueue(
            target_type="entity",
            target_id="nj-dobi",
            priority=1,
            depth=1,
            metadata={"name": "NJ DOBI", "jurisdiction": "state"},
        )
        snap = q.to_snapshot()
        checkpoint = {
            "type": "l1_boundary",
            "batch_n": 0,
            "api_calls_used": 50,
            **snap,
        }

        llm = MockLLM()
        graph = DiscoveryGraph(llm=llm, db=mock_db, manifest_id="test-resume-002")

        events = []
        async for event in graph.run_resumed("Test manifest", checkpoint=checkpoint, k_depth=2):
            events.append(event)

        expansion_starts = [e for e in events if e["event"] == "entity_expansion_start"]
        assert len(expansion_starts) == 1
        assert expansion_starts[0]["data"]["entity_id"] == "nj-dobi"

    @pytest.mark.asyncio
    async def test_run_resumed_restores_visited_set(self, mock_db):
        """Entities in visited set from checkpoint must not be re-enqueued."""
        from app.agent.discovery_queue import DiscoveryQueue

        q = DiscoveryQueue(max_depth=2)
        q.enqueue(
            target_type="entity",
            target_id="entity-already-done",
            priority=1,
            depth=1,
            metadata={"name": "Done Entity"},
        )
        snap = q.to_snapshot()
        # Pop the item so queue is empty but visited set still has it
        q.pop()
        empty_snap = q.to_snapshot()
        assert len(empty_snap["queue_items"]) == 0
        assert "entity-already-done" in empty_snap["visited"]

        checkpoint = {
            "type": "l2_batch",
            "batch_n": 1,
            "api_calls_used": 100,
            **empty_snap,
        }

        llm = MockLLM()
        graph = DiscoveryGraph(llm=llm, db=mock_db, manifest_id="test-resume-003")

        events = []
        async for event in graph.run_resumed("Test manifest", checkpoint=checkpoint, k_depth=2):
            events.append(event)

        # Queue was empty, so no expansions should occur
        expansion_starts = [e for e in events if e["event"] == "entity_expansion_start"]
        assert len(expansion_starts) == 0

