from __future__ import annotations

import hashlib
import math
import os
import threading
from dataclasses import dataclass
from typing import Iterable

import numpy as np

from app.config import settings


@dataclass
class EncodedVector:
    dense: list[float]
    sparse_indices: list[int]
    sparse_values: list[float]


class EmbeddingService:
    """Lazy embedding service.

    Default production backend is BGE-M3 through FlagEmbedding. A deterministic hash backend
    exists for tests and low-resource smoke runs. It is intentionally opt-in.
    """

    _instance: "EmbeddingService | None" = None
    _lock = threading.Lock()

    def __new__(cls):
        with cls._lock:
            if cls._instance is None:
                cls._instance = super().__new__(cls)
                cls._instance._model = None
            return cls._instance

    @property
    def dimension(self) -> int:
        return 128 if settings.embedding_backend == "hash" else settings.embedding_dim

    def _device(self) -> str:
        value = settings.embedding_device.lower()
        if value != "auto":
            return value
        try:
            import torch

            if torch.cuda.is_available():
                return "cuda"
            if getattr(torch.backends, "mps", None) and torch.backends.mps.is_available():
                return "mps"
        except Exception:
            pass
        return "cpu"

    def _load(self):
        if settings.embedding_backend == "hash":
            return None
        if self._model is not None:
            return self._model
        try:
            from FlagEmbedding import BGEM3FlagModel
        except ImportError as exc:
            raise RuntimeError(
                "FlagEmbedding is not installed. Install SemanticFit with the ml extra: pip install -e '.[ml]'"
            ) from exc

        device = self._device()
        use_fp16 = settings.embedding_use_fp16 and device == "cuda"
        kwargs = {"use_fp16": use_fp16}
        if device != "auto":
            kwargs["devices"] = [device]
        self._model = BGEM3FlagModel(settings.embedding_model, **kwargs)
        return self._model

    @staticmethod
    def _hash_vector(text: str, dim: int = 128) -> EncodedVector:
        tokens = [t for t in text.lower().split() if t]
        dense = np.zeros(dim, dtype=np.float32)
        counts: dict[int, float] = {}
        for token in tokens:
            digest = hashlib.sha256(token.encode("utf-8")).digest()
            idx = int.from_bytes(digest[:4], "big") % dim
            sign = 1.0 if digest[4] % 2 == 0 else -1.0
            dense[idx] += sign
            sparse_idx = int.from_bytes(digest[5:9], "big") % 1_000_003
            counts[sparse_idx] = counts.get(sparse_idx, 0.0) + 1.0
        norm = float(np.linalg.norm(dense))
        if norm:
            dense /= norm
        indices = sorted(counts)
        values = [math.log1p(counts[i]) for i in indices]
        return EncodedVector(dense.tolist(), indices, values)

    def encode_one(self, text: str) -> EncodedVector:
        return self.encode_many([text])[0]

    def encode_many(self, texts: Iterable[str]) -> list[EncodedVector]:
        materialized = list(texts)
        if not materialized:
            return []
        if settings.embedding_backend == "hash":
            return [self._hash_vector(text) for text in materialized]

        model = self._load()
        output = model.encode(
            materialized,
            batch_size=settings.embedding_batch_size,
            return_dense=True,
            return_sparse=True,
            return_colbert_vecs=False,
        )
        dense = output["dense_vecs"]
        sparse = output["lexical_weights"]
        results: list[EncodedVector] = []
        for dv, sv in zip(dense, sparse):
            if hasattr(dv, "tolist"):
                dv = dv.tolist()
            pairs = sorted((int(k), float(v)) for k, v in (sv or {}).items() if float(v) != 0.0)
            results.append(
                EncodedVector(
                    dense=[float(x) for x in dv],
                    sparse_indices=[k for k, _ in pairs],
                    sparse_values=[v for _, v in pairs],
                )
            )
        return results

    def ready(self) -> bool:
        try:
            if settings.embedding_backend == "hash":
                return True
            self._load()
            return True
        except Exception:
            return False
