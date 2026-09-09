from __future__ import annotations

import hashlib

from flask import request

from app.config import settings
from .cache import CacheService


class RateLimiter:
    def __init__(self):
        self.redis = CacheService().client

    def identity(self, scope: str) -> str:
        forwarded = request.headers.get("X-Forwarded-For", request.remote_addr or "").split(",")[0].strip()
        session_id = request.headers.get("X-Session-ID", "")
        raw = f"{scope}:{forwarded}:{session_id}:{settings.secret_key}"
        return hashlib.sha256(raw.encode("utf-8")).hexdigest()

    def allow(self, scope: str, limit: int, window_seconds: int = 60) -> tuple[bool, int]:
        if self.redis is None or limit <= 0:
            return True, 0
        key = f"semanticfit:ratelimit:{scope}:{self.identity(scope)}"
        try:
            pipe = self.redis.pipeline()
            pipe.incr(key)
            pipe.ttl(key)
            count, ttl = pipe.execute()
            if int(count) == 1 or int(ttl) < 0:
                self.redis.expire(key, window_seconds)
                ttl = window_seconds
            return int(count) <= limit, max(0, int(ttl))
        except Exception:
            return True, 0
