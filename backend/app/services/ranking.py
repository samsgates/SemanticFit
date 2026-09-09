from __future__ import annotations

import math
from collections import defaultdict
from typing import Any

from app.models import Product


def _minmax(values: list[float]) -> list[float]:
    if not values:
        return []
    low, high = min(values), max(values)
    if high - low < 1e-9:
        return [1.0 for _ in values]
    return [(v - low) / (high - low) for v in values]


def bayesian_quality(rating: float | None, count: int | None, prior: float = 4.0, strength: float = 50.0) -> float:
    rating = float(rating or 0.0)
    count = max(0, int(count or 0))
    if rating <= 0:
        return 0.0
    weighted = (count / (count + strength)) * rating + (strength / (count + strength)) * prior
    return max(0.0, min(1.0, weighted / 5.0))


def popularity(count: int | None) -> float:
    return math.log1p(max(0, int(count or 0)))


def category_alignment(product: Product, intent: dict[str, Any]) -> float:
    haystack = " ".join(product.categories or []).lower()
    words = []
    for key in ("occasion", "season", "style", "materials", "colors"):
        words.extend(intent.get(key) or [])
    if not words:
        return 0.5
    hits = sum(1 for word in words if word.lower() in haystack or word.lower() in product.search_document.lower())
    return min(1.0, hits / max(1, min(3, len(words))))


def rank_candidates(
    rows: list[dict[str, Any]],
    *,
    intent: dict[str, Any],
) -> list[dict[str, Any]]:
    if not rows:
        return []
    semantic_norm = _minmax([float(row["semantic_score"]) for row in rows])
    popularity_norm = _minmax([popularity(row["product"].rating_number) for row in rows])
    for idx, row in enumerate(rows):
        product: Product = row["product"]
        rerank = float(row.get("reranker_score", 0.5))
        semantic = semantic_norm[idx]
        quality = bayesian_quality(product.average_rating, product.rating_number)
        pop = popularity_norm[idx]
        cat = category_alignment(product, intent)
        final = 0.55 * rerank + 0.20 * semantic + 0.10 * quality + 0.05 * pop + 0.10 * cat
        row["score_breakdown"] = {
            "reranker": round(rerank, 6),
            "semantic": round(semantic, 6),
            "quality": round(quality, 6),
            "popularity": round(pop, 6),
            "intent_alignment": round(cat, 6),
        }
        row["final_score"] = float(final)
    return sorted(rows, key=lambda x: x["final_score"], reverse=True)


def diversify(rows: list[dict[str, Any]], limit: int) -> list[dict[str, Any]]:
    """Category-aware diversification.

    The Amazon metadata file is already parent-ASIN-centric, so this primarily reduces repeated
    leaf categories instead of pretending to deduplicate child variants that are not in the file.
    """
    selected: list[dict[str, Any]] = []
    category_counts: defaultdict[str, int] = defaultdict(int)
    pool = rows.copy()
    while pool and len(selected) < limit:
        best_index = 0
        best_adjusted = -1.0
        for idx, row in enumerate(pool):
            product: Product = row["product"]
            categories = product.categories or []
            leaf = str(categories[-1]).lower() if categories else (product.main_category or "unknown").lower()
            penalty = min(0.18, 0.045 * category_counts[leaf])
            adjusted = float(row["final_score"]) - penalty
            if adjusted > best_adjusted:
                best_index, best_adjusted = idx, adjusted
        chosen = pool.pop(best_index)
        product = chosen["product"]
        categories = product.categories or []
        leaf = str(categories[-1]).lower() if categories else (product.main_category or "unknown").lower()
        category_counts[leaf] += 1
        chosen["diversified_score"] = best_adjusted
        selected.append(chosen)
    return selected
