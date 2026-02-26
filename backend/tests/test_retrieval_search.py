"""Tests for retrieval search — RRF fusion, filter building, and result handling."""

from app.retrieval.search import SearchFilters, SearchResult, _build_filter_clause, _rrf_merge


def _make_result(chunk_id: str, score: float = 0.5) -> SearchResult:
    return SearchResult(
        chunk_id=chunk_id,
        document_id=f"doc-{chunk_id}",
        source_id=f"src-{chunk_id}",
        manifest_id="m-001",
        section_path=f"§{chunk_id}",
        text=f"Text for {chunk_id}",
        score=score,
    )


class TestRRFMerge:
    def test_fuses_dense_and_sparse(self):
        dense = [_make_result("a"), _make_result("b"), _make_result("c")]
        sparse = [_make_result("b"), _make_result("d"), _make_result("a")]

        fused = _rrf_merge(dense, sparse, k=60)

        # Items appearing in both should rank higher
        ids = [r.chunk_id for r in fused]
        assert "a" in ids
        assert "b" in ids
        assert "c" in ids
        assert "d" in ids
        # b and a appear in both, should be at the top
        assert ids.index("b") < ids.index("c")
        assert ids.index("a") < ids.index("d")

    def test_empty_sparse(self):
        dense = [_make_result("a"), _make_result("b")]
        fused = _rrf_merge(dense, [], k=60)
        assert len(fused) == 2
        assert fused[0].chunk_id == "a"

    def test_empty_dense(self):
        sparse = [_make_result("x"), _make_result("y")]
        fused = _rrf_merge([], sparse, k=60)
        assert len(fused) == 2
        assert fused[0].chunk_id == "x"

    def test_both_empty(self):
        fused = _rrf_merge([], [], k=60)
        assert fused == []

    def test_single_item_overlap(self):
        dense = [_make_result("a")]
        sparse = [_make_result("a")]
        fused = _rrf_merge(dense, sparse, k=60)
        assert len(fused) == 1
        assert fused[0].chunk_id == "a"
        # Score should be the sum of both RRF contributions
        expected_score = 1 / (60 + 1) + 1 / (60 + 1)
        assert abs(fused[0].score - expected_score) < 1e-10

    def test_preserves_metadata(self):
        dense = [_make_result("a")]
        dense[0].chunk_metadata = {"source_id": "src-a", "jurisdiction": "federal"}
        fused = _rrf_merge(dense, [], k=60)
        assert fused[0].chunk_metadata["jurisdiction"] == "federal"


class TestFilterClause:
    def test_no_filters(self):
        clause, params = _build_filter_clause(None)
        assert clause == ""
        assert params == {}

    def test_empty_filters(self):
        filters = SearchFilters()
        clause, params = _build_filter_clause(filters)
        assert clause == ""
        assert params == {}

    def test_jurisdiction_filter(self):
        filters = SearchFilters(jurisdiction=["federal", "state"])
        clause, params = _build_filter_clause(filters)
        assert "jurisdiction" in clause
        assert params["jurisdictions"] == ["federal", "state"]

    def test_multiple_filters(self):
        filters = SearchFilters(
            jurisdiction=["federal"],
            document_type=["statute"],
            regulatory_body=["naic"],
        )
        clause, params = _build_filter_clause(filters)
        assert "jurisdiction" in clause
        assert "document_type" in clause
        assert "regulatory_body" in clause
        assert len(params) == 3

    def test_authority_level_filter(self):
        filters = SearchFilters(authority_level=["binding"])
        clause, params = _build_filter_clause(filters)
        assert "authority_level" in clause
        assert params["auth_levels"] == ["binding"]
