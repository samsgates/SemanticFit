from __future__ import annotations

import hmac
from functools import wraps

from flask import jsonify, request, session


def admin_required(fn):
    @wraps(fn)
    def wrapped(*args, **kwargs):
        if not session.get("admin_user"):
            return jsonify({"error": {"code": "ADMIN_AUTH_REQUIRED", "message": "Admin login required"}}), 401
        if request.method not in {"GET", "HEAD", "OPTIONS"}:
            expected = str(session.get("csrf_token") or "")
            supplied = str(request.headers.get("X-CSRF-Token") or "")
            if not expected or not supplied or not hmac.compare_digest(expected, supplied):
                return jsonify({"error": {"code": "CSRF_FAILED", "message": "Invalid CSRF token"}}), 403
        return fn(*args, **kwargs)

    return wrapped
