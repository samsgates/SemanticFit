from __future__ import annotations

import re
import time
from decimal import Decimal
from typing import Any

from flask import current_app

from app.audit import write_audit
from app.config import settings
from app.extensions import db
from app.models import Product, SearchEvent
from .cache import CacheService
from .embeddings import EmbeddingService
from .intent import Intent, parse_intent
from .qdrant_store import QdrantStore
from .ranking import diversify, rank_candidates
from .reranker import RerankerService


def _serialize_product(product: Product, row: dict[str, Any], query: str) -> dict[str, Any]:
    price = float(product.price) if isinstance(product.price, Decimal) else product.price
    explanation = explain(product, query, row)
    return {
        "product_id": product.parent_asin,
        "parent_asin": product.parent_asin,
        "title": product.title,
        "main_category": product.main_category,
        "price": price,
        "rating": product.average_rating,
        "rating_count": product.rating_number,
        "store": product.store,
        "categories": product.categories or [],
        "image": product.primary_image,
        "thumbnail": product.thumbnail_image,
        "score": round(float(row["final_score"]), 6),
        "match_percent": max(1, min(99, round(float(row["final_score"]) * 100))),
        "reason": explanation,
        "score_breakdown": row.get("score_breakdown", {}),
    }


def explain(product: Product, query: str, row: dict[str, Any]) -> str:
    query_tokens = {x for x in re.findall(r"[a-zA-Z]{3,}", query.lower()) if x not in {"need", "want", "something", "with", "this", "that", "for", "the"}}
    doc = product.search_document.lower()
    matches = [token for token in query_tokens if token in doc][:3]
    reasons: list[str] = []
    if matches:
        reasons.append("matches " + ", ".join(matches))
    if product.average_rating and product.average_rating >= 4.3:
        reasons.append(f"rated {product.average_rating:.1f}/5")
    features = [str(x).strip() for x in (product.features or []) if str(x).strip()]
    if features:
        short = re.sub(r"\s+", " ", features[0])
        if len(short) > 90:
            short = short[:87] + "..."
        reasons.append(short)
    if not reasons:
        reasons.append("strong semantic relevance to your request")
    return " · ".join(reasons[:3])


def _merge_filters(intent: Intent, explicit: dict[str, Any] | None) -> dict[str, Any]:
    filters = dict(explicit or {})
    if filters.get("min_price") is None and intent.min_price is not None:
        filters["min_price"] = intent.min_price
    if filters.get("max_price") is None and intent.max_price is not None:
        filters["max_price"] = intent.max_price
    if filters.get("min_rating") is None and intent.min_rating is not None:
        filters["min_rating"] = intent.min_rating
    return {k: v for k, v in filters.items() if v not in (None, "")}


class SearchService:
    def __init__(self):
        self.embeddings = EmbeddingService()
        self.qdrant = QdrantStore()
        self.reranker = RerankerService()
        self.cache = CacheService()

    def search(
        self,
        query: str,
        *,
        limit: int | None = None,
        filters: dict[str, Any] | None = None,
        request_id: str,
        session_id: str | None = None,
        debug: bool = False,
        persist_event: bool = True,
    ) -> dict[str, Any]:
        started = time.perf_counter()
        query = (query or "").strip()
        if not query:
            raise ValueError("Query cannot be empty")
        if len(query) > 1000:
            raise ValueError("Query is too long")
        limit = max(1, min(int(limit or settings.search_default_limit), settings.search_max_limit))

        intent = parse_intent(query)
        merged_filters = _merge_filters(intent, filters)
        cache_key = self.cache.key(intent.semantic_query, merged_filters, limit)
        cached = self.cache.get(cache_key)
        if cached:
            cached = dict(cached)
            cached["request_id"] = request_id
            cached.setdefault("meta", {})["cache_hit"] = True
            cached["meta"]["latency_ms"] = round((time.perf_counter() - started) * 1000, 2)
            if persist_event:
                self._record_event(cached, session_id, intent.llm_used)
            return cached

        stage: dict[str, float] = {}
        t = time.perf_counter()
        vector = self.embeddings.encode_one(intent.semantic_query)
        stage["embedding_ms"] = (time.perf_counter() - t) * 1000

        self.qdrant.ensure_collection()
        t = time.perf_counter()
        hits = self.qdrant.hybrid_search(
            vector,
            limit=settings.search_candidate_count,
            filters=merged_filters,
        )
        stage["retrieval_ms"] = (time.perf_counter() - t) * 1000

        ids = [hit["payload"].get("parent_asin") for hit in hits if hit["payload"].get("parent_asin")]
        products = Product.query.filter(Product.parent_asin.in_(ids)).all() if ids else []
        product_map = {p.parent_asin: p for p in products}
        rows = [
            {"product": product_map[pid], "semantic_score": hit["score"]}
            for hit in hits
            if (pid := hit["payload"].get("parent_asin")) in product_map
        ]

        # Enforce free-text exclusions after retrieval. Hard numeric filters already execute in Qdrant.
        if intent.exclude:
            filtered_rows = []
            for row in rows:
                doc = row["product"].search_document.lower()
                if not any(term.lower() in doc for term in intent.exclude):
                    filtered_rows.append(row)
            rows = filtered_rows

        t = time.perf_counter()
        rerank_rows = rows[: settings.reranker_top_n]
        scores = self.reranker.score(intent.semantic_query, [r["product"].search_document for r in rerank_rows])
        for row, score in zip(rerank_rows, scores):
            row["reranker_score"] = score
        for row in rows[len(rerank_rows) :]:
            row["reranker_score"] = 0.5
        stage["rerank_ms"] = (time.perf_counter() - t) * 1000

        ranked = rank_candidates(rows, intent=intent.to_dict())
        selected = diversify(ranked, limit)
        results = [_serialize_product(r["product"], r, query) for r in selected]
        latency = (time.perf_counter() - started) * 1000
        response = {
            "request_id": request_id,
            "query": query,
            "intent": intent.to_dict(),
            "filters": merged_filters,
            "results": results,
            "meta": {
                "retrieved": len(hits),
                "reranked": len(rerank_rows),
                "returned": len(results),
                "latency_ms": round(latency, 2),
                "cache_hit": False,
                "llm_used": intent.llm_used,
            },
        }
        if debug:
            response["debug"] = {k: round(v, 2) for k, v in stage.items()}
        self.cache.set(cache_key, {k: v for k, v in response.items() if k != "request_id"})
        if persist_event:
            self._record_event(response, session_id, intent.llm_used)
        return response

    @staticmethod
    def _record_event(response: dict[str, Any], session_id: str | None, llm_used: bool) -> None:
        try:
            event = SearchEvent(
                request_id=response["request_id"],
                session_id=session_id,
                query_text=response["query"],
                normalized_query=response["intent"].get("semantic_query") or response["query"],
                intent=response["intent"],
                filters=response.get("filters", {}),
                results=[r["product_id"] for r in response.get("results", [])],
                result_count=len(response.get("results", [])),
                latency_ms=float(response.get("meta", {}).get("latency_ms", 0)),
                cache_hit=bool(response.get("meta", {}).get("cache_hit")),
                llm_used=llm_used,
            )
            db.session.add(event)
            db.session.commit()
            write_audit(
                "SEARCH_REQUEST",
                request_id=response["request_id"],
                metadata={"result_count": event.result_count, "latency_ms": event.latency_ms},
            )
        except Exception:
            db.session.rollback()
