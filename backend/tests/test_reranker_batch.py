"""Tests for the batch LLM reranker."""

from app.retrieval.reranker import _parse_batch_scores, _parse_score
from app.retrieval.search import SearchResult


def _make_result(chunk_id: str, score: float = 0.5) -> SearchResult:
    return SearchResult(
        chunk_id=chunk_id,
        document_id="doc-1",
        source_id="src-1",
        manifest_id="m-1",
        section_path="Section 1",
        text=f"Content for {chunk_id}",
        score=score,
    )


class TestParseBatchScores:
    def test_valid_json_array(self):
        results = [_make_result("c1"), _make_result("c2")]
        response = '[{"id": "c1", "score": 9}, {"id": "c2", "score": 3}]'
        scores = _parse_batch_scores(response, results)
        assert scores["c1"] == 9.0
        assert scores["c2"] == 3.0

    def test_markdown_wrapped_json(self):
        results = [_make_result("c1")]
        response = '```json\n[{"id": "c1", "score": 7}]\n```'
        scores = _parse_batch_scores(response, results)
        assert scores["c1"] == 7.0

    def test_score_capped_at_10(self):
        results = [_make_result("c1")]
        response = '[{"id": "c1", "score": 15}]'
        scores = _parse_batch_scores(response, results)
        assert scores["c1"] == 10.0

    def test_fallback_index_parsing(self):
        results = [_make_result("c1"), _make_result("c2")]
        response = "Scores:\n[0] 8\n[1] 5"
        scores = _parse_batch_scores(response, results)
        assert scores.get("c1") == 8.0
        assert scores.get("c2") == 5.0

    def test_empty_response(self):
        results = [_make_result("c1")]
        scores = _parse_batch_scores("", results)
        assert scores == {}

    def test_garbage_response(self):
        results = [_make_result("c1")]
        scores = _parse_batch_scores("This is not useful", results)
        assert scores == {}


class TestParseScore:
    def test_json_score(self):
        assert _parse_score('{"score": 8}') == 8.0

    def test_plain_number_fallback(self):
        assert _parse_score("7") == 7.0

    def test_capped_at_10(self):
        assert _parse_score("15") == 10.0

    def test_default_on_garbage(self):
        assert _parse_score("no numbers here") == 5.0
