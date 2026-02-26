"""Tests for retrieval evaluation metrics: precision@k and NDCG@k."""

from app.eval.metrics import ndcg_at_k, precision_at_k


class TestPrecisionAtK:
    def test_perfect_precision(self):
        ranked = ["a", "b", "c", "d", "e"]
        relevant = {"a", "b", "c", "d", "e"}
        result = precision_at_k(ranked, relevant, k=5)
        assert result.value == 1.0
        assert result.passed is True

    def test_zero_precision(self):
        ranked = ["x", "y", "z"]
        relevant = {"a", "b", "c"}
        result = precision_at_k(ranked, relevant, k=3)
        assert result.value == 0.0
        assert result.passed is False

    def test_half_precision(self):
        ranked = ["a", "x", "b", "y"]
        relevant = {"a", "b"}
        result = precision_at_k(ranked, relevant, k=4)
        assert result.value == 0.5

    def test_precision_at_k_truncates(self):
        ranked = ["a", "b", "c", "d", "e", "f", "g", "h", "i", "j"]
        relevant = {"a", "b", "c"}
        result = precision_at_k(ranked, relevant, k=5)
        assert result.value == 0.6  # 3 of 5

    def test_empty_ranked(self):
        result = precision_at_k([], {"a", "b"}, k=5)
        assert result.value == 0.0
        assert result.passed is False

    def test_empty_relevant(self):
        result = precision_at_k(["a", "b"], set(), k=5)
        assert result.value == 0.0

    def test_k_larger_than_results(self):
        ranked = ["a", "b"]
        relevant = {"a", "b"}
        result = precision_at_k(ranked, relevant, k=10)
        assert result.value == 1.0  # 2/2


class TestNDCGAtK:
    def test_perfect_ndcg(self):
        ranked = ["a", "b", "c"]
        relevant = {"a", "b", "c"}
        result = ndcg_at_k(ranked, relevant, k=3)
        assert result.value == 1.0
        assert result.passed is True

    def test_zero_ndcg(self):
        ranked = ["x", "y", "z"]
        relevant = {"a", "b", "c"}
        result = ndcg_at_k(ranked, relevant, k=3)
        assert result.value == 0.0
        assert result.passed is False

    def test_partial_ndcg(self):
        ranked = ["x", "a", "y", "b"]
        relevant = {"a", "b"}
        result = ndcg_at_k(ranked, relevant, k=4)
        # a at position 2, b at position 4
        # DCG = 1/log2(3) + 1/log2(5)
        # IDCG = 1/log2(2) + 1/log2(3) — ideal has both at top
        assert 0.0 < result.value < 1.0

    def test_empty_ranked(self):
        result = ndcg_at_k([], {"a"}, k=5)
        assert result.value == 0.0

    def test_empty_relevant(self):
        result = ndcg_at_k(["a"], set(), k=5)
        assert result.value == 0.0

    def test_single_relevant_at_top(self):
        ranked = ["a", "x", "y"]
        relevant = {"a"}
        result = ndcg_at_k(ranked, relevant, k=3)
        assert result.value == 1.0  # Single relevant item at rank 1 = perfect
