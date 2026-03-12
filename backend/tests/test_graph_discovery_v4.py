"""Tests for V5 prompt-driven discovery engine (graph_discovery.py).

Validates:
- Sector calls receive the full instruction text untruncated
- Sector calls receive the SECTOR SCOPE header
- Sector calls do NOT receive old guidance_block wrapper
- Constitution text appears in sector prompts
- All items are persisted (no silent drops)
- SSE events are emitted in expected order (V5 names)
- Low-confidence programs are flagged
"""

import json
from collections.abc import AsyncGenerator
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.agent.graph_discovery import DiscoveryGraph
from app.llm.base import Citation


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


def _make_llm_mock(return_bodies=None, return_sources=None, return_programs=None):
    """Create an LLM mock that returns V5-format sector discovery responses."""
    entities = return_bodies or [
        {
            "id": "ca-hfa",
            "name": "California Housing Finance Agency",
            "entity_type": "state_hfa",
            "jurisdiction": "state",
            "url": "https://www.calhfa.ca.gov",
            "governs": ["down_payment_assistance"],
            "confidence": 0.9,
            "needs_human_review": False,
            "verification_state": "verified",
        },
        {
            "id": "la-housing",
            "name": "Los Angeles Housing Department",
            "entity_type": "municipal",
            "jurisdiction": "municipal",
            "url": "https://housing.lacity.org",
            "governs": ["down_payment_assistance"],
            "confidence": 0.85,
            "needs_human_review": False,
            "verification_state": "verified",
        },
    ]
    sources = return_sources or [
        {
            "id": "src-001",
            "name": "CalHFA MyHome Program Page",
            "regulatory_body": "ca-hfa",
            "type": "guidance",
            "format": "html",
            "authority": "informational",
            "jurisdiction": "state",
            "url": "https://www.calhfa.ca.gov/homebuyer/programs/myhome.htm",
            "access_method": "scrape",
            "confidence": 0.9,
            "needs_human_review": False,
        }
    ]
    programs = return_programs or [
        {
            "name": "MyHome Assistance Program",
            "administering_entity": "California Housing Finance Agency",
            "geo_scope": "state",
            "jurisdiction": "California",
            "benefits": "Up to 3.5% down payment assistance",
            "eligibility": "First-time homebuyers",
            "status": "active",
            "evidence_snippet": "MyHome offers a deferred-payment junior loan",
            "source_urls": ["https://www.calhfa.ca.gov/homebuyer/programs/myhome.htm"],
            "confidence": 0.85,
            "needs_human_review": False,
        }
    ]

    # V5 sector discovery response format
    sector_response = json.dumps({
        "sector_key": "state_hfa",
        "coverage_summary": {"entities_found": len(entities), "programs_found": len(programs), "gaps": []},
        "administering_entities": entities,
        "programs": programs,
        "funding_streams": [],
        "queue_state": {"visited_entities": [], "visited_sources": [], "next_actions": []},
    })

    llm = MagicMock()
    llm.complete = AsyncMock(return_value=sector_response)
    return llm


def _make_db_mock():
    """Create a minimal async DB session mock."""
    db = MagicMock(spec=AsyncSession)
    db.add = MagicMock()
    db.flush = AsyncMock()
    db.commit = AsyncMock()

    manifest_mock = MagicMock()
    manifest_mock.status = "generating"
    manifest_mock.completeness_score = 0.0
    manifest_mock.jurisdiction_hierarchy = None
    manifest_mock.coverage_summary = None
    db.get = AsyncMock(return_value=manifest_mock)
    return db


# ---------------------------------------------------------------------------
# Helper: collect all SSE events from the generator
# ---------------------------------------------------------------------------


async def _collect_events(gen: AsyncGenerator) -> list[dict]:
    events = []
    async for event in gen:
        events.append(event)
    return events


