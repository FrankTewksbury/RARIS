"""Tests for hierarchical graph discovery engine (DiscoveryGraph)."""

import json
import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from app.agent.graph_discovery import DiscoveryGraph, _SEED_TO_ENTITY_TYPE, _ENTITY_SEARCH_QUERIES
from app.llm.base import Citation, LLMProvider


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

class MockLLM(LLMProvider):
    """Mock LLM that returns canned JSON responses."""

    def __init__(self, responses: dict[str, str] | None = None):
        self._responses = responses or {}
        self._call_count = 0
        self.grounded_calls: list[dict] = []

    async def complete(self, messages, **kwargs):
        self._call_count += 1
        return '{"programs": []}'

    async def stream(self, messages, **kwargs):
        yield '{"programs": []}'

    async def complete_grounded(self, messages, **kwargs):
        self._call_count += 1
        prompt = messages[-1]["content"] if messages else ""
        self.grounded_calls.append({"prompt": prompt[:200], "kwargs": kwargs})

        # Determine which response to return based on prompt content
        if "regulatory domain" in prompt.lower() or "landscape" in prompt.lower():
            text = self._responses.get("landscape", json.dumps({
                "regulatory_bodies": [
                    {
                        "id": "hud",
                        "name": "HUD",
                        "jurisdiction": "federal",
                        "authority_type": "regulator",
                        "url": "https://hud.gov",
                        "governs": ["housing"],
                    }
                ],
                "jurisdiction_hierarchy": {
                    "federal": {"bodies": ["hud"], "count": 1},
                    "state": {"bodies": [], "count": 0},
                    "municipal": {"bodies": [], "count": 0},
                },
            }))
        elif "source documents" in prompt.lower() or "source hunter" in prompt.lower():
            text = self._responses.get("sources", json.dumps({
                "sources": [
                    {
                        "id": "src-001",
                        "name": "HUD DPA Guide",
                        "regulatory_body": "hud",
                        "type": "guidance",
                        "format": "html",
                        "authority": "informational",
                        "jurisdiction": "federal",
                        "url": "https://hud.gov/dpa",
                        "access_method": "scrape",
                        "confidence": 0.9,
                        "needs_human_review": False,
                    }
                ]
            }))
        elif "entity type" in prompt.lower() or "expand" in prompt.lower():
            text = self._responses.get("expansion", json.dumps({
                "entities": [
                    {
                        "id": "cdfi-example",
                        "name": "Example CDFI",
                        "type": "nonprofit",
                        "url": "https://example-cdfi.org",
                        "jurisdiction": "state",
                        "programs": [
                            {
                                "name": "CDFI DPA Grant",
                                "administering_entity": "Example CDFI",
                                "geo_scope": "state",
                                "jurisdiction": "California",
                                "benefits": "Up to $10,000 grant",
                                "eligibility": "LMI households",
                                "status": "active",
                                "evidence_snippet": "CDFI grant program",
                                "source_urls": ["https://example-cdfi.org/dpa"],
                                "confidence": 0.8,
                                "needs_human_review": False,
                            }
                        ],
                    }
                ]
            }))
        elif "gap" in prompt.lower() or "unmatched" in prompt.lower():
            text = self._responses.get("gap_fill", json.dumps({
                "programs": [
                    {
                        "name": "Gap Fill Program",
                        "administering_entity": "Gap Fill Entity",
                        "geo_scope": "state",
                        "jurisdiction": "Texas",
                        "benefits": "Forgivable loan",
                        "eligibility": "FTHB",
                        "status": "active",
                        "evidence_snippet": "Found via web search",
                        "source_urls": ["https://gapfill.gov"],
                        "confidence": 0.7,
                        "needs_human_review": True,
                    }
                ],
                "gap_fill_summary": {
                    "seeds_recovered": 1,
                    "new_programs_found": 1,
                    "categories_searched": ["municipal"],
                },
            }))
        else:
            text = '{"programs": []}'

        citations = [Citation(url="https://hud.gov", title="HUD")]
        return text, citations


@pytest.fixture
def mock_db():
    """Create a mock async database session."""
    db = AsyncMock()
    db.add = MagicMock()
    db.flush = AsyncMock()
    db.commit = AsyncMock()

    # Mock manifest retrieval
    mock_manifest = MagicMock()
    mock_manifest.jurisdiction_hierarchy = None
    mock_manifest.status = None
    mock_manifest.completeness_score = None
    db.get = AsyncMock(return_value=mock_manifest)

    return db


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

