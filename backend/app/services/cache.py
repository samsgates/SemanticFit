from __future__ import annotations

import hashlib
import json
from typing import Any

from app.config import settings


class CacheService:
    def __init__(self):
        self.client = None
        if settings.redis_enabled:
            try:
                import redis

                self.client = redis.Redis.from_url(settings.redis_url, decode_responses=True, socket_timeout=1)
            except Exception:
                self.client = None

    @staticmethod
    def key(query: str, filters: dict[str, Any], limit: int) -> str:
        raw = json.dumps({"q": query, "f": filters, "l": limit}, sort_keys=True)
        return "semanticfit:search:" + hashlib.sha256(raw.encode("utf-8")).hexdigest()

    def get(self, key: str) -> dict[str, Any] | None:
        if self.client is None:
            return None
        try:
            value = self.client.get(key)
            return json.loads(value) if value else None
        except Exception:
            return None

    def set(self, key: str, value: dict[str, Any], ttl: int = 600) -> None:
        if self.client is None:
            return
        try:
            self.client.setex(key, ttl, json.dumps(value))
        except Exception:
            pass

    def healthy(self) -> bool:
        if not settings.redis_enabled:
            return True
        if self.client is None:
            return False
        try:
            return bool(self.client.ping())
        except Exception:
            return False