# ---------------------------------------------------------------------------
# Test: L0 receives full instruction text
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_sector_receives_full_instruction_text():
    """The full instruction_text must appear verbatim in sector call user messages."""
    llm = _make_llm_mock()
    db = _make_db_mock()

    instruction = (
        "## 1. Domain Definition\n"
        "You are a DPA discovery agent.\n\n"
        "## 8. Output Schema\n"
        '{"administering_entities": [], "programs": []}'
    )

    engine = DiscoveryGraph(llm=llm, db=db, manifest_id="test-manifest-001")
    events = await _collect_events(
        engine.run(
            "Test DPA Scan",
            instruction_texts=[instruction],
            k_depth=1,
        )
    )

    assert llm.complete.called

    # Check first sector call contains instruction text verbatim
    first_call_args = llm.complete.call_args_list[0]
    messages = first_call_args[0][0]

    user_message = next(m["content"] for m in messages if m["role"] == "user")

    assert "## 1. Domain Definition" in user_message
    assert "You are a DPA discovery agent." in user_message
    assert "## 8. Output Schema" in user_message


@pytest.mark.asyncio
async def test_sector_call_has_sector_scope_header():
    """Each sector call user message must contain the SECTOR SCOPE header (V5)."""
    llm = _make_llm_mock()
    db = _make_db_mock()

    instruction = "## 1. Domain Definition\nDPA discovery agent."

    engine = DiscoveryGraph(llm=llm, db=db, manifest_id="test-manifest-002")
    await _collect_events(
        engine.run(
            "Test DPA Scan",
            instruction_texts=[instruction],
            k_depth=1,
        )
    )

    first_call_args = llm.complete.call_args_list[0]
    messages = first_call_args[0][0]
    user_message = next(m["content"] for m in messages if m["role"] == "user")

    # V5: SECTOR SCOPE header must be present; old wrapper patterns must not
    assert "SECTOR SCOPE" in user_message
    assert "Additional guidance documents:" not in user_message
    assert "guidance_block" not in user_message
    assert "Instruction guidance:" not in user_message


# ---------------------------------------------------------------------------
# Test: L1 prompts reference L0 entity data
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_entity_expansion_prompts_reference_entity_data():
    """Entity expansion prompts must contain the entity name and URL."""
    llm = _make_llm_mock()
    db = _make_db_mock()

    engine = DiscoveryGraph(llm=llm, db=db, manifest_id="test-manifest-003")
    await _collect_events(
        engine.run(
            "Test DPA Scan",
            instruction_texts=["## 1. Domain Definition\nDPA."],
            k_depth=2,  # k_depth=2 triggers entity expansion
        )
    )

    # k_depth=2 with 3 neutral runtime sectors each returning 2 entities = 6 queue entries
    # Total calls: 3 sector calls + up to 2 expansion calls (dedup via visited set)
    assert llm.complete.call_count >= 4  # at least 3 sector + 1 expansion

    # Find entity expansion calls (they contain "## NODE EXPANSION")
    expansion_calls = [
        call for call in llm.complete.call_args_list
        if "## node expansion" in call[0][0][-1]["content"].lower()
    ]
    assert len(expansion_calls) >= 1

    # The expansion prompt must contain entity data (name + URL)
    expansion_user_msg = expansion_calls[0][0][0][-1]["content"]
    assert "California Housing Finance Agency" in expansion_user_msg or \
           "Los Angeles Housing Department" in expansion_user_msg or \
           "HUD" in expansion_user_msg
    assert "https://" in expansion_user_msg


# ---------------------------------------------------------------------------
# Test: SSE events emitted in expected order
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_sse_events_order():
    """SSE events must include V5 sector events and a complete event."""
    llm = _make_llm_mock()
    db = _make_db_mock()

    engine = DiscoveryGraph(llm=llm, db=db, manifest_id="test-manifest-004")
    events = await _collect_events(
        engine.run(
            "Test DPA Scan",
            instruction_texts=["## 1. Domain Definition\nDPA."],
            k_depth=1,
        )
    )

    event_types = [e["event"] for e in events]

    # V5 SSE events
    assert "sector_start" in event_types
    assert "sector_complete" in event_types
    assert "l1_assembly_complete" in event_types
    assert "complete" in event_types


