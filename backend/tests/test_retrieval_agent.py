"""Tests for retrieval agent — depth config, query planning, source formatting."""

from app.retrieval.agent import DEPTH_CONFIG, RetrievalAgent
from app.retrieval.citations import CitationChain
from app.retrieval.search import SearchResult


class TestDepthConfig:
    def test_all_levels_present(self):
        assert set(DEPTH_CONFIG.keys()) == {1, 2, 3, 4}

    def test_each_level_has_required_keys(self):
        for level, config in DEPTH_CONFIG.items():
            assert "name" in config, f"Level {level} missing 'name'"
            assert "token_budget" in config, f"Level {level} missing 'token_budget'"
            assert "instructions" in config, f"Level {level} missing 'instructions'"

    def test_token_budgets_increase(self):
        budgets = [DEPTH_CONFIG[i]["token_budget"] for i in range(1, 5)]
        assert budgets == sorted(budgets), "Token budgets should increase with depth"

    def test_level_names(self):
        assert DEPTH_CONFIG[1]["name"] == "Quick Check"
        assert DEPTH_CONFIG[2]["name"] == "Summary"
        assert DEPTH_CONFIG[3]["name"] == "Analysis"
        assert DEPTH_CONFIG[4]["name"] == "Exhaustive"


class TestSourceFormatting:
    def test_format_sources_with_citations(self):
        """Test _format_sources produces valid source blocks."""
        # We can't easily construct a RetrievalAgent without a real db session,
        # so test the formatting logic directly.
        results = [
            SearchResult(
                chunk_id="c1",
                document_id="d1",
                source_id="src-001",
                manifest_id="m-001",
                section_path="§1026.37(a)",
                text="Loan estimate disclosure requirements",
                score=0.95,
            ),
            SearchResult(
                chunk_id="c2",
                document_id="d2",
                source_id="src-002",
                manifest_id="m-001",
                section_path="§1026.19(e)",
                text="Timing of disclosures",
                score=0.88,
            ),
        ]
        citations = {
            "c1": CitationChain(
                chunk_id="c1",
                chunk_text="Loan estimate...",
                section_path="§1026.37(a)",
                document_id="d1",
                document_title="Reg Z",
                source_id="src-001",
                source_url="https://example.com/regz",
                regulatory_body="CFPB",
                jurisdiction="federal",
                authority_level="binding",
                manifest_id="m-001",
                confidence=0.95,
            ),
        }

        # Use the static method pattern (create a dummy agent-like object)
        agent = type("Agent", (), {"_format_sources": RetrievalAgent._format_sources})()
        block = agent._format_sources(results, citations)

        assert "[src-001 §§1026.37(a)]" in block
        assert "Loan estimate disclosure requirements" in block
        assert "binding" in block
        assert "---" in block  # separator

    def test_format_sources_empty(self):
        agent = type("Agent", (), {"_format_sources": RetrievalAgent._format_sources})()
        block = agent._format_sources([], {})
        assert "No sources retrieved" in block


class TestRerankerParsing:
    def test_parse_json_score(self):
        from app.retrieval.reranker import _parse_score

        assert _parse_score('{"score": 8, "reason": "relevant"}') == 8.0

    def test_parse_markdown_wrapped_json(self):
        from app.retrieval.reranker import _parse_score

        response = '```json\n{"score": 7, "reason": "mostly relevant"}\n```'
        assert _parse_score(response) == 7.0

    def test_parse_plain_number_fallback(self):
        from app.retrieval.reranker import _parse_score

        assert _parse_score("The relevance score is 9 out of 10") == 9.0

    def test_parse_default_on_garbage(self):
        from app.retrieval.reranker import _parse_score

        assert _parse_score("no numbers here") == 5.0

    def test_parse_caps_score_at_10(self):
        from app.retrieval.reranker import _parse_score

        assert _parse_score("Score: 15") == 10.0


class TestAnalysisParsing:
    def test_parse_analysis_response_valid(self):
        from app.retrieval.analysis import _parse_analysis_response

        response = '''{
            "findings": [
                {
                    "category": "gap",
                    "severity": "high",
                    "description": "Missing disclosure",
                    "recommendation": "Add disclosure"
                }
            ],
            "summary": "One critical gap found",
            "coverage_score": 0.75
        }'''
        findings, summary, coverage = _parse_analysis_response(response)
        assert len(findings) == 1
        assert findings[0].category == "gap"
        assert findings[0].severity == "high"
        assert summary == "One critical gap found"
        assert coverage == 0.75

    def test_parse_analysis_response_markdown(self):
        from app.retrieval.analysis import _parse_analysis_response

        response = '```json\n{"findings": [], "summary": "No gaps", "coverage_score": 1.0}\n```'
        findings, summary, coverage = _parse_analysis_response(response)
        assert findings == []
        assert summary == "No gaps"
        assert coverage == 1.0

    def test_parse_analysis_response_invalid_json(self):
        from app.retrieval.analysis import _parse_analysis_response

        response = "This is not valid JSON at all."
        findings, summary, coverage = _parse_analysis_response(response)
        assert findings == []
        assert "This is not valid" in summary
        assert coverage is None

    def test_parse_analysis_no_coverage(self):
        from app.retrieval.analysis import _parse_analysis_response

        response = '{"findings": [], "summary": "Conflict analysis"}'
        findings, summary, coverage = _parse_analysis_response(response)
        assert coverage is None
        assert summary == "Conflict analysis"
