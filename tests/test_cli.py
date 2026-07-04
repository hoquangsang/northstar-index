from __future__ import annotations

from app import cli
from app.cli import app
from app.schemas import AskResponse, AskSource
from typer.testing import CliRunner


def test_cli_exposes_commands() -> None:
    runner = CliRunner()

    result = runner.invoke(app, ["--help"])

    assert result.exit_code == 0
    assert "serve" in result.output
    assert "sync" in result.output
    assert "ask" in result.output
    assert "stats" in result.output

    sync_help = runner.invoke(app, ["sync", "--help"])

    assert sync_help.exit_code == 0
    assert "--local-only" in sync_help.output
    assert "--dry-run" in sync_help.output

    ask_help = runner.invoke(app, ["ask", "--help"])

    assert ask_help.exit_code == 0
    assert "--language" in ask_help.output


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