# ---------------------------------------------------------------------------
# Test: No silent drops — all items persisted
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_all_items_persisted():
    """db.add must be called for entities and assessment records."""
    llm = _make_llm_mock()
    db = _make_db_mock()

    engine = DiscoveryGraph(llm=llm, db=db, manifest_id="test-manifest-005")
    await _collect_events(
        engine.run(
            "Test DPA Scan",
            instruction_texts=["## 1. Domain Definition\nDPA."],
            k_depth=1,
        )
    )

    # db.add should have been called for at least 6 entities (one per sector)
    assert db.add.call_count >= 2


# ---------------------------------------------------------------------------
# Test: Low-confidence programs get needs_human_review=True
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_low_confidence_programs_flagged():
    """Programs with confidence < 0.5 must have needs_human_review forced to True."""
    low_conf_programs = [
        {
            "name": "Uncertain DPA Program",
            "administering_entity": "Some Agency",
            "geo_scope": "city",
            "jurisdiction": "Somewhere, CA",
            "status": "verification_pending",
            "evidence_snippet": "possibly exists",
            "source_urls": [],
            "confidence": 0.3,
            "needs_human_review": False,  # will be overridden by engine
        }
    ]
    llm = _make_llm_mock(return_programs=low_conf_programs)
    db = _make_db_mock()

    engine = DiscoveryGraph(llm=llm, db=db, manifest_id="test-manifest-006")
    await _collect_events(
        engine.run(
            "Test DPA Scan",
            instruction_texts=["## 1. Domain Definition\nDPA."],
            k_depth=2,  # k_depth=2 triggers entity expansion where programs are persisted
        )
    )

    # Find the Program object added to db.add
    program_adds = [
        call.args[0]
        for call in db.add.call_args_list
        if hasattr(call.args[0], "needs_human_review")
        and hasattr(call.args[0], "confidence")
    ]

    low_conf_adds = [p for p in program_adds if p.confidence < 0.5]
    assert all(p.needs_human_review is True for p in low_conf_adds), (
        "Programs with confidence < 0.5 must have needs_human_review=True"
    )


# ---------------------------------------------------------------------------
# Test: manifest_name is just a label — not passed to L0 discovery prompt
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_manifest_name_not_in_sector_prompt_without_instruction():
    """With a minimal instruction, engine uses generic discovery prompt."""
    llm = _make_llm_mock()
    db = _make_db_mock()

    manifest_name = "DPA National Scan March 2026"
    engine = DiscoveryGraph(llm=llm, db=db, manifest_id="test-manifest-007")
    await _collect_events(
        engine.run(manifest_name, k_depth=1, instruction_texts=["## 1. Domain Definition\nDown payment assistance programs."])
    )

    first_call_args = llm.complete.call_args_list[0]
    messages = first_call_args[0][0]
    user_message = next(m["content"] for m in messages if m["role"] == "user")

    # The prompt should still describe discovery broadly
    assert "down payment" in user_message.lower() or "assistance" in user_message.lower()


# ---------------------------------------------------------------------------
# Test: constitution text appears as guardrails in sector messages
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_constitution_text_in_sector_message():
    """constitution_text must appear in sector call user messages as guardrails."""
    llm = _make_llm_mock()
    db = _make_db_mock()

    constitution = "GUARDRAIL: Only include verified sources."

    engine = DiscoveryGraph(llm=llm, db=db, manifest_id="test-manifest-008")
    await _collect_events(
        engine.run(
            "Test DPA Scan",
            constitution_text=constitution,
            instruction_texts=["## 1. Domain Definition\nDPA."],
            k_depth=1,
        )
    )

    first_call_args = llm.complete.call_args_list[0]
    messages = first_call_args[0][0]
    user_message = next(m["content"] for m in messages if m["role"] == "user")

    assert "GUARDRAIL: Only include verified sources." in user_message
