from __future__ import annotations

import csv
import io
import secrets
from datetime import datetime, timedelta, timezone
from statistics import mean

from flask import Blueprint, Response, jsonify, request, session
from sqlalchemy import desc, func
from werkzeug.security import check_password_hash

from app.audit import write_audit
from app.auth import admin_required
from app.config import settings
from app.extensions import db
from app.models import AdminUser, AuditLog, EvaluationRun, Feedback, IngestionJob, Product, SearchEvent
from app.services.cache import CacheService
from app.services.qdrant_store import QdrantStore
from app.services.rate_limit import RateLimiter

admin_bp = Blueprint("admin", __name__)


def _iso(value):
    return value.isoformat() if value else None


@admin_bp.post("/login")
def login():
    allowed, retry_after = RateLimiter().allow("admin-login", settings.admin_login_rate_limit_per_minute)
    if not allowed:
        response = jsonify({"error": {"code": "RATE_LIMITED", "message": "Too many login attempts"}})
        response.status_code = 429
        response.headers["Retry-After"] = str(retry_after)
        return response
    payload = request.get_json(silent=True) or {}
    username = str(payload.get("username", "")).strip()
    password = str(payload.get("password", ""))
    user = AdminUser.query.filter_by(username=username, enabled=True).first()
    if not user or not check_password_hash(user.password_hash, password):
        write_audit("ADMIN_LOGIN", status="failure", actor_type="admin", actor_id=username, metadata={"reason": "invalid_credentials"})
        return jsonify({"error": {"code": "INVALID_CREDENTIALS", "message": "Invalid username or password"}}), 401
    session.clear()
    session["admin_user"] = user.username
    session["csrf_token"] = secrets.token_urlsafe(32)
    user.last_login_at = datetime.now(timezone.utc)
    db.session.commit()
    write_audit("ADMIN_LOGIN", actor_type="admin", actor_id=user.username)
    return jsonify({"ok": True, "username": user.username, "csrf_token": session["csrf_token"]})


@admin_bp.post("/logout")
@admin_required
def logout():
    username = session.get("admin_user")
    write_audit("ADMIN_LOGOUT", actor_type="admin", actor_id=username)
    session.clear()
    return jsonify({"ok": True})


@admin_bp.get("/session")
def session_info():
    return jsonify({"authenticated": bool(session.get("admin_user")), "username": session.get("admin_user"), "csrf_token": session.get("csrf_token")})


@admin_bp.get("/dashboard")
@admin_required
def dashboard():
    now = datetime.now(timezone.utc)
    day = now - timedelta(days=1)
    week = now - timedelta(days=7)
    total_products = db.session.query(func.count(Product.parent_asin)).scalar() or 0
    searches_today = SearchEvent.query.filter(SearchEvent.created_at >= day).count()
    errors_today = AuditLog.query.filter(AuditLog.created_at >= day, AuditLog.status == "failure").count()
    recent = SearchEvent.query.filter(SearchEvent.created_at >= week).order_by(SearchEvent.created_at.asc()).all()
    latencies = [x.latency_ms for x in recent]
    avg_latency = mean(latencies) if latencies else 0.0
    p95 = sorted(latencies)[max(0, int(len(latencies) * 0.95) - 1)] if latencies else 0.0
    zero_rate = (sum(1 for x in recent if x.result_count == 0) / len(recent) * 100) if recent else 0.0

    per_day: dict[str, int] = {}
    for item in recent:
        key = item.created_at.date().isoformat()
        per_day[key] = per_day.get(key, 0) + 1
    top_queries = (
        db.session.query(SearchEvent.query_text, func.count(SearchEvent.id).label("count"))
        .group_by(SearchEvent.query_text)
        .order_by(desc("count"))
        .limit(8)
        .all()
    )
    latest_eval = EvaluationRun.query.filter_by(status="completed").order_by(EvaluationRun.completed_at.desc()).first()
    latest_ingest = IngestionJob.query.order_by(IngestionJob.started_at.desc()).first()
    feedback_total = Feedback.query.count()
    positive = Feedback.query.filter(Feedback.feedback_type.in_(["helpful", "search_helpful"])).count()
    return jsonify(
        {
            "stats": {
                "products": total_products,
                "searches_today": searches_today,
                "avg_latency_ms": round(avg_latency, 2),
                "p95_latency_ms": round(p95, 2),
                "zero_result_rate": round(zero_rate, 2),
                "errors_today": errors_today,
                "feedback_positive_rate": round((positive / feedback_total * 100), 2) if feedback_total else None,
                "evaluation_score": (latest_eval.metrics or {}).get("ndcg_at_k") or (latest_eval.metrics or {}).get("intent_coverage") if latest_eval else None,
            },
            "searches_by_day": [{"date": key, "count": value} for key, value in per_day.items()],
            "top_queries": [{"query": query, "count": count} for query, count in top_queries],
            "latest_ingestion": _job_json(latest_ingest) if latest_ingest else None,
        }
    )


def _job_json(job: IngestionJob) -> dict:
    return {
        "id": job.id,
        "filename": job.filename,
        "status": job.status,
        "file_size": job.file_size,
        "processed": job.processed,
        "success": job.success,
        "skipped": job.skipped,
        "failed": job.failed,
        "current_line": job.current_line,
        "progress_percent": job.progress_percent,
        "rate_per_second": job.rate_per_second,
        "eta_seconds": job.eta_seconds,
        "stats": job.stats or {},
        "error": job.error,
        "started_at": _iso(job.started_at),
        "updated_at": _iso(job.updated_at),
        "completed_at": _iso(job.completed_at),
    }


