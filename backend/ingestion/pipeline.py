from __future__ import annotations

import gzip
import hashlib
import json
import os
import time
import uuid
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, BinaryIO, Callable

from sqlalchemy.dialects.postgresql import insert as pg_insert

from app.audit import write_audit
from app.config import settings
from app.extensions import db
from app.models import IngestionJob, Product
from app.services.embeddings import EmbeddingService
from app.services.qdrant_store import QdrantStore
from ingestion.normalize import normalize_product

ProgressCallback = Callable[[dict[str, Any]], None]


def utcnow():
    return datetime.now(timezone.utc)


def file_fingerprint(path: Path) -> str:
    size = path.stat().st_size
    h = hashlib.sha256()
    h.update(str(size).encode())
    with path.open("rb") as fh:
        h.update(fh.read(1024 * 1024))
        if size > 2 * 1024 * 1024:
            fh.seek(max(0, size - 1024 * 1024))
            h.update(fh.read(1024 * 1024))
    return h.hexdigest()


def open_stream(path: Path) -> BinaryIO:
    if path.suffix.lower() == ".gz":
        return gzip.open(path, "rb")  # type: ignore[return-value]
    return path.open("rb")


def estimate_line_count(path: Path, sample_bytes: int = 8 * 1024 * 1024) -> int | None:
    if path.suffix.lower() == ".gz":
        return None
    size = path.stat().st_size
    with path.open("rb") as fh:
        sample = fh.read(sample_bytes)
    if not sample:
        return 0
    newlines = sample.count(b"\n")
    if not newlines:
        return None
    avg = len(sample) / newlines
    return int(size / avg)


def inspect_file(path: Path, sample_records: int = 5000) -> dict[str, Any]:
    counters = Counter()
    categories = Counter()
    stores = Counter()
    prices: list[float] = []
    ratings: list[float] = []
    errors = 0
    records = 0
    with open_stream(path) as fh:
        for line in fh:
            if records >= sample_records:
                break
            try:
                raw = json.loads(line)
                row, warnings = normalize_product(raw)
                records += 1
                if row is None:
                    errors += 1
                    counters.update(warnings)
                    continue
                counters.update(warnings)
                categories.update(row["categories"])
                if row.get("store"):
                    stores[row["store"]] += 1
                if row.get("price") is not None:
                    prices.append(float(row["price"]))
                if row.get("average_rating") is not None:
                    ratings.append(float(row["average_rating"]))
            except Exception:
                errors += 1
    return {
        "file": str(path),
        "file_size": path.stat().st_size,
        "fingerprint": file_fingerprint(path),
        "estimated_lines": estimate_line_count(path),
        "sampled_records": records,
        "invalid_sample_records": errors,
        "warnings": dict(counters),
        "top_categories": categories.most_common(25),
        "top_stores": stores.most_common(15),
        "price": {
            "min": min(prices) if prices else None,
            "max": max(prices) if prices else None,
            "mean": round(sum(prices) / len(prices), 2) if prices else None,
        },
        "rating": {
            "min": min(ratings) if ratings else None,
            "max": max(ratings) if ratings else None,
            "mean": round(sum(ratings) / len(ratings), 3) if ratings else None,
        },
    }


