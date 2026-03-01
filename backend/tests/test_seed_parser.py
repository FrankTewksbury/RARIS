"""Tests for topic-indexed seed parser (_infer_program_type, _index_seeds_by_type)."""

import pytest

from app.routers.manifests import (
    _infer_program_type,
    _index_seeds_by_type,
    _normalize_program_seed,
)


# ---------------------------------------------------------------------------
# _infer_program_type — keyword inference
# ---------------------------------------------------------------------------

class TestInferProgramType:
    def test_explicit_program_type_field(self):
        record = {"name": "Some Program", "program_type": "CDFI"}
        assert _infer_program_type(record) == "cdfi"

    def test_explicit_category_field(self):
        record = {"name": "Some Program", "category": "Veteran"}
        assert _infer_program_type(record) == "veteran"

    def test_program_type_takes_precedence_over_keywords(self):
        """Explicit program_type overrides keyword matching."""
        record = {
            "name": "VA Home Loan Program",
            "program_type": "general",
        }
        assert _infer_program_type(record) == "general"

    def test_veteran_keyword_in_name(self):
        record = {"name": "California Veterans Housing Program"}
        assert _infer_program_type(record) == "veteran"

    def test_military_keyword(self):
        record = {"name": "Military Family Housing Assistance"}
        assert _infer_program_type(record) == "veteran"

    def test_tribal_keyword_in_name(self):
        record = {"name": "Tribal Housing Authority DPA"}
        assert _infer_program_type(record) == "tribal"

    def test_section_184(self):
        record = {"eligibility": "Must qualify under Section 184 program"}
        assert _infer_program_type(record) == "tribal"

    def test_native_american(self):
        record = {"name": "Native American Homeownership Program"}
        assert _infer_program_type(record) == "tribal"

    def test_teacher_occupation(self):
        record = {"eligibility": "Must be a current teacher in the district"}
        assert _infer_program_type(record) == "occupation"

    def test_good_neighbor_next_door(self):
        record = {"name": "Good Neighbor Next Door Program"}
        assert _infer_program_type(record) == "occupation"

    def test_first_responder(self):
        record = {"eligibility": "First responder or law enforcement officer"}
        assert _infer_program_type(record) == "occupation"

    def test_cdfi_keyword(self):
        record = {"administering_entity": "Local CDFI Housing Fund"}
        assert _infer_program_type(record) == "cdfi"

    def test_community_development_financial(self):
        record = {"name": "Community Development Financial Institution DPA"}
        assert _infer_program_type(record) == "cdfi"

    def test_employer_assisted_housing(self):
        record = {"name": "Employer Assisted Housing Benefit"}
        assert _infer_program_type(record) == "eah"

    def test_workforce_housing(self):
        record = {"benefits": "Workforce housing grant up to $10,000"}
        assert _infer_program_type(record) == "eah"

    def test_municipal_city_of(self):
        record = {"administering_entity": "City of Houston Housing Department"}
        assert _infer_program_type(record) == "municipal"

    def test_municipal_county(self):
        record = {"administering_entity": "County of Los Angeles Housing Authority"}
        assert _infer_program_type(record) == "municipal"

    def test_municipal_cdbg(self):
        record = {"benefits": "CDBG-funded down payment assistance grant"}
        assert _infer_program_type(record) == "municipal"

    def test_lmi_keyword(self):
        record = {"eligibility": "Must be LMI household (80% AMI or below)"}
        assert _infer_program_type(record) == "lmi"

    def test_low_income(self):
        record = {"eligibility": "Low income households only"}
        assert _infer_program_type(record) == "lmi"

    def test_fthb_first_time(self):
        record = {"name": "First-Time Homebuyer Program"}
        assert _infer_program_type(record) == "fthb"

    def test_fthb_keyword(self):
        record = {"eligibility": "Must be FTHB as defined by HUD"}
        assert _infer_program_type(record) == "fthb"

    def test_general_fallback(self):
        record = {"name": "CalHFA MyHome Assistance"}
        assert _infer_program_type(record) == "general"

    def test_empty_record(self):
        assert _infer_program_type({}) == "general"

    def test_provider_field_searched(self):
        record = {"provider": "City of Austin Housing Authority"}
        assert _infer_program_type(record) == "municipal"

    def test_agency_field_searched(self):
        record = {"agency": "Tribal Housing Administration"}
        assert _infer_program_type(record) == "tribal"


# ---------------------------------------------------------------------------
# _index_seeds_by_type — grouping
# ---------------------------------------------------------------------------

class TestIndexSeedsByType:
    def test_groups_by_program_type(self):
        seeds = [
            {"name": "A", "program_type": "veteran"},
            {"name": "B", "program_type": "fthb"},
            {"name": "C", "program_type": "veteran"},
            {"name": "D", "program_type": "general"},
        ]
        index = _index_seeds_by_type(seeds)
        assert len(index["veteran"]) == 2
        assert len(index["fthb"]) == 1
        assert len(index["general"]) == 1

    def test_missing_program_type_defaults_to_general(self):
        seeds = [
            {"name": "A"},
            {"name": "B", "program_type": "tribal"},
        ]
        index = _index_seeds_by_type(seeds)
        assert len(index["general"]) == 1
        assert len(index["tribal"]) == 1

    def test_empty_list(self):
        assert _index_seeds_by_type([]) == {}

    def test_all_same_type(self):
        seeds = [
            {"name": "A", "program_type": "cdfi"},
            {"name": "B", "program_type": "cdfi"},
        ]
        index = _index_seeds_by_type(seeds)
        assert list(index.keys()) == ["cdfi"]
        assert len(index["cdfi"]) == 2


# ---------------------------------------------------------------------------
# _normalize_program_seed — program_type integration
# ---------------------------------------------------------------------------

class TestNormalizeProgramSeedType:
    def test_program_type_added_to_output(self):
        record = {
            "program_name": "VA Homebuyer Grant",
            "administering_entity": "VA",
            "benefits": "Up to $5,000",
        }
        result = _normalize_program_seed(record)
        assert "program_type" in result
        assert result["program_type"] == "veteran"

    def test_general_fallback_in_output(self):
        record = {
            "name": "MyHome Assistance",
            "administering_entity": "CalHFA",
        }
        result = _normalize_program_seed(record)
        assert result["program_type"] == "general"

    def test_explicit_type_propagated(self):
        record = {
            "name": "Some Program",
            "program_type": "eah",
        }
        result = _normalize_program_seed(record)
        assert result["program_type"] == "eah"
