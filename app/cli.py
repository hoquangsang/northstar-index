from __future__ import annotations

from typing import Annotated

import typer
import uvicorn

from app.config import get_settings
from app.errors import GeminiQueryError, KnowledgeBaseNotReadyError
from app.schemas import AnswerLanguage
from app.services.chat_service import answer_question
from app.services.stats_service import get_stats
from app.services.sync_service import run_ingestion_sync
from app.utils.logging import console
from app.utils.paths import ensure_runtime_dirs

app = typer.Typer(
    help="Northstar Index CLI for sync jobs, grounded questions, and the API server.",
    no_args_is_help=True,
)


@app.command()
def serve() -> None:
    """Start the FastAPI server."""
    settings = get_settings()
    ensure_runtime_dirs()
    uvicorn.run(
        "app.api.app:create_app",
        factory=True,
        host=settings.app_host,
        port=settings.app_port,
    )


@app.command()
def sync(
    limit: int | None = typer.Option(default=None, min=1, help="Maximum articles to process."),
    dry_run: bool = typer.Option(
        default=False,
        help="Preview local changes without writing files or calling Gemini.",
    ),
    local_only: bool = typer.Option(
        default=False,
        help="Write local articles and manifest without calling Gemini.",
    ),
) -> None:
    """Run the knowledge-base sync pipeline."""
    ensure_runtime_dirs()
    try:
        response = run_ingestion_sync(
            limit=limit,
            dry_run=dry_run,
            local_only=local_only,
        )
    except RuntimeError as exc:
        console.print(f"[red]{exc}[/red]")
        raise typer.Exit(code=1) from exc

    console.print(response.model_dump())
    if response.failed:
        raise typer.Exit(code=1)


@app.command()
def ask(
    question: str,
    language: Annotated[
        AnswerLanguage,
        typer.Option(help="Answer language: auto, en, or vi.", case_sensitive=False),
    ] = AnswerLanguage.AUTO,
) -> None:
    """Ask a grounded question using uploaded knowledge-base documents."""
    ensure_runtime_dirs()
    try:
        response = answer_question(question, language)
    except (KnowledgeBaseNotReadyError, GeminiQueryError) as exc:
        console.print(f"[red]{exc}[/red]")
        raise typer.Exit(code=1) from exc

    console.print(response.answer, markup=False)
    for source in response.sources:
        console.print(f"Article URL: {source.url}", markup=False)


@app.command()
def stats() -> None:
    """Print local runtime state statistics."""
    console.print(get_stats().model_dump())
