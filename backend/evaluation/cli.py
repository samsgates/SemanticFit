from __future__ import annotations

import asyncio
import json
import statistics
import time
from pathlib import Path

import httpx
import typer
from rich.console import Console
from rich.table import Table

from app import create_app
from app.bootstrap import bootstrap
from app.extensions import db
from app.models import EvaluationRun
from evaluation.metrics import percentile
from evaluation.runner import EvaluationRunner, load_cases

app = typer.Typer(help="SemanticFit recommendation quality and performance evaluation CLI.")
console = Console()


def _app():
    flask_app = create_app()
    bootstrap(flask_app)
    return flask_app


@app.command()
def validate(dataset: Path):
    cases = load_cases(dataset)
    errors = []
    for idx, case in enumerate(cases, 1):
        if not case.get("query"):
            errors.append(f"line {idx}: missing query")
        if not case.get("id"):
            errors.append(f"line {idx}: missing id")
    if errors:
        for error in errors:
            console.print(f"[red]{error}[/red]")
        raise typer.Exit(2)
    console.print(f"[green]Valid evaluation dataset with {len(cases)} cases.[/green]")


@app.command()
def run(
    dataset: Path = typer.Option(Path("../evaluation/datasets/core.jsonl"), exists=True),
    name: str | None = None,
    k: int = typer.Option(10, min=1, max=50),
    fail_on_regression: bool = False,
):
    flask_app = _app()
    runner = EvaluationRunner(flask_app)
    with flask_app.app_context():
        previous = EvaluationRun.query.filter_by(status="completed").order_by(EvaluationRun.completed_at.desc()).first()
    result = runner.run(dataset, name=name, k=k)
    table = Table(title=result.run_name)
    table.add_column("Metric")
    table.add_column("Value", justify="right")
    for key, value in result.metrics.items():
        table.add_row(key, str(value))
    console.print(table)
    console.print(f"Report: {result.report_dir}")
    if fail_on_regression and previous:
        current_score = result.metrics.get("ndcg_at_k", result.metrics.get("intent_coverage", 0))
        previous_score = previous.metrics.get("ndcg_at_k", previous.metrics.get("intent_coverage", 0))
        if current_score + 0.02 < previous_score:
            console.print(f"[red]Regression detected: {previous_score:.4f} -> {current_score:.4f}[/red]")
            raise typer.Exit(3)


@app.command()
def compare(run_a: str, run_b: str):
    flask_app = _app()
    with flask_app.app_context():
        a = db.session.get(EvaluationRun, run_a)
        b = db.session.get(EvaluationRun, run_b)
        if not a or not b:
            console.print("[red]One or both run IDs were not found.[/red]")
            raise typer.Exit(2)
        keys = sorted(set((a.metrics or {}).keys()) | set((b.metrics or {}).keys()))
        table = Table(title="Evaluation comparison")
        table.add_column("Metric")
        table.add_column("A")
        table.add_column("B")
        table.add_column("Δ")
        for key in keys:
            av, bv = (a.metrics or {}).get(key), (b.metrics or {}).get(key)
            delta = ""
            if isinstance(av, (int, float)) and isinstance(bv, (int, float)):
                delta = f"{bv - av:+.4f}"
            table.add_row(key, str(av), str(bv), delta)
        console.print(table)


@app.command()
def report(run_id: str):
    flask_app = _app()
    with flask_app.app_context():
        row = db.session.get(EvaluationRun, run_id)
        if not row:
            raise typer.Exit(2)
        console.print_json(json.dumps({"id": row.id, "name": row.run_name, "metrics": row.metrics, "report_dir": row.report_dir}))


async def _benchmark(url: str, query: str, concurrency: int, requests_count: int):
    semaphore = asyncio.Semaphore(concurrency)
    latencies = []
    errors = 0
    async with httpx.AsyncClient(timeout=60) as client:
        async def one(i: int):
            nonlocal errors
            async with semaphore:
                started = time.perf_counter()
                try:
                    response = await client.post(url.rstrip("/") + "/api/v1/recommendations", json={"query": query, "limit": 8}, headers={"X-Session-ID": "benchmark"})
                    response.raise_for_status()
                except Exception:
                    errors += 1
                finally:
                    latencies.append((time.perf_counter() - started) * 1000)
        await asyncio.gather(*(one(i) for i in range(requests_count)))
    return latencies, errors


@app.command()
def benchmark(
    url: str = "http://localhost:5000",
    query: str = "lightweight clothes for a summer beach vacation",
    concurrency: int = typer.Option(10, min=1, max=100),
    requests_count: int = typer.Option(50, min=1, max=5000),
):
    latencies, errors = asyncio.run(_benchmark(url, query, concurrency, requests_count))
    table = Table(title="SemanticFit API benchmark")
    table.add_column("Metric")
    table.add_column("Value", justify="right")
    table.add_row("Requests", str(requests_count))
    table.add_row("Concurrency", str(concurrency))
    table.add_row("Errors", str(errors))
    table.add_row("Mean ms", f"{statistics.mean(latencies):.2f}")
    table.add_row("P50 ms", f"{percentile(latencies, .5):.2f}")
    table.add_row("P95 ms", f"{percentile(latencies, .95):.2f}")
    table.add_row("P99 ms", f"{percentile(latencies, .99):.2f}")
    console.print(table)


if __name__ == "__main__":
    app()