class IngestionPipeline:
    def __init__(self, app, progress: ProgressCallback | None = None):
        self.app = app
        self.progress = progress or (lambda _: None)
        self.embedder = EmbeddingService()
        self.qdrant = QdrantStore()

    def _upsert_products(self, rows: list[dict[str, Any]]) -> None:
        if not rows:
            return
        dialect = db.engine.dialect.name
        common = []
        for row in rows:
            item = dict(row)
            item.update(
                {
                    "embedding_model": settings.embedding_model,
                    "embedding_version": "1",
                    "indexed": False,
                    "updated_at": utcnow(),
                }
            )
            common.append(item)
        if dialect == "postgresql":
            stmt = pg_insert(Product.__table__).values(common)
            update_cols = {
                c.name: getattr(stmt.excluded, c.name)
                for c in Product.__table__.columns
                if c.name not in {"parent_asin", "created_at"}
            }
            db.session.execute(stmt.on_conflict_do_update(index_elements=[Product.parent_asin], set_=update_cols))
        else:
            for item in common:
                existing = db.session.get(Product, item["parent_asin"])
                if existing:
                    for key, value in item.items():
                        if key not in {"parent_asin", "created_at"}:
                            setattr(existing, key, value)
                else:
                    db.session.add(Product(**item))
        db.session.commit()

    def _mark_indexed(self, ids: list[str]) -> None:
        if ids:
            Product.query.filter(Product.parent_asin.in_(ids)).update(
                {Product.indexed: True, Product.indexed_at: utcnow()}, synchronize_session=False
            )
            db.session.commit()

    def _flush_batch(self, rows: list[dict[str, Any]]) -> None:
        self._upsert_products(rows)
        vectors = self.embedder.encode_many([x["search_document"] for x in rows])
        self.qdrant.upsert(rows, vectors)
        self._mark_indexed([x["parent_asin"] for x in rows])

    def ingest(
        self,
        path: Path,
        *,
        batch_size: int = 128,
        checkpoint_every: int = 1000,
        resume_job_id: str | None = None,
        max_records: int | None = None,
    ) -> str:
        path = path.resolve()
        self.progress({"stage": "1/6 Validate source", "status": "starting", "processed": 0})
        if not path.exists():
            raise FileNotFoundError(path)
        if path.stat().st_size <= 0:
            raise ValueError("Dataset file is empty")
        with self.app.app_context():
            self.progress({"stage": "2/6 Database and job", "status": "starting", "processed": 0})
            fingerprint = file_fingerprint(path)
            if resume_job_id:
                job = db.session.get(IngestionJob, resume_job_id)
                if not job:
                    raise ValueError(f"Unknown ingestion job: {resume_job_id}")
                if job.file_hash != fingerprint:
                    raise ValueError("Dataset fingerprint changed. Refusing unsafe resume.")
                job.status = "running"
                job.error = None
                db.session.commit()
            else:
                job = IngestionJob(
                    id=str(uuid.uuid4()),
                    filename=str(path),
                    file_hash=fingerprint,
                    file_size=path.stat().st_size,
                    status="running",
                    stats={"warnings": {}, "top_categories": {}},
                )
                db.session.add(job)
                db.session.commit()
                write_audit("INGESTION_STARTED", actor_type="system", actor_id="semanticfit-ingest", metadata={"job_id": job.id, "filename": str(path)})

            self.progress({"stage": "3/6 Qdrant collection", "status": "starting", "job_id": job.id, "processed": job.processed})
            self.qdrant.ensure_collection()
            self.progress({"stage": "4/6 Embedding model", "status": "loading", "job_id": job.id, "processed": job.processed})
            if not self.embedder.ready():
                raise RuntimeError("Embedding model could not be loaded")
            self.progress({"stage": "5/6 Stream, embed and index", "status": "running", "job_id": job.id, "processed": job.processed})

            error_dir = settings.data_dir / "errors"
            error_dir.mkdir(parents=True, exist_ok=True)
            error_path = error_dir / f"ingestion_{job.id}.jsonl"
            report_dir = settings.reports_dir / "ingestion"
            report_dir.mkdir(parents=True, exist_ok=True)

            warning_counts = Counter((job.stats or {}).get("warnings", {}))
            category_counts = Counter((job.stats or {}).get("top_categories", {}))
            started = time.perf_counter()
            processed_count = int(job.processed)
            success_count = int(job.success)
            failed_count = int(job.failed)
            skipped_count = int(job.skipped)
            start_processed = processed_count
            batch: list[dict[str, Any]] = []
            batch_last_offset = job.current_offset
            batch_last_line = job.current_line
            checkpoint_counter = 0
            limit_reached = False

            try:
                with open_stream(path) as fh, error_path.open("a", encoding="utf-8") as errors:
                    if job.current_offset:
                        fh.seek(job.current_offset)
                    line_number = job.current_line
                    while True:
                        line_start = fh.tell()
                        line = fh.readline()
                        if not line:
                            break
                        line_number += 1
                        line_end = fh.tell()
                        processed_count += 1
                        try:
                            raw = json.loads(line)
                            row, warnings = normalize_product(raw)
                            warning_counts.update(warnings)
                            if row is None:
                                failed_count += 1
                                errors.write(json.dumps({"line": line_number, "offset": line_start, "reason": warnings, "raw_preview": line[:300].decode("utf-8", "replace")}) + "\n")
                            else:
                                batch.append(row)
                                success_count += 1
                                category_counts.update(row.get("categories") or [])
                        except Exception as exc:
                            failed_count += 1
                            errors.write(json.dumps({"line": line_number, "offset": line_start, "reason": str(exc), "raw_preview": line[:300].decode("utf-8", "replace")}) + "\n")

                        batch_last_offset = line_end
                        batch_last_line = line_number
                        checkpoint_counter += 1
                        if len(batch) >= batch_size:
                            self._flush_batch(batch)
                            batch.clear()

                        if checkpoint_counter >= checkpoint_every:
                            self._checkpoint(job, warning_counts, category_counts, batch_last_offset, batch_last_line, started, start_processed, processed_count, success_count, failed_count, skipped_count)
                            checkpoint_counter = 0
                            self.progress(self._progress_payload(job))

                        if max_records is not None and processed_count - start_processed >= max_records:
                            limit_reached = True
                            break

                    if batch:
                        self._flush_batch(batch)
                    self._checkpoint(job, warning_counts, category_counts, batch_last_offset, batch_last_line, started, start_processed, processed_count, success_count, failed_count, skipped_count)

                if limit_reached:
                    job.status = "paused"
                    job.error = None
                    db.session.commit()
                    write_audit("INGESTION_PAUSED", actor_type="system", actor_id="semanticfit-ingest", metadata={"job_id": job.id, "reason": "record_limit", "max_records": max_records})
                    self.progress(self._progress_payload(job))
                    return job.id

                self.progress({"stage": "6/6 Finalize report", "status": "finalizing", "job_id": job.id, "processed": job.processed})
                job.status = "completed"
                job.progress_percent = 100.0
                job.eta_seconds = 0
                job.completed_at = utcnow()
                db.session.commit()
                report = self._report(job, warning_counts, category_counts, error_path)
                (report_dir / f"{job.id}.json").write_text(json.dumps(report, indent=2), encoding="utf-8")
                write_audit("INGESTION_COMPLETED", actor_type="system", actor_id="semanticfit-ingest", metadata={"job_id": job.id, "processed": job.processed, "success": job.success, "failed": job.failed})
                self.progress(self._progress_payload(job))
                return job.id
            except KeyboardInterrupt:
                db.session.rollback()
                job = db.session.get(IngestionJob, job.id)
                job.status = "paused"
                job.error = "Interrupted by user"
                db.session.commit()
                write_audit("INGESTION_PAUSED", actor_type="system", actor_id="semanticfit-ingest", metadata={"job_id": job.id})
                raise
            except Exception as exc:
                db.session.rollback()
                job = db.session.get(IngestionJob, job.id)
                job.status = "failed"
                job.error = str(exc)[:4000]
                db.session.commit()
                write_audit("INGESTION_FAILED", status="failure", actor_type="system", actor_id="semanticfit-ingest", metadata={"job_id": job.id, "error": str(exc)[:1000]})
                raise

    def _checkpoint(self, job, warning_counts, category_counts, offset, line, started, start_processed, processed_count, success_count, failed_count, skipped_count):
        elapsed = max(0.001, time.perf_counter() - started)
        processed_now = max(0, processed_count - start_processed)
        job.processed = processed_count
        job.success = success_count
        job.failed = failed_count
        job.skipped = skipped_count
        rate = processed_now / elapsed
        job.current_offset = int(offset)
        job.current_line = int(line)
        job.rate_per_second = round(rate, 2)
        if not str(job.filename).endswith(".gz") and job.file_size:
            job.progress_percent = min(100.0, (job.current_offset / job.file_size) * 100)
            remaining_bytes = max(0, job.file_size - job.current_offset)
            bytes_per_record = job.current_offset / max(1, job.processed)
            remaining_records = remaining_bytes / max(1, bytes_per_record)
            job.eta_seconds = int(remaining_records / max(rate, 0.001))
        job.stats = {
            "warnings": dict(warning_counts),
            "top_categories": dict(category_counts.most_common(50)),
        }
        job.updated_at = utcnow()
        db.session.commit()

    @staticmethod
    def _progress_payload(job: IngestionJob) -> dict[str, Any]:
        return {
            "stage": "5/6 Stream, embed and index" if job.status == "running" else ("6/6 Complete" if job.status == "completed" else job.status),
            "job_id": job.id,
            "status": job.status,
            "processed": job.processed,
            "success": job.success,
            "failed": job.failed,
            "skipped": job.skipped,
            "progress_percent": round(job.progress_percent, 2),
            "rate_per_second": job.rate_per_second,
            "eta_seconds": job.eta_seconds,
            "current_line": job.current_line,
        }

    @staticmethod
    def _report(job, warnings, categories, error_path):
        return {
            "stage": "5/6 Stream, embed and index" if job.status == "running" else ("6/6 Complete" if job.status == "completed" else job.status),
            "job_id": job.id,
            "file": job.filename,
            "file_hash": job.file_hash,
            "status": job.status,
            "processed": job.processed,
            "success": job.success,
            "failed": job.failed,
            "skipped": job.skipped,
            "warning_counts": dict(warnings),
            "top_categories": categories.most_common(50),
            "error_file": str(error_path),
            "started_at": job.started_at.isoformat() if job.started_at else None,
            "completed_at": job.completed_at.isoformat() if job.completed_at else None,
        }

    def rebuild_index(self, batch_size: int = 128, limit: int | None = None) -> int:
        with self.app.app_context():
            self.qdrant.ensure_collection()
            query = Product.query.order_by(Product.parent_asin)
            count = 0
            offset = 0
            while True:
                rows = query.offset(offset).limit(batch_size).all()
                if not rows:
                    break
                payloads = []
                for p in rows:
                    payloads.append({
                        "parent_asin": p.parent_asin,
                        "title": p.title,
                        "main_category": p.main_category,
                        "price": float(p.price) if p.price is not None else None,
                        "average_rating": p.average_rating,
                        "rating_number": p.rating_number,
                        "store": p.store,
                        "categories": p.categories or [],
                        "primary_image": p.primary_image,
                        "search_document": p.search_document,
                        "search_document_version": p.search_document_version,
                    })
                vectors = self.embedder.encode_many([x["search_document"] for x in payloads])
                self.qdrant.upsert(payloads, vectors)
                self._mark_indexed([p.parent_asin for p in rows])
                count += len(rows)
                offset += len(rows)
                self.progress({"status": "rebuilding", "processed": count})
                if limit and count >= limit:
                    break
            write_audit("INDEX_REBUILT", actor_type="system", actor_id="semanticfit-ingest", metadata={"products": count})
            return count
