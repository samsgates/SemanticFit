from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import Index
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.types import JSON

from .extensions import db


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


def json_type():
    return JSON().with_variant(JSONB, "postgresql")


class AdminUser(db.Model):
    __tablename__ = "admin_users"

    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(120), unique=True, nullable=False, index=True)
    password_hash = db.Column(db.String(512), nullable=False)
    enabled = db.Column(db.Boolean, nullable=False, default=True)
    created_at = db.Column(db.DateTime(timezone=True), nullable=False, default=utcnow)
    last_login_at = db.Column(db.DateTime(timezone=True), nullable=True)


class Product(db.Model):
    __tablename__ = "products"

    parent_asin = db.Column(db.String(64), primary_key=True)
    main_category = db.Column(db.Text, nullable=True, index=True)
    title = db.Column(db.Text, nullable=False)
    average_rating = db.Column(db.Float, nullable=True, index=True)
    rating_number = db.Column(db.Integer, nullable=False, default=0)
    price = db.Column(db.Numeric(12, 2), nullable=True, index=True)
    store = db.Column(db.Text, nullable=True, index=True)

    features = db.Column(json_type(), nullable=False, default=list)
    description = db.Column(json_type(), nullable=False, default=list)
    categories = db.Column(json_type(), nullable=False, default=list)
    details = db.Column(json_type(), nullable=False, default=dict)
    images = db.Column(json_type(), nullable=False, default=list)
    videos = db.Column(json_type(), nullable=False, default=list)
    bought_together = db.Column(json_type(), nullable=True)

    primary_image = db.Column(db.Text, nullable=True)
    thumbnail_image = db.Column(db.Text, nullable=True)
    category_path = db.Column(db.Text, nullable=True)
    search_document = db.Column(db.Text, nullable=False)
    search_document_hash = db.Column(db.String(64), nullable=False, index=True)
    search_document_version = db.Column(db.Integer, nullable=False, default=1)
    embedding_model = db.Column(db.String(255), nullable=True)
    embedding_version = db.Column(db.String(64), nullable=True)
    indexed = db.Column(db.Boolean, nullable=False, default=False, index=True)
    indexed_at = db.Column(db.DateTime(timezone=True), nullable=True)
    created_at = db.Column(db.DateTime(timezone=True), nullable=False, default=utcnow)
    updated_at = db.Column(db.DateTime(timezone=True), nullable=False, default=utcnow, onupdate=utcnow)


class IngestionJob(db.Model):
    __tablename__ = "ingestion_jobs"

    id = db.Column(db.String(36), primary_key=True)
    filename = db.Column(db.Text, nullable=False)
    file_hash = db.Column(db.String(128), nullable=False, index=True)
    file_size = db.Column(db.BigInteger, nullable=False, default=0)
    status = db.Column(db.String(32), nullable=False, index=True)
    processed = db.Column(db.BigInteger, nullable=False, default=0)
    success = db.Column(db.BigInteger, nullable=False, default=0)
    skipped = db.Column(db.BigInteger, nullable=False, default=0)
    failed = db.Column(db.BigInteger, nullable=False, default=0)
    current_offset = db.Column(db.BigInteger, nullable=False, default=0)
    current_line = db.Column(db.BigInteger, nullable=False, default=0)
    progress_percent = db.Column(db.Float, nullable=False, default=0.0)
    rate_per_second = db.Column(db.Float, nullable=False, default=0.0)
    eta_seconds = db.Column(db.Integer, nullable=True)
    stats = db.Column(json_type(), nullable=False, default=dict)
    error = db.Column(db.Text, nullable=True)
    started_at = db.Column(db.DateTime(timezone=True), nullable=False, default=utcnow)
    updated_at = db.Column(db.DateTime(timezone=True), nullable=False, default=utcnow, onupdate=utcnow)
    completed_at = db.Column(db.DateTime(timezone=True), nullable=True)


class SearchEvent(db.Model):
    __tablename__ = "search_events"

    id = db.Column(db.BigInteger, primary_key=True, autoincrement=True)
    request_id = db.Column(db.String(64), nullable=False, unique=True, index=True)
    session_id = db.Column(db.String(128), nullable=True, index=True)
    query_text = db.Column("query", db.Text, nullable=False)
    normalized_query = db.Column(db.Text, nullable=False)
    intent = db.Column(json_type(), nullable=False, default=dict)
    filters = db.Column(json_type(), nullable=False, default=dict)
    results = db.Column(json_type(), nullable=False, default=list)
    result_count = db.Column(db.Integer, nullable=False, default=0)
    latency_ms = db.Column(db.Float, nullable=False, default=0.0, index=True)
    cache_hit = db.Column(db.Boolean, nullable=False, default=False)
    llm_used = db.Column(db.Boolean, nullable=False, default=False)
    created_at = db.Column(db.DateTime(timezone=True), nullable=False, default=utcnow, index=True)


class Feedback(db.Model):
    __tablename__ = "feedback"

    id = db.Column(db.BigInteger, primary_key=True, autoincrement=True)
    request_id = db.Column(db.String(64), nullable=False, index=True)
    product_id = db.Column(db.String(64), nullable=True, index=True)
    session_id = db.Column(db.String(128), nullable=True, index=True)
    feedback_type = db.Column(db.String(64), nullable=False, index=True)
    feedback_reason = db.Column(db.String(255), nullable=True)
    details = db.Column(json_type(), nullable=False, default=dict)
    created_at = db.Column(db.DateTime(timezone=True), nullable=False, default=utcnow, index=True)


class AuditLog(db.Model):
    __tablename__ = "audit_logs"

    id = db.Column(db.BigInteger, primary_key=True, autoincrement=True)
    event_type = db.Column(db.String(64), nullable=False, index=True)
    actor_type = db.Column(db.String(32), nullable=False, default="system", index=True)
    actor_id = db.Column(db.String(128), nullable=True)
    request_id = db.Column(db.String(64), nullable=True, index=True)
    action = db.Column(db.Text, nullable=True)
    status = db.Column(db.String(32), nullable=False, default="success", index=True)
    metadata_json = db.Column("metadata", json_type(), nullable=False, default=dict)
    ip_hash = db.Column(db.String(64), nullable=True)
    created_at = db.Column(db.DateTime(timezone=True), nullable=False, default=utcnow, index=True)


class EvaluationRun(db.Model):
    __tablename__ = "evaluation_runs"

    id = db.Column(db.String(36), primary_key=True)
    run_name = db.Column(db.String(255), nullable=False)
    model_version = db.Column(db.String(255), nullable=True)
    index_version = db.Column(db.String(255), nullable=True)
    dataset_version = db.Column(db.String(255), nullable=True)
    config = db.Column(json_type(), nullable=False, default=dict)
    metrics = db.Column(json_type(), nullable=False, default=dict)
    cases = db.Column(json_type(), nullable=False, default=list)
    report_dir = db.Column(db.Text, nullable=True)
    status = db.Column(db.String(32), nullable=False, default="running", index=True)
    started_at = db.Column(db.DateTime(timezone=True), nullable=False, default=utcnow)
    completed_at = db.Column(db.DateTime(timezone=True), nullable=True)


Index("ix_search_events_created_latency", SearchEvent.created_at, SearchEvent.latency_ms)
Index("ix_audit_created_event", AuditLog.created_at, AuditLog.event_type)
