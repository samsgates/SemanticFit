from __future__ import annotations

import csv
import json
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from app.audit import write_audit
from app.config import settings
from app.extensions import db
from app.models import EvaluationRun, Product
from app.services.search import SearchService
from evaluation.metrics import aggregate_case_metrics, ndcg_at_k, precision_at_k, recall_at_k, reciprocal_rank


def utcnow():
    return datetime.now(timezone.utc)


def load_cases(path: Path) -> list[dict[str, Any]]:
    cases = []
    with path.open("r", encoding="utf-8") as fh:
        for line in fh:
            line = line.strip()
            if line:
                cases.append(json.loads(line))
    return cases


def _proxy_relevance(result: dict[str, Any], expected_terms: list[str], expected_categories: list[str]) -> int:
    haystack = " ".join(
        [
            str(result.get("title") or ""),
            str(result.get("main_category") or ""),
            " ".join(result.get("categories") or []),
            str(result.get("reason") or ""),
        ]
    ).lower()
    terms = [x.lower() for x in expected_terms]
    cats = [x.lower() for x in expected_categories]
    term_hit = any(x in haystack for x in terms) if terms else False
    cat_hit = any(x in haystack for x in cats) if cats else False
    return 1 if term_hit or cat_hit else 0


def _constraint_ok(result: dict[str, Any], constraints: dict[str, Any]) -> bool:
    price = result.get("price")
    rating = result.get("rating")
    if constraints.get("max_price") is not None and (price is None or float(price) > float(constraints["max_price"])):
        return False
    if constraints.get("min_price") is not None and (price is None or float(price) < float(constraints["min_price"])):
        return False
    if constraints.get("min_rating") is not None and (rating is None or float(rating) < float(constraints["min_rating"])):
        return False
    return True


def _intent_coverage(results: list[dict[str, Any]], terms: list[str], categories: list[str]) -> float:
    expected = [x.lower() for x in terms + categories if x]
    if not expected:
        return 1.0 if results else 0.0
    combined = " ".join(
        " ".join([str(r.get("title") or ""), " ".join(r.get("categories") or []), str(r.get("reason") or "")])
        for r in results
    ).lower()
    return sum(1 for x in expected if x in combined) / len(expected)


def _diversity(results: list[dict[str, Any]]) -> float:
    if not results:
        return 0.0
    leaves = []
    for result in results:
        cats = result.get("categories") or []
        leaves.append(str(cats[-1] if cats else result.get("main_category") or "unknown").lower())
    return len(set(leaves)) / len(leaves)


