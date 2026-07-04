from __future__ import annotations

import json

from pydantic import ValidationError

from app.ingestion.manifest import load_manifest
from app.schemas import LastRunLog, ManifestArticle, StatsResponse
from app.utils.paths import ARTICLES_DIR, LAST_RUN_LOG_PATH, MANIFEST_PATH


def get_stats() -> StatsResponse:
    article_count = len(list(ARTICLES_DIR.glob("*.md"))) if ARTICLES_DIR.exists() else 0
    manifest_exists = MANIFEST_PATH.exists()
    manifest = load_manifest(MANIFEST_PATH) if manifest_exists else None
    articles = tuple(manifest.articles.values()) if manifest else ()
    last_run = _load_last_run_log()
    return StatsResponse(
        article_count=article_count,
        manifest_exists=manifest_exists,
        last_run_exists=LAST_RUN_LOG_PATH.exists(),
        file_search_store_name=manifest.gemini_file_search_store_name if manifest else None,
        manifest_article_count=len(articles),
        uploaded_article_count=sum(1 for article in articles if _is_uploaded(article)),
        pending_article_count=sum(1 for article in articles if _is_pending(article)),
        failed_article_count=sum(1 for article in articles if article.upload_status == "failed"),
        last_run_success=last_run.success if last_run else None,
        last_run_finished_at=last_run.finished_at if last_run else None,
    )


def _load_last_run_log() -> LastRunLog | None:
    if not LAST_RUN_LOG_PATH.exists():
        return None
    try:
        raw = json.loads(LAST_RUN_LOG_PATH.read_text(encoding="utf-8"))
        return LastRunLog.model_validate(raw)
    except (OSError, json.JSONDecodeError, ValidationError):
        return None


def _is_uploaded(article: ManifestArticle) -> bool:
    return bool(
        article.gemini_document_name
        and article.uploaded_content_hash == article.content_hash
        and article.upload_status == "uploaded"
    )


def _is_pending(article: ManifestArticle) -> bool:
    return article.upload_status in {"pending", "indexing", "cleanup_pending"}
