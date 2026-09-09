from __future__ import annotations

import threading

from app.config import settings


class RerankerService:
    _instance: "RerankerService | None" = None
    _lock = threading.Lock()

    def __new__(cls):
        with cls._lock:
            if cls._instance is None:
                cls._instance = super().__new__(cls)
                cls._instance._model = None
            return cls._instance

    def _load(self):
        if not settings.reranker_enabled or settings.embedding_backend == "hash":
            return None
        if self._model is not None:
            return self._model
        try:
            from FlagEmbedding import FlagReranker
        except ImportError as exc:
            raise RuntimeError("FlagEmbedding is required for reranking") from exc
        self._model = FlagReranker(
            settings.reranker_model,
            use_fp16=settings.embedding_use_fp16,
        )
        return self._model

    def score(self, query: str, documents: list[str]) -> list[float]:
        if not documents:
            return []
        model = self._load()
        if model is None:
            return [0.5 for _ in documents]
        pairs = [[query, doc] for doc in documents]
        values = model.compute_score(pairs, normalize=True)
        if not isinstance(values, list):
            values = [values]
        return [float(x) for x in values]

    def ready(self) -> bool:
        if not settings.reranker_enabled or settings.embedding_backend == "hash":
            return True
        try:
            self._load()
            return True
        except Exception:
            return False