class TestDiscoveryGraphInit:
    def test_instantiation(self, mock_db):
        llm = MockLLM()
        graph = DiscoveryGraph(llm=llm, db=mock_db, manifest_id="test-001")
        assert graph.manifest_id == "test-001"


class TestDiscoveryGraphRun:
    @pytest.mark.asyncio
    async def test_full_run_yields_events(self, mock_db):
        """Full L0-L3 run yields expected SSE events."""
        llm = MockLLM()
        graph = DiscoveryGraph(llm=llm, db=mock_db, manifest_id="test-001")

        events = []
        async for event in graph.run(
            "Down payment assistance programs in the US",
            seed_index={"cdfi": [{"name": "CDFI Program", "program_type": "cdfi"}]},
            seed_programs=[{"name": "CDFI Program", "program_type": "cdfi"}],
        ):
            events.append(event)

        event_types = [e["event"] for e in events]
        assert "step" in event_types
        assert "complete" in event_types

        # Check that complete event has required fields
        complete_event = [e for e in events if e["event"] == "complete"][0]
        assert "total_sources" in complete_event["data"]
        assert "total_programs" in complete_event["data"]
        assert "seed_recovery_rate" in complete_event["data"]
        assert "seed_match_rate_by_topic" in complete_event["data"]

    @pytest.mark.asyncio
    async def test_discovery_levels_in_events(self, mock_db):
        """Events include discovery_level field."""
        llm = MockLLM()
        graph = DiscoveryGraph(llm=llm, db=mock_db, manifest_id="test-002")

        events = []
        async for event in graph.run("DPA programs"):
            events.append(event)

        step_events = [e for e in events if e["event"] == "step"]
        levels_seen = set()
        for e in step_events:
            if "discovery_level" in e["data"]:
                levels_seen.add(e["data"]["discovery_level"])

        assert 0 in levels_seen  # L0
        assert 1 in levels_seen  # L1
        assert 2 in levels_seen  # L2
        assert 3 in levels_seen  # L3

    @pytest.mark.asyncio
    async def test_cumulative_programs_in_step_events(self, mock_db):
        """Step events include cumulative_programs for progress tracking."""
        llm = MockLLM()
        graph = DiscoveryGraph(llm=llm, db=mock_db, manifest_id="test-metrics-1")

        events = []
        async for event in graph.run(
            "DPA programs",
            seed_index={"cdfi": [{"name": "CDFI Program"}]},
            seed_programs=[{"name": "CDFI Program"}],
        ):
            events.append(event)

        # All completed step events should have cumulative_programs
        completed_steps = [
            e for e in events
            if e["event"] == "step" and e["data"].get("status") == "complete"
        ]
        for step in completed_steps:
            assert "cumulative_programs" in step["data"], (
                f"Step {step['data'].get('step')} missing cumulative_programs"
            )

    @pytest.mark.asyncio
    async def test_nodes_at_level_in_step_events(self, mock_db):
        """L0 landscape and L1 expansion emit nodes_at_level."""
        llm = MockLLM()
        graph = DiscoveryGraph(llm=llm, db=mock_db, manifest_id="test-metrics-2")

        events = []
        async for event in graph.run("DPA programs"):
            events.append(event)

        # L0 landscape complete should have nodes_at_level
        l0_landscape = [
            e for e in events
            if e["event"] == "step"
            and e["data"].get("step") == "L0_landscape"
            and e["data"].get("status") == "complete"
        ]
        assert len(l0_landscape) == 1
        assert "nodes_at_level" in l0_landscape[0]["data"]
        assert l0_landscape[0]["data"]["nodes_at_level"] >= 1

        # L1 expansion complete should have nodes_at_level
        l1_complete = [
            e for e in events
            if e["event"] == "step"
            and e["data"].get("step") == "L1_expansion"
            and e["data"].get("status") == "complete"
        ]
        assert len(l1_complete) == 1
        assert "nodes_at_level" in l1_complete[0]["data"]

    @pytest.mark.asyncio
    async def test_seed_match_rate_by_topic_structure(self, mock_db):
        """Complete event seed_match_rate_by_topic has correct structure."""
        llm = MockLLM()
        graph = DiscoveryGraph(llm=llm, db=mock_db, manifest_id="test-metrics-3")

        events = []
        async for event in graph.run(
            "DPA programs",
            seed_index={
                "cdfi": [{"name": "CDFI Program"}],
                "veteran": [{"name": "VA DPA"}],
            },
            seed_programs=[
                {"name": "CDFI Program", "program_type": "cdfi"},
                {"name": "VA DPA", "program_type": "veteran"},
            ],
        ):
            events.append(event)

        complete = [e for e in events if e["event"] == "complete"][0]
        rates = complete["data"]["seed_match_rate_by_topic"]
        assert isinstance(rates, dict)
        # Both seed topics should appear
        assert "cdfi" in rates
        assert "veteran" in rates
        # Rates are floats between 0 and 1
        for topic, rate in rates.items():
            assert 0.0 <= rate <= 1.0

    @pytest.mark.asyncio
    async def test_uses_grounded_calls(self, mock_db):
        """Verify that grounded (web search) LLM calls are used."""
        llm = MockLLM()
        graph = DiscoveryGraph(llm=llm, db=mock_db, manifest_id="test-003")

        async for _ in graph.run("DPA programs"):
            pass

        # At minimum: L0 landscape + L0 source hunter + L1 expansions
        assert len(llm.grounded_calls) >= 2

    @pytest.mark.asyncio
    async def test_seed_index_routing(self, mock_db):
        """Seeds are routed to the correct entity types for expansion."""
        llm = MockLLM()
        graph = DiscoveryGraph(llm=llm, db=mock_db, manifest_id="test-004")

        seed_index = {
            "cdfi": [{"name": "CDFI Grant", "program_type": "cdfi"}],
            "veteran": [{"name": "VA Grant", "program_type": "veteran"}],
        }

        async for _ in graph.run(
            "DPA programs",
            seed_index=seed_index,
            seed_programs=[
                {"name": "CDFI Grant", "program_type": "cdfi"},
                {"name": "VA Grant", "program_type": "veteran"},
            ],
        ):
            pass

        # L1 expansion should have been called for entity types
        expansion_calls = [
            c for c in llm.grounded_calls
            if "entity type" in c["prompt"].lower() or "expand" in c["prompt"].lower()
        ]
        assert len(expansion_calls) >= 1

    @pytest.mark.asyncio
    async def test_persists_bodies_and_sources(self, mock_db):
        """Regulatory bodies and sources are persisted to DB."""
        llm = MockLLM()
        graph = DiscoveryGraph(llm=llm, db=mock_db, manifest_id="test-005")

        async for _ in graph.run("DPA programs"):
            pass

        # db.add should have been called for bodies + sources + programs
        assert mock_db.add.call_count >= 2  # At least 1 body + 1 source
        assert mock_db.commit.call_count >= 2  # L0 sources commit + final commit

    @pytest.mark.asyncio
    async def test_l3_gap_fill_runs(self, mock_db):
        """L3 gap fill runs when there are unmatched seeds."""
        llm = MockLLM()
        graph = DiscoveryGraph(llm=llm, db=mock_db, manifest_id="test-006")

        async for _ in graph.run(
            "DPA programs",
            seed_programs=[
                {"name": "Unmatched Program X", "program_type": "municipal"},
            ],
            seed_index={"municipal": [{"name": "Unmatched Program X"}]},
        ):
            pass

        # L3 gap fill should have been attempted
        gap_calls = [
            c for c in llm.grounded_calls
            if "gap" in c["prompt"].lower() or "unmatched" in c["prompt"].lower()
        ]
        assert len(gap_calls) >= 1


class TestDiscoveryGraphUtils:
    def test_dedupe_programs(self):
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
        # Higher confidence should win
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
        event = DiscoveryGraph._event("step", step="L0", status="running")
        assert event["event"] == "step"
        assert event["data"]["step"] == "L0"


class TestSeedToEntityMapping:
    def test_all_seed_types_mapped(self):
        """Every seed type in the keyword dict has an entity mapping."""
        from app.routers.manifests import _PROGRAM_TYPE_KEYWORDS
        for ptype in _PROGRAM_TYPE_KEYWORDS:
            assert ptype in _SEED_TO_ENTITY_TYPE, f"Missing mapping for {ptype}"

    def test_entity_search_queries_exist(self):
        """Entity types referenced by seed mapping have search queries."""
        entity_types = set(_SEED_TO_ENTITY_TYPE.values())
        # Not all entity types need queries (federal is in training data)
        for etype in ("municipal", "nonprofit", "employer", "tribal", "cdfi"):
            assert etype in _ENTITY_SEARCH_QUERIES, f"Missing query for {etype}"
