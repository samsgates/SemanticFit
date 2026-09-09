from __future__ import annotations

import time
import uuid

import structlog
from flask import Flask, jsonify, request
from flask_cors import CORS
from prometheus_client import CONTENT_TYPE_LATEST, Counter, Histogram, generate_latest

from .config import settings
from .extensions import db

REQUEST_COUNT = Counter("semanticfit_http_requests_total", "HTTP requests", ["method", "path", "status"])
REQUEST_LATENCY = Histogram("semanticfit_http_request_duration_seconds", "HTTP request latency", ["path"])


def create_app(test_config: dict | None = None) -> Flask:
    app = Flask(__name__)
    app.config.update(
        SECRET_KEY=settings.secret_key,
        SQLALCHEMY_DATABASE_URI=settings.database_url,
        SQLALCHEMY_TRACK_MODIFICATIONS=False,
        SESSION_COOKIE_HTTPONLY=True,
        SESSION_COOKIE_SAMESITE="Lax",
        SESSION_COOKIE_SECURE=settings.session_cookie_secure,
        JSON_SORT_KEYS=False,
    )
    if test_config:
        app.config.update(test_config)

    db.init_app(app)
    origins = [x.strip() for x in settings.cors_origins.split(",") if x.strip()]
    CORS(app, supports_credentials=True, origins=origins)

    structlog.configure(
        processors=[
            structlog.processors.TimeStamper(fmt="iso"),
            structlog.processors.add_log_level,
            structlog.processors.JSONRenderer(),
        ]
    )

    from .api.admin import admin_bp
    from .api.public import public_bp

    app.register_blueprint(public_bp, url_prefix="/api/v1")
    app.register_blueprint(admin_bp, url_prefix="/api/v1/admin")

    @app.before_request
    def before_request():
        request.request_id = request.headers.get("X-Request-ID") or f"req_{uuid.uuid4().hex}"
        request._semanticfit_started = time.perf_counter()

    @app.after_request
    def after_request(response):
        elapsed = time.perf_counter() - getattr(request, "_semanticfit_started", time.perf_counter())
        response.headers["X-Request-ID"] = getattr(request, "request_id", "")
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
        REQUEST_COUNT.labels(request.method, request.path, str(response.status_code)).inc()
        REQUEST_LATENCY.labels(request.path).observe(elapsed)
        return response

    @app.get("/metrics")
    def metrics():
        return app.response_class(generate_latest(), mimetype=CONTENT_TYPE_LATEST)

    @app.errorhandler(404)
    def not_found(_):
        return jsonify({"error": {"code": "NOT_FOUND", "message": "Resource not found", "request_id": getattr(request, "request_id", None)}}), 404

    @app.errorhandler(500)
    def internal_error(_):
        db.session.rollback()
        return jsonify({"error": {"code": "INTERNAL_ERROR", "message": "Unexpected server error", "request_id": getattr(request, "request_id", None)}}), 500

    return app
