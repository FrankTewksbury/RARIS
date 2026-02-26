"""Evaluation metrics for RARIS pipeline phases.

Phase 1: Manifest Accuracy (≥95%), Source Recall (≥90%)
Phase 2: Scrape Completion (≥90%)
Phase 3: Ingestion Success (≥95%)
Phase 4: Retrieval Precision@k (≥80%), NDCG@k
"""

import math
from dataclasses import dataclass


@dataclass
class MetricResult:
    name: str
    value: float
    target: float
    passed: bool

    @property
    def formatted(self) -> str:
        status = "PASS" if self.passed else "FAIL"
        return f"[{status}] {self.name}: {self.value:.2%} (target: {self.target:.2%})"


def manifest_accuracy(predicted_sources: list[dict], ground_truth: list[dict]) -> MetricResult:
    """Measure how many predicted sources match ground truth entries.

    A source is considered a match if the regulatory_body and type match.
    """
    target = 0.95
    if not ground_truth:
        return MetricResult("Manifest Accuracy", 0.0, target, False)

    gt_keys = {(s["regulatory_body"], s["type"]) for s in ground_truth}
    pred_keys = {(s.get("regulatory_body"), s.get("type")) for s in predicted_sources}
    correct = len(gt_keys & pred_keys)
    accuracy = correct / len(gt_keys) if gt_keys else 0.0
    return MetricResult("Manifest Accuracy", accuracy, target, accuracy >= target)


def source_recall(predicted_sources: list[dict], ground_truth: list[dict]) -> MetricResult:
    """Measure what fraction of ground truth sources were found."""
    target = 0.90
    if not ground_truth:
        return MetricResult("Source Recall", 0.0, target, False)

    gt_keys = {(s["regulatory_body"], s["name"].lower()) for s in ground_truth}
    pred_keys = {(s.get("regulatory_body"), s.get("name", "").lower()) for s in predicted_sources}
    found = len(gt_keys & pred_keys)
    recall = found / len(gt_keys) if gt_keys else 0.0
    return MetricResult("Source Recall", recall, target, recall >= target)


def scrape_completion(completed: int, total: int) -> MetricResult:
    """Phase 2: fraction of sources successfully scraped."""
    target = 0.90
    rate = completed / total if total > 0 else 0.0
    return MetricResult("Scrape Completion", rate, target, rate >= target)


def ingestion_success(ingested: int, total: int) -> MetricResult:
    """Phase 3: fraction of scraped documents successfully ingested."""
    target = 0.95
    rate = ingested / total if total > 0 else 0.0
    return MetricResult("Ingestion Success", rate, target, rate >= target)


def precision_at_k(
    ranked_ids: list[str], relevant_ids: set[str], k: int = 10
) -> MetricResult:
    """Phase 4: fraction of top-k results that are relevant.

    Args:
        ranked_ids: Ordered list of chunk/document IDs from retrieval.
        relevant_ids: Set of IDs known to be relevant (ground truth).
        k: Cutoff rank.
    """
    target = 0.80
    if not ranked_ids or not relevant_ids:
        return MetricResult(f"Precision@{k}", 0.0, target, False)

    top_k = ranked_ids[:k]
    relevant_in_top_k = sum(1 for rid in top_k if rid in relevant_ids)
    precision = relevant_in_top_k / len(top_k)
    return MetricResult(f"Precision@{k}", precision, target, precision >= target)


def ndcg_at_k(
    ranked_ids: list[str], relevant_ids: set[str], k: int = 10
) -> MetricResult:
    """Phase 4: Normalized Discounted Cumulative Gain at k.

    Binary relevance: 1 if in relevant_ids, 0 otherwise.
    """
    target = 0.70

    if not ranked_ids or not relevant_ids:
        return MetricResult(f"NDCG@{k}", 0.0, target, False)

    # DCG
    dcg = 0.0
    for i, rid in enumerate(ranked_ids[:k]):
        rel = 1.0 if rid in relevant_ids else 0.0
        dcg += rel / math.log2(i + 2)  # i+2 because rank starts at 1

    # Ideal DCG — all relevant items at top
    ideal_count = min(len(relevant_ids), k)
    idcg = sum(1.0 / math.log2(i + 2) for i in range(ideal_count))

    ndcg = dcg / idcg if idcg > 0 else 0.0
    return MetricResult(f"NDCG@{k}", ndcg, target, ndcg >= target)
