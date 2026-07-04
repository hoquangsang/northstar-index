from __future__ import annotations

from collections.abc import Callable
from pathlib import Path

import pytest
from app.ingestion import pipeline
from app.ingestion.manifest import load_manifest, save_manifest
from app.schemas import Article


def test_pipeline_dry_run_does_not_write_files(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(pipeline, "fetch_articles", _fake_fetch_articles("<p>Hello</p>"))

    output_dir = tmp_path / "articles"
    manifest_path = tmp_path / "manifest.json"
    summary = pipeline.run_sync(
        base_url="https://support.optisigns.com",
        output_dir=output_dir,
        manifest_path=manifest_path,
        limit=1,
        dry_run=True,
    )

    assert summary.total_fetched == 1
    assert summary.added == 1
    assert summary.updated == 0
    assert summary.skipped == 0
    assert summary.markdown_written == 0
    assert summary.article_paths == []
    assert not output_dir.exists()
    assert not manifest_path.exists()


def test_pipeline_writes_new_article_and_manifest(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(pipeline, "fetch_articles", _fake_fetch_articles("<p>Hello</p>"))

    output_dir = tmp_path / "articles"
    manifest_path = tmp_path / "manifest.json"
    summary = pipeline.run_sync(
        base_url="https://support.optisigns.com",
        output_dir=output_dir,
        manifest_path=manifest_path,
        limit=1,
    )

    assert summary.added == 1
    assert summary.updated == 0
    assert summary.skipped == 0
    assert summary.markdown_written == 1
    assert manifest_path.exists()
    assert (output_dir / "1-Sample.md").exists()


def test_pipeline_skips_unchanged_article(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(pipeline, "fetch_articles", _fake_fetch_articles("<p>Hello</p>"))
    output_dir = tmp_path / "articles"
    manifest_path = tmp_path / "manifest.json"

    pipeline.run_sync(
        base_url="https://support.optisigns.com",
        output_dir=output_dir,
        manifest_path=manifest_path,
        limit=1,
    )
    summary = pipeline.run_sync(
        base_url="https://support.optisigns.com",
        output_dir=output_dir,
        manifest_path=manifest_path,
        limit=1,
        dry_run=True,
    )

    assert summary.added == 0
    assert summary.updated == 0
    assert summary.skipped == 1
    assert summary.markdown_written == 0
    assert summary.article_paths == []


def test_pipeline_detects_updated_article(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    output_dir = tmp_path / "articles"
    manifest_path = tmp_path / "manifest.json"
    monkeypatch.setattr(pipeline, "fetch_articles", _fake_fetch_articles("<p>Hello</p>"))
    pipeline.run_sync(
        base_url="https://support.optisigns.com",
        output_dir=output_dir,
        manifest_path=manifest_path,
        limit=1,
    )

    monkeypatch.setattr(pipeline, "fetch_articles", _fake_fetch_articles("<p>Changed</p>"))
    summary = pipeline.run_sync(
        base_url="https://support.optisigns.com",
        output_dir=output_dir,
        manifest_path=manifest_path,
        limit=1,
        dry_run=True,
    )

    assert summary.added == 0
    assert summary.updated == 1
    assert summary.skipped == 0
    assert summary.markdown_written == 0


def test_pipeline_preserves_remote_state_when_local_content_changes(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    output_dir = tmp_path / "articles"
    manifest_path = tmp_path / "manifest.json"
    monkeypatch.setattr(pipeline, "fetch_articles", _fake_fetch_articles("<p>Hello</p>"))
    pipeline.run_sync(
        base_url="https://support.optisigns.com",
        output_dir=output_dir,
        manifest_path=manifest_path,
        limit=1,
    )
    manifest = load_manifest(manifest_path)
    article = manifest.articles["1"]
    original_hash = article.content_hash
    article.gemini_document_name = "fileSearchStores/store/documents/doc-old"
    article.gemini_file_search_store_name = "fileSearchStores/store"
    article.uploaded_content_hash = original_hash
    article.upload_status = "uploaded"
    save_manifest(manifest_path, manifest)

    monkeypatch.setattr(pipeline, "fetch_articles", _fake_fetch_articles("<p>Changed</p>"))
    pipeline.run_sync(
        base_url="https://support.optisigns.com",
        output_dir=output_dir,
        manifest_path=manifest_path,
        limit=1,
    )

    updated = load_manifest(manifest_path).articles["1"]
    assert updated.content_hash != original_hash
    assert updated.gemini_document_name == "fileSearchStores/store/documents/doc-old"
    assert updated.uploaded_content_hash == original_hash
    assert updated.upload_status == "pending"


def _fake_fetch_articles(body: str) -> Callable[[str, int | None], list[Article]]:
    def fake_fetch_articles(base_url: str, limit: int | None) -> list[Article]:
        return [
            Article(
                article_id=1,
                title="Sample",
                html_url="https://support.optisigns.com/hc/en-us/articles/1-Sample",
                body=body,
            )
        ]

    return fake_fetch_articles
