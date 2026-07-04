from __future__ import annotations

import json
from pathlib import Path

import pytest
from app.ingestion.manifest import save_manifest
from app.schemas import LastRunLog, ManifestArticle, ManifestState, SyncResponse
from app.services import stats_service


def test_stats_reads_manifest_and_last_run(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    articles_dir = tmp_path / "articles"
    articles_dir.mkdir()
    (articles_dir / "1-Sample.md").write_text("# Sample\n", encoding="utf-8")
    manifest_path = tmp_path / "manifest.json"
    log_path = tmp_path / "logs" / "last_run.json"

    save_manifest(
        manifest_path,
        ManifestState(
            gemini_file_search_store_name="fileSearchStores/test-store",
            articles={
                "1": ManifestArticle(
                    article_id=1,
                    slug="1-Sample",
                    title="Sample",
                    source_url="https://support.optisigns.com/hc/en-us/articles/1-Sample",
                    content_hash="hash-a",
                    local_path=str(articles_dir / "1-Sample.md"),
                    last_synced_at="2026-01-01T00:00:00+00:00",
                    gemini_document_name="fileSearchStores/test-store/documents/doc-1",
                    gemini_file_search_store_name="fileSearchStores/test-store",
                    uploaded_content_hash="hash-a",
                    upload_status="uploaded",
                ),
                "2": ManifestArticle(
                    article_id=2,
                    slug="2-Pending",
                    title="Pending",
                    source_url="https://support.optisigns.com/hc/en-us/articles/2-Pending",
                    content_hash="hash-b",
                    local_path=str(articles_dir / "2-Pending.md"),
                    last_synced_at="2026-01-01T00:00:00+00:00",
                    upload_status="indexing",
                ),
            },
        ),
    )
    log_path.parent.mkdir()
    log_path.write_text(
        json.dumps(
            LastRunLog(
                started_at="2026-01-01T00:00:00+00:00",
                finished_at="2026-01-01T00:01:00+00:00",
                success=True,
                limit=5,
                dry_run=False,
                local_only=False,
                summary=SyncResponse(total_fetched=2, markdown_written=2, dry_run=False),
            ).model_dump(mode="json")
        ),
        encoding="utf-8",
    )
    monkeypatch.setattr(stats_service, "ARTICLES_DIR", articles_dir)
    monkeypatch.setattr(stats_service, "MANIFEST_PATH", manifest_path)
    monkeypatch.setattr(stats_service, "LAST_RUN_LOG_PATH", log_path)

    stats = stats_service.get_stats()

    assert stats.article_count == 1
    assert stats.manifest_exists is True
    assert stats.last_run_exists is True
    assert stats.file_search_store_name == "fileSearchStores/test-store"
    assert stats.manifest_article_count == 2
    assert stats.uploaded_article_count == 1
    assert stats.pending_article_count == 1
    assert stats.failed_article_count == 0
    assert stats.last_run_success is True
    assert stats.last_run_finished_at == "2026-01-01T00:01:00+00:00"
