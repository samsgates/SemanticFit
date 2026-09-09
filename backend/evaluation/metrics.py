from __future__ import annotations

import math
from statistics import mean
from typing import Any


def precision_at_k(relevance: list[int], k: int) -> float:
    values = relevance[:k]
    return sum(values) / k if k else 0.0


def recall_at_k(result_ids: list[str], relevant_ids: set[str], k: int) -> float | None:
    if not relevant_ids:
        return None
    return len(set(result_ids[:k]) & relevant_ids) / len(relevant_ids)


def reciprocal_rank(relevance: list[int]) -> float:
    for idx, value in enumerate(relevance, 1):
        if value:
            return 1.0 / idx
    return 0.0


def ndcg_at_k(relevance: list[int], k: int) -> float:
    values = relevance[:k]
    dcg = sum(rel / math.log2(i + 2) for i, rel in enumerate(values))
    ideal = sorted(values, reverse=True)
    idcg = sum(rel / math.log2(i + 2) for i, rel in enumerate(ideal))
    return dcg / idcg if idcg else 0.0


def percentile(values: list[float], p: float) -> float:
    if not values:
        return 0.0
    ordered = sorted(values)
    index = min(len(ordered) - 1, max(0, math.ceil(p * len(ordered)) - 1))
    return float(ordered[index])


def aggregate_case_metrics(cases: list[dict[str, Any]]) -> dict[str, Any]:
    latencies = [float(x["latency_ms"]) for x in cases]
    proxy_precision = [float(x["proxy_precision_at_k"]) for x in cases]
    coverage = [float(x["intent_coverage"]) for x in cases]
    constraints = [float(x["constraint_satisfaction"]) for x in cases]
    diversity = [float(x["diversity"]) for x in cases]
    hit_rate = [1.0 if x["proxy_hits"] > 0 else 0.0 for x in cases]

    metrics: dict[str, Any] = {
        "case_count": len(cases),
        "proxy_precision_at_k": round(mean(proxy_precision), 6) if proxy_precision else 0.0,
        "intent_coverage": round(mean(coverage), 6) if coverage else 0.0,
        "constraint_satisfaction": round(mean(constraints), 6) if constraints else 0.0,
        "diversity": round(mean(diversity), 6) if diversity else 0.0,
        "hit_rate": round(mean(hit_rate), 6) if hit_rate else 0.0,
        "mean_latency_ms": round(mean(latencies), 3) if latencies else 0.0,
        "p50_latency_ms": round(percentile(latencies, 0.50), 3),
        "p95_latency_ms": round(percentile(latencies, 0.95), 3),
        "p99_latency_ms": round(percentile(latencies, 0.99), 3),
    }

    labeled = [x for x in cases if x.get("has_manual_labels")]
    if labeled:
        metrics.update(
            {
                "precision_at_k": round(mean(float(x["precision_at_k"]) for x in labeled), 6),
                "recall_at_k": round(mean(float(x["recall_at_k"]) for x in labeled), 6),
                "mrr": round(mean(float(x["mrr"]) for x in labeled), 6),
                "ndcg_at_k": round(mean(float(x["ndcg_at_k"]) for x in labeled), 6),
                "manually_labeled_case_count": len(labeled),
            }
        )
    return metrics