class EvaluationRunner:
    def __init__(self, app):
        self.app = app

    def run(self, dataset_path: Path, *, name: str | None = None, k: int = 10) -> EvaluationRun:
        cases = load_cases(dataset_path)
        run_id = str(uuid.uuid4())
        report_root = settings.reports_dir / "evaluation" / datetime.now().strftime("%Y%m%d_%H%M%S")
        report_root.mkdir(parents=True, exist_ok=True)

        with self.app.app_context():
            run = EvaluationRun(
                id=run_id,
                run_name=name or f"SemanticFit evaluation {datetime.now().isoformat(timespec='seconds')}",
                model_version=settings.embedding_model,
                index_version="1",
                dataset_version=dataset_path.name,
                config={
                    "k": k,
                    "embedding_model": settings.embedding_model,
                    "reranker_model": settings.reranker_model if settings.reranker_enabled else None,
                    "llm_enabled": settings.llm_enabled,
                },
                report_dir=str(report_root),
                status="running",
            )
            db.session.add(run)
            db.session.commit()
            write_audit("EVALUATION_STARTED", actor_type="system", actor_id="semanticfit-eval", metadata={"run_id": run_id, "dataset": str(dataset_path)})

            results_out: list[dict[str, Any]] = []
            service = SearchService()
            for case in cases:
                query = case["query"]
                constraints = case.get("constraints") or {}
                response = service.search(
                    query,
                    limit=k,
                    filters=constraints,
                    request_id=f"eval_{uuid.uuid4().hex}",
                    session_id="evaluation",
                    debug=False,
                    persist_event=False,
                )
                results = response.get("results", [])
                result_ids = [x["product_id"] for x in results]
                expected_terms = case.get("expected_terms") or []
                expected_categories = case.get("expected_categories") or []
                proxy_rel = [_proxy_relevance(x, expected_terms, expected_categories) for x in results]
                relevant_ids = set(case.get("relevant_parent_asins") or [])
                has_labels = bool(relevant_ids)
                manual_rel = [1 if x in relevant_ids else 0 for x in result_ids] if has_labels else []
                constraint_score = sum(1 for x in results if _constraint_ok(x, constraints)) / len(results) if results else 0.0
                row = {
                    "id": case.get("id"),
                    "query": query,
                    "result_ids": result_ids,
                    "latency_ms": response["meta"]["latency_ms"],
                    "proxy_hits": sum(proxy_rel),
                    "proxy_precision_at_k": precision_at_k(proxy_rel, k),
                    "intent_coverage": _intent_coverage(results, expected_terms, expected_categories),
                    "constraint_satisfaction": constraint_score,
                    "diversity": _diversity(results),
                    "has_manual_labels": has_labels,
                }
                if has_labels:
                    row.update(
                        {
                            "precision_at_k": precision_at_k(manual_rel, k),
                            "recall_at_k": recall_at_k(result_ids, relevant_ids, k) or 0.0,
                            "mrr": reciprocal_rank(manual_rel),
                            "ndcg_at_k": ndcg_at_k(manual_rel, k),
                        }
                    )
                results_out.append(row)

            metrics = aggregate_case_metrics(results_out)
            run.metrics = metrics
            run.cases = results_out
            run.status = "completed"
            run.completed_at = utcnow()
            db.session.commit()
            self._write_reports(report_root, run)
            write_audit("EVALUATION_COMPLETED", actor_type="system", actor_id="semanticfit-eval", metadata={"run_id": run_id, "metrics": metrics})
            return run

    @staticmethod
    def _write_reports(report_root: Path, run: EvaluationRun) -> None:
        summary = {
            "id": run.id,
            "run_name": run.run_name,
            "config": run.config,
            "metrics": run.metrics,
            "cases": run.cases,
        }
        (report_root / "summary.json").write_text(json.dumps(summary, indent=2), encoding="utf-8")

        with (report_root / "cases.csv").open("w", newline="", encoding="utf-8") as fh:
            fieldnames = sorted({key for row in (run.cases or []) for key in row.keys()})
            writer = csv.DictWriter(fh, fieldnames=fieldnames)
            writer.writeheader()
            for row in run.cases or []:
                writer.writerow({k: json.dumps(v) if isinstance(v, (dict, list)) else v for k, v in row.items()})

        metric_lines = "\n".join(f"| {k} | {v} |" for k, v in (run.metrics or {}).items())
        markdown = f"# {run.run_name}\n\n| Metric | Value |\n|---|---:|\n{metric_lines}\n"
        (report_root / "report.md").write_text(markdown, encoding="utf-8")
        html_rows = "".join(f"<tr><td>{k}</td><td>{v}</td></tr>" for k, v in (run.metrics or {}).items())
        html = f"""<!doctype html><html><head><meta charset='utf-8'><title>{run.run_name}</title>
<style>body{{font:16px system-ui;max-width:960px;margin:40px auto;padding:0 24px;color:#171717}}table{{width:100%;border-collapse:collapse}}td,th{{padding:10px;border-bottom:1px solid #ddd;text-align:left}}h1{{font-size:30px}}</style></head>
<body><h1>{run.run_name}</h1><p>Run ID: {run.id}</p><table><thead><tr><th>Metric</th><th>Value</th></tr></thead><tbody>{html_rows}</tbody></table></body></html>"""
        (report_root / "report.html").write_text(html, encoding="utf-8")
