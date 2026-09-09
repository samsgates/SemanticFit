from __future__ import annotations

import uuid
from typing import Any

from qdrant_client import QdrantClient, models

from app.config import settings
from .embeddings import EncodedVector, EmbeddingService

_NAMESPACE = uuid.UUID("6dd6ec7b-16f4-4375-b74f-8c65097c0d85")


def point_id(parent_asin: str) -> str:
    return str(uuid.uuid5(_NAMESPACE, parent_asin))


class QdrantStore:
    def __init__(self):
        self.client = QdrantClient(url=settings.qdrant_url, timeout=30.0)
        self.collection = settings.qdrant_collection

    def ensure_collection(self) -> None:
        collections = {c.name for c in self.client.get_collections().collections}
        if self.collection in collections:
            return
        dim = EmbeddingService().dimension
        self.client.create_collection(
            collection_name=self.collection,
            vectors_config={
                "dense": models.VectorParams(size=dim, distance=models.Distance.COSINE),
            },
            sparse_vectors_config={
                "sparse": models.SparseVectorParams(
                    index=models.SparseIndexParams(on_disk=True)
                )
            },
            hnsw_config=models.HnswConfigDiff(m=16, ef_construct=128),
        )
        # Payload indexes improve filter latency. Errors are non-fatal for old Qdrant versions.
        for field, schema in [
            ("price", models.PayloadSchemaType.FLOAT),
            ("average_rating", models.PayloadSchemaType.FLOAT),
            ("main_category", models.PayloadSchemaType.KEYWORD),
            ("category_path", models.PayloadSchemaType.KEYWORD),
            ("store", models.PayloadSchemaType.KEYWORD),
        ]:
            try:
                self.client.create_payload_index(self.collection, field, field_schema=schema)
            except Exception:
                pass

    def upsert(self, rows: list[dict[str, Any]], vectors: list[EncodedVector]) -> None:
        points = []
        for row, vector in zip(rows, vectors):
            payload = {
                "parent_asin": row["parent_asin"],
                "title": row["title"],
                "main_category": row.get("main_category"),
                "price": row.get("price"),
                "average_rating": row.get("average_rating"),
                "rating_number": row.get("rating_number", 0),
                "store": row.get("store"),
                "category_path": row.get("categories", []),
                "primary_image": row.get("primary_image"),
                "search_document_version": row.get("search_document_version", 1),
            }
            payload = {k: v for k, v in payload.items() if v is not None}
            points.append(
                models.PointStruct(
                    id=point_id(row["parent_asin"]),
                    vector={
                        "dense": vector.dense,
                        "sparse": models.SparseVector(
                            indices=vector.sparse_indices,
                            values=vector.sparse_values,
                        ),
                    },
                    payload=payload,
                )
            )
        if points:
            self.client.upsert(self.collection, points=points, wait=True)

    def _filter(self, filters: dict[str, Any] | None) -> models.Filter | None:
        if not filters:
            return None
        must: list[models.Condition] = []
        min_price = filters.get("min_price")
        max_price = filters.get("max_price")
        if min_price is not None or max_price is not None:
            must.append(
                models.FieldCondition(
                    key="price",
                    range=models.Range(gte=min_price, lte=max_price),
                )
            )
        if filters.get("min_rating") is not None:
            must.append(
                models.FieldCondition(
                    key="average_rating",
                    range=models.Range(gte=float(filters["min_rating"])),
                )
            )
        if filters.get("category"):
            must.append(
                models.FieldCondition(
                    key="category_path",
                    match=models.MatchValue(value=str(filters["category"])),
                )
            )
        if filters.get("store"):
            must.append(
                models.FieldCondition(
                    key="store", match=models.MatchValue(value=str(filters["store"]))
                )
            )
        return models.Filter(must=must) if must else None

    def hybrid_search(
        self,
        vector: EncodedVector,
        *,
        limit: int,
        filters: dict[str, Any] | None = None,
    ) -> list[dict[str, Any]]:
        query_filter = self._filter(filters)
        prefetch = [
            models.Prefetch(query=vector.dense, using="dense", limit=max(limit, 20)),
        ]
        if vector.sparse_indices:
            prefetch.append(
                models.Prefetch(
                    query=models.SparseVector(
                        indices=vector.sparse_indices,
                        values=vector.sparse_values,
                    ),
                    using="sparse",
                    limit=max(limit, 20),
                )
            )
        if len(prefetch) == 1:
            result = self.client.query_points(
                collection_name=self.collection,
                query=vector.dense,
                using="dense",
                query_filter=query_filter,
                limit=limit,
                with_payload=True,
            )
        else:
            result = self.client.query_points(
                collection_name=self.collection,
                prefetch=prefetch,
                query=models.FusionQuery(fusion=models.Fusion.RRF),
                query_filter=query_filter,
                limit=limit,
                with_payload=True,
            )
        return [
            {
                "id": str(point.id),
                "score": float(point.score),
                "payload": point.payload or {},
            }
            for point in result.points
        ]

    def count(self) -> int:
        self.ensure_collection()
        return int(self.client.count(self.collection, exact=True).count)

    def healthy(self) -> bool:
        try:
            self.client.get_collections()
            return True
        except Exception:
            return False