@admin_bp.get("/ingestion/jobs")
@admin_required
def ingestion_jobs():
    rows = IngestionJob.query.order_by(IngestionJob.started_at.desc()).limit(100).all()
    return jsonify({"jobs": [_job_json(x) for x in rows]})


@admin_bp.get("/ingestion/jobs/<job_id>")
@admin_required
def ingestion_job(job_id: str):
    row = db.session.get(IngestionJob, job_id)
    if not row:
        return jsonify({"error": {"code": "NOT_FOUND", "message": "Ingestion job not found"}}), 404
    return jsonify(_job_json(row))


@admin_bp.get("/search-usage")
@admin_required
def search_usage():
    limit = min(int(request.args.get("limit", 100)), 500)
    rows = SearchEvent.query.order_by(SearchEvent.created_at.desc()).limit(limit).all()
    return jsonify(
        {
            "events": [
                {
                    "request_id": x.request_id,
                    "query": x.query_text,
                    "intent": x.intent,
                    "filters": x.filters,
                    "result_count": x.result_count,
                    "latency_ms": x.latency_ms,
                    "cache_hit": x.cache_hit,
                    "llm_used": x.llm_used,
                    "created_at": _iso(x.created_at),
                }
                for x in rows
            ]
        }
    )


@admin_bp.get("/audit")
@admin_required
def audit():
    query = AuditLog.query
    if request.args.get("event_type"):
        query = query.filter(AuditLog.event_type == request.args["event_type"])
    if request.args.get("status"):
        query = query.filter(AuditLog.status == request.args["status"])
    rows = query.order_by(AuditLog.created_at.desc()).limit(min(int(request.args.get("limit", 200)), 1000)).all()
    return jsonify({"logs": [_audit_json(x) for x in rows]})


def _audit_json(x: AuditLog) -> dict:
    return {
        "id": x.id,
        "event_type": x.event_type,
        "actor_type": x.actor_type,
        "actor_id": x.actor_id,
        "request_id": x.request_id,
        "action": x.action,
        "status": x.status,
        "metadata": x.metadata_json,
        "created_at": _iso(x.created_at),
    }


@admin_bp.get("/audit/export")
@admin_required
def audit_export():
    fmt = (request.args.get("format") or "csv").lower()
    rows = AuditLog.query.order_by(AuditLog.created_at.desc()).limit(10000).all()
    if fmt == "json":
        return jsonify({"logs": [_audit_json(x) for x in rows]})
    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(["id", "event_type", "actor_type", "actor_id", "request_id", "status", "created_at"])
    for x in rows:
        writer.writerow([x.id, x.event_type, x.actor_type, x.actor_id, x.request_id, x.status, _iso(x.created_at)])
    return Response(output.getvalue(), mimetype="text/csv", headers={"Content-Disposition": "attachment; filename=semanticfit-audit.csv"})


@admin_bp.get("/feedback")
@admin_required
def feedback():
    rows = Feedback.query.order_by(Feedback.created_at.desc()).limit(min(int(request.args.get("limit", 250)), 1000)).all()
    counts = dict(db.session.query(Feedback.feedback_type, func.count(Feedback.id)).group_by(Feedback.feedback_type).all())
    return jsonify(
        {
            "summary": counts,
            "feedback": [
                {
                    "id": x.id,
                    "request_id": x.request_id,
                    "product_id": x.product_id,
                    "feedback_type": x.feedback_type,
                    "feedback_reason": x.feedback_reason,
                    "details": x.details,
                    "created_at": _iso(x.created_at),
                }
                for x in rows
            ],
        }
    )


@admin_bp.get("/evaluations")
@admin_required
def evaluations():
    rows = EvaluationRun.query.order_by(EvaluationRun.started_at.desc()).limit(100).all()
    return jsonify(
        {
            "runs": [
                {
                    "id": x.id,
                    "run_name": x.run_name,
                    "status": x.status,
                    "metrics": x.metrics,
                    "model_version": x.model_version,
                    "dataset_version": x.dataset_version,
                    "started_at": _iso(x.started_at),
                    "completed_at": _iso(x.completed_at),
                }
                for x in rows
            ]
        }
    )


@admin_bp.get("/evaluations/<run_id>")
@admin_required
def evaluation(run_id: str):
    x = db.session.get(EvaluationRun, run_id)
    if not x:
        return jsonify({"error": {"code": "NOT_FOUND", "message": "Evaluation run not found"}}), 404
    return jsonify({"id": x.id, "run_name": x.run_name, "status": x.status, "metrics": x.metrics, "config": x.config, "cases": x.cases, "report_dir": x.report_dir, "started_at": _iso(x.started_at), "completed_at": _iso(x.completed_at)})


@admin_bp.get("/system")
@admin_required
def system():
    qdrant = QdrantStore()
    cache = CacheService()
    try:
        q_count = qdrant.count()
    except Exception:
        q_count = None
    return jsonify(
        {
            "app_env": settings.app_env,
            "embedding_backend": settings.embedding_backend,
            "embedding_model": settings.embedding_model,
            "reranker_enabled": settings.reranker_enabled,
            "reranker_model": settings.reranker_model,
            "llm_enabled": settings.llm_enabled,
            "llm_provider": settings.llm_provider if settings.llm_enabled else None,
            "feedback_enabled": settings.feedback_enabled,
            "audit_enabled": settings.audit_enabled,
            "qdrant_collection": settings.qdrant_collection,
            "qdrant_vectors": q_count,
            "redis_healthy": cache.healthy(),
            "product_rows": Product.query.count(),
        }
    )
