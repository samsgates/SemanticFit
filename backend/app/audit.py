from __future__ import annotations

import hashlib
from typing import Any

from flask import has_request_context, request, session

from .config import settings
from .extensions import db
from .models import AuditLog


def _ip_hash() -> str | None:
    if not has_request_context():
        return None
    value = request.headers.get("X-Forwarded-For", request.remote_addr or "").split(",")[0].strip()
    if not value:
        return None
    salt = settings.secret_key.encode("utf-8")
    return hashlib.sha256(salt + value.encode("utf-8")).hexdigest()


def write_audit(
    event_type: str,
    *,
    status: str = "success",
    action: str | None = None,
    request_id: str | None = None,
    metadata: dict[str, Any] | None = None,
    actor_type: str | None = None,
    actor_id: str | None = None,
    commit: bool = True,
) -> None:
    if not settings.audit_enabled:
        return
    if has_request_context():
        request_id = request_id or getattr(request, "request_id", None)
        if actor_type is None:
            actor_type = "admin" if session.get("admin_user") else "anonymous"
        actor_id = actor_id or session.get("admin_user")
    row = AuditLog(
        event_type=event_type,
        actor_type=actor_type or "system",
        actor_id=actor_id,
        request_id=request_id,
        action=action,
        status=status,
        metadata_json=metadata or {},
        ip_hash=_ip_hash(),
    )
    db.session.add(row)
    if commit:
        db.session.commit()
