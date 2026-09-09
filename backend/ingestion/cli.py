from __future__ import annotations

import json
from pathlib import Path

import typer
from rich.console import Console
from rich.live import Live
from rich.panel import Panel
from rich.table import Table

from app import create_app
from app.bootstrap import bootstrap
from app.extensions import db
from app.models import IngestionJob, Product
from app.services.qdrant_store import QdrantStore
from ingestion.pipeline import IngestionPipeline, inspect_file, open_stream
from ingestion.normalize import normalize_product

app = typer.Typer(help="SemanticFit streaming dataset ingestion and index management CLI.")
console = Console()


def _ensure_app():
    flask_app = create_app()
    bootstrap(flask_app)
    return flask_app


def _status_table(payload: dict) -> Table:
    table = Table(title=f"SemanticFit ingestion {payload.get('job_id', '')}")
    table.add_column("Metric")
    table.add_column("Value", justify="right")
    for key in ("stage", "status", "processed", "success", "failed", "skipped", "progress_percent", "rate_per_second", "eta_seconds", "current_line"):
        if key in payload:
            table.add_row(key.replace("_", " ").title(), str(payload[key]))
    return table


@app.command()
def inspect(path: Path, sample_records: int = typer.Option(5000, min=100, max=100000)):
    """Inspect structure and data quality using a bounded sample."""
    result = inspect_file(path, sample_records)
    console.print_json(json.dumps(result))


@app.command()
def validate(path: Path, limit: int = typer.Option(0, help="0 validates the entire file."), strict: bool = False):
    """Stream through JSONL and validate records without writing to databases."""
    processed = valid = invalid = warnings = 0
    with open_stream(path) as fh:
        for line in fh:
            if limit and processed >= limit:
                break
            processed += 1
            try:
                raw = json.loads(line)
                row, row_warnings = normalize_product(raw)
                warnings += len(row_warnings)
                if row is None or (strict and row_warnings):
                    invalid += 1
                else:
                    valid += 1
            except Exception:
                invalid += 1
            if processed % 10000 == 0:
                console.print(f"Validated {processed:,} records. valid={valid:,}, invalid={invalid:,}, warnings={warnings:,}")
    console.print(Panel.fit(f"Processed {processed:,}\nValid {valid:,}\nInvalid {invalid:,}\nWarnings {warnings:,}", title="Validation complete"))
    if invalid:
        raise typer.Exit(code=2 if strict else 0)


@app.command()
def ingest(
    path: Path,
    batch_size: int = typer.Option(128, min=1, max=2048),
    checkpoint_every: int = typer.Option(1000, min=100),
    no_ui: bool = typer.Option(False, help="Emit line status rather than a live table."),
):
    """Ingest raw Amazon Fashion JSONL into PostgreSQL and Qdrant."""
    flask_app = _ensure_app()
    last = {}

    def callback(payload):
        nonlocal last
        last = payload
        if no_ui:
            console.print(json.dumps(payload))

    pipeline = IngestionPipeline(flask_app, callback)
    if no_ui:
        job_id = pipeline.ingest(path, batch_size=batch_size, checkpoint_every=checkpoint_every)
    else:
        with Live(_status_table({"status": "starting"}), console=console, refresh_per_second=4) as live:
            def live_callback(payload):
                callback(payload)
                live.update(_status_table(payload))
            pipeline.progress = live_callback
            job_id = pipeline.ingest(path, batch_size=batch_size, checkpoint_every=checkpoint_every)
    console.print(f"[bold green]Completed[/bold green] job {job_id}")


@app.command()
def resume(
    job_id: str,
    batch_size: int = typer.Option(128, min=1, max=2048),
    checkpoint_every: int = typer.Option(1000, min=100),
    max_records: int | None = typer.Option(None, min=1, help="Process at most this many additional source records, then pause."),
):
    """Resume a paused/failed job from the last committed byte offset."""
    flask_app = _ensure_app()
    with flask_app.app_context():
        job = db.session.get(IngestionJob, job_id)
        if not job:
            console.print("[red]Job not found[/red]")
            raise typer.Exit(2)
        path = Path(job.filename)
    with Live(_status_table({"job_id": job_id, "status": "resuming"}), console=console, refresh_per_second=4) as live:
        pipeline = IngestionPipeline(flask_app, lambda payload: live.update(_status_table(payload)))
        pipeline.ingest(path, batch_size=batch_size, checkpoint_every=checkpoint_every, resume_job_id=job_id, max_records=max_records)
    with flask_app.app_context():
        final_status = db.session.get(IngestionJob, job_id).status
    console.print(f"[bold green]{final_status.title()}[/bold green] job {job_id}")


@app.command()
def status(job_id: str | None = None):
    """Show one job or the most recent ingestion jobs."""
    flask_app = _ensure_app()
    with flask_app.app_context():
        if job_id:
            rows = [db.session.get(IngestionJob, job_id)]
        else:
            rows = IngestionJob.query.order_by(IngestionJob.started_at.desc()).limit(10).all()
        rows = [x for x in rows if x]
        table = Table(title="SemanticFit ingestion jobs")
        for col in ("ID", "Status", "Processed", "Success", "Failed", "Progress", "Rate/s"):
            table.add_column(col)
        for row in rows:
            table.add_row(row.id, row.status, f"{row.processed:,}", f"{row.success:,}", f"{row.failed:,}", f"{row.progress_percent:.1f}%", f"{row.rate_per_second:.1f}")
        console.print(table)


@app.command()
def verify():
    """Compare canonical product rows and Qdrant point count."""
    flask_app = _ensure_app()
    with flask_app.app_context():
        products = Product.query.count()
        indexed = Product.query.filter_by(indexed=True).count()
        try:
            vectors = QdrantStore().count()
        except Exception as exc:
            console.print(f"[red]Qdrant unavailable:[/red] {exc}")
            raise typer.Exit(2)
        console.print(Panel.fit(f"PostgreSQL products: {products:,}\nMarked indexed: {indexed:,}\nQdrant points: {vectors:,}\nDifference: {products - vectors:,}", title="Index verification"))


@app.command("rebuild-index")
def rebuild_index(batch_size: int = 128, limit: int = 0):
    """Rebuild Qdrant vectors from PostgreSQL canonical product rows."""
    flask_app = _ensure_app()
    pipeline = IngestionPipeline(flask_app, lambda p: console.print(f"Indexed {p.get('processed', 0):,}"))
    count = pipeline.rebuild_index(batch_size=batch_size, limit=limit or None)
    console.print(f"[green]Rebuilt {count:,} products[/green]")


@app.command()
def reset(yes: bool = typer.Option(False, "--yes", help="Required destructive confirmation.")):
    """Delete product rows and the Qdrant collection. Admin/audit history is retained."""
    if not yes:
        console.print("[red]Refusing destructive reset without --yes[/red]")
        raise typer.Exit(2)
    flask_app = _ensure_app()
    with flask_app.app_context():
        Product.query.delete()
        db.session.commit()
        store = QdrantStore()
        try:
            store.client.delete_collection(store.collection)
        except Exception:
            pass
    console.print("[yellow]Product catalog and vector index reset.[/yellow]")


if __name__ == "__main__":
    app()
