from __future__ import annotations

from app import cli
from app.cli import app
from app.schemas import AskResponse, AskSource, SyncResponse
from typer.testing import CliRunner


def test_cli_exposes_commands() -> None:
    runner = CliRunner()

    result = runner.invoke(app, ["--help"])

    assert result.exit_code == 0
    assert "serve" in result.output
    assert "sync" in result.output
    assert "ask" in result.output
    assert "stats" in result.output

    ask_help = runner.invoke(app, ["ask", "--help"])

    assert ask_help.exit_code == 0
    assert "--language" in ask_help.output


def test_cli_sync_forwards_options(monkeypatch) -> None:
    captured: dict[str, object] = {}

    def fake_sync(
        *,
        limit: int | None,
        dry_run: bool,
        local_only: bool,
    ) -> SyncResponse:
        captured.update(
            {
                "limit": limit,
                "dry_run": dry_run,
                "local_only": local_only,
            }
        )
        return SyncResponse(total_fetched=0, markdown_written=0, dry_run=dry_run)

    monkeypatch.setattr(cli, "run_ingestion_sync", fake_sync)
    runner = CliRunner()

    result = runner.invoke(app, ["sync", "--limit", "3", "--dry-run", "--local-only"])

    assert result.exit_code == 0
    assert captured == {"limit": 3, "dry_run": True, "local_only": True}


def test_cli_ask_prints_verified_article_urls(monkeypatch) -> None:
    monkeypatch.setattr(
        cli,
        "answer_question",
        lambda question, language: AskResponse(
            status="answered",
            answer="- Grounded answer",
            sources=[
                AskSource(
                    title="Article",
                    url="https://support.optisigns.com/hc/en-us/articles/1",
                )
            ],
            model="gemini-test",
        ),
    )
    runner = CliRunner()

    result = runner.invoke(app, ["ask", "Question", "--language", "en"])

    assert result.exit_code == 0
    assert "- Grounded answer" in result.output
    assert "Article URL: https://support.optisigns.com" in result.output
