from __future__ import annotations

import json
from pathlib import Path

import pytest
from app.ingestion.manifest import load_manifest, save_manifest
from app.schemas import ManifestArticle, ManifestState


def test_load_manifest_returns_empty_state_when_missing(tmp_path: Path) -> None:
    manifest = load_manifest(tmp_path / "manifest.json")

    assert manifest.articles == {}


def test_load_manifest_rejects_non_object_json(tmp_path: Path) -> None:
    manifest_path = tmp_path / "manifest.json"
    manifest_path.write_text("[]", encoding="utf-8")

    with pytest.raises(ValueError, match="Manifest must be a JSON object"):
        load_manifest(manifest_path)


def test_save_and_load_manifest_roundtrip(tmp_path: Path) -> None:
    manifest_path = tmp_path / "manifest.json"
    manifest = ManifestState(
        articles={
            "1": ManifestArticle(
                article_id=1,
                slug="1-Sample",
                title="Sample",
                source_url="https://support.optisigns.com/hc/en-us/articles/1-Sample",
                updated_at="2026-01-01T00:00:00Z",
                content_hash="abc123",
                local_path="data/articles/1-Sample.md",
                last_synced_at="2026-01-01T00:00:01+00:00",
            )
        }
    )

    save_manifest(manifest_path, manifest)
    loaded = load_manifest(manifest_path)

    assert loaded == manifest


def test_load_manifest_accepts_entries_without_gemini_metadata(tmp_path: Path) -> None:
    manifest_path = tmp_path / "manifest.json"
    manifest_path.write_text(
        json.dumps(
            {
                "articles": {
                    "1": {
                        "article_id": 1,
                        "slug": "1-Sample",
                        "title": "Sample",
                        "source_url": (
                            "https://support.optisigns.com/hc/en-us/articles/1-Sample"
                        ),
                        "updated_at": "2026-01-01T00:00:00Z",
                        "content_hash": "abc123",
                        "local_path": "data/articles/1-Sample.md",
                        "last_synced_at": "2026-01-01T00:00:01+00:00",
                    }
                }
            }
        ),
        encoding="utf-8",
    )

    loaded = load_manifest(manifest_path)
    article = loaded.articles["1"]

    assert article.gemini_document_name is None
    assert article.gemini_file_search_store_name is None
    assert article.uploaded_at is None
    assert article.upload_status is None
