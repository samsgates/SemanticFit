from __future__ import annotations

from collections import Counter
from decimal import Decimal

from flask import Blueprint, jsonify, request
from sqlalchemy import text

from app.audit import write_audit
from app.config import settings
from app.extensions import db
from app.models import Feedback, Product
from app.services.cache import CacheService
from app.services.embeddings import EmbeddingService
from app.services.qdrant_store import QdrantStore
from app.services.rate_limit import RateLimiter
from app.services.reranker import RerankerService
from app.services.search import SearchService

public_bp = Blueprint("public", __name__)


def _product_json(product: Product) -> dict:
    return {
        "parent_asin": product.parent_asin,
        "title": product.title,
        "main_category": product.main_category,
        "price": float(product.price) if isinstance(product.price, Decimal) else product.price,
        "average_rating": product.average_rating,
        "rating_number": product.rating_number,
        "features": product.features or [],
        "description": product.description or [],
        "images": product.images or [],
        "videos": product.videos or [],
        "store": product.store,
        "categories": product.categories or [],
        "details": product.details or {},
        "bought_together": product.bought_together,
        "primary_image": product.primary_image,
        "thumbnail_image": product.thumbnail_image,
    }


@public_bp.get("/health")
def health():
    qdrant = QdrantStore()
    cache = CacheService()
    db_ok = True
    try:
        db.session.execute(text("SELECT 1"))
    except Exception:
        db_ok = False
        db.session.rollback()
    components = {
        "postgres": "healthy" if db_ok else "unhealthy",
        "qdrant": "healthy" if qdrant.healthy() else "unhealthy",
        "redis": "healthy" if cache.healthy() else "degraded",
    }
    overall = "healthy" if components["postgres"] == "healthy" and components["qdrant"] == "healthy" else "degraded"
    return jsonify({"status": overall, "components": components})


@public_bp.get("/ready")
def ready():
    embed_ok = EmbeddingService().ready()
    rerank_ok = RerankerService().ready()
    qdrant_ok = QdrantStore().healthy()
    ok = embed_ok and rerank_ok and qdrant_ok
    return jsonify(
        {
            "ready": ok,
            "embedding_model": "ready" if embed_ok else "unavailable",
            "reranker": "ready" if rerank_ok else "unavailable",
            "qdrant": "ready" if qdrant_ok else "unavailable",
        }
    ), 200 if ok else 503


@public_bp.post("/recommendations")
def recommendations():
    allowed, retry_after = RateLimiter().allow("search", settings.search_rate_limit_per_minute)
    if not allowed:
        response = jsonify({"error": {"code": "RATE_LIMITED", "message": "Too many search requests", "request_id": request.request_id}})
        response.status_code = 429
        response.headers["Retry-After"] = str(retry_after)
        return response
    payload = request.get_json(silent=True) or {}
    query = str(payload.get("query", "")).strip()
    limit = payload.get("limit")
    filters = payload.get("filters") or {}
    session_id = request.headers.get("X-Session-ID") or payload.get("session_id")
    debug = request.args.get("debug", "false").lower() in {"1", "true", "yes"}
    try:
        result = SearchService().search(
            query,
            limit=limit,
            filters=filters,
            request_id=request.request_id,
            session_id=session_id,
            debug=debug,
        )
        return jsonify(result)
    except ValueError as exc:
        return jsonify({"error": {"code": "INVALID_QUERY", "message": str(exc), "request_id": request.request_id}}), 400
    except Exception as exc:
        db.session.rollback()
        write_audit("SEARCH_FAILURE", status="failure", request_id=request.request_id, metadata={"error": str(exc)[:500]})
        current = {"error": {"code": "SEARCH_FAILED", "message": "Search could not be completed", "request_id": request.request_id}}
        return jsonify(current), 503


@public_bp.get("/products/<parent_asin>")
def product(parent_asin: str):
    item = db.session.get(Product, parent_asin)
    if not item:
        return jsonify({"error": {"code": "PRODUCT_NOT_FOUND", "message": "Product not found"}}), 404
    return jsonify(_product_json(item))


@public_bp.get("/categories")
def categories():
    rows = Product.query.with_entities(Product.categories).limit(5000).all()
    counts: Counter[str] = Counter()
    for (values,) in rows:
        for value in values or []:
            if value:
                counts[str(value)] += 1
    data = [{"name": name, "count": count} for name, count in counts.most_common(100)]
    return jsonify({"categories": data})


@public_bp.get("/search/suggestions")
def suggestions():
    q = (request.args.get("q") or "").strip().lower()
    defaults = [
        "Something elegant for a summer wedding",
        "Comfortable clothes for a long flight",
        "Lightweight clothes for hot weather",
        "Smart casual outfit for a business dinner",
        "Relaxed beach vacation outfit",
        "Warm layers for a winter trip",
    ]
    if not q:
        return jsonify({"suggestions": defaults})
    titles = (
        Product.query.filter(Product.title.ilike(f"%{q}%"))
        .with_entities(Product.title)
        .limit(6)
        .all()
    )
    return jsonify({"suggestions": [x[0] for x in titles] or defaults[:4]})


@public_bp.post("/feedback")
def feedback():
    if not settings.feedback_enabled:
        return jsonify({"error": {"code": "FEEDBACK_DISABLED", "message": "Feedback is disabled"}}), 404
    payload = request.get_json(silent=True) or {}
    request_id = str(payload.get("request_id", "")).strip()
    feedback_type = str(payload.get("feedback_type", "")).strip()
    allowed = {"helpful", "not_relevant", "search_helpful", "search_partial", "search_not_helpful", "click", "detail_view"}
    if not request_id or feedback_type not in allowed:
        return jsonify({"error": {"code": "INVALID_FEEDBACK", "message": "Invalid feedback payload"}}), 400
    row = Feedback(
        request_id=request_id,
        product_id=payload.get("product_id"),
        session_id=payload.get("session_id") or request.headers.get("X-Session-ID"),
        feedback_type=feedback_type,
        feedback_reason=payload.get("feedback_reason"),
        details=payload.get("details") or {},
    )
    db.session.add(row)
    db.session.commit()
    write_audit("FEEDBACK_SUBMITTED", request_id=request_id, metadata={"feedback_id": row.id, "feedback_type": feedback_type, "product_id": row.product_id})
    return jsonify({"ok": True, "feedback_id": row.id}), 201
