from __future__ import annotations

import json
from datetime import UTC, datetime

from app.config import get_settings
from app.ingestion.pipeline import run_ingestion
from app.integrations.gemini_client import build_gemini_client
from app.integrations.gemini_file_search import GeminiFileSearchGateway
from app.rag.file_search import sync_markdown_files
from app.schemas import LastRunLog, SyncResponse
from app.utils.paths import ARTICLES_DIR, LAST_RUN_LOG_PATH, MANIFEST_PATH


def run_ingestion_sync(
    limit: int | None,
    dry_run: bool,
    local_only: bool = False,
) -> SyncResponse:
    started_at = _utc_now()
    try:
        response = _run_ingestion_sync(
            limit=limit,
            dry_run=dry_run,
            local_only=local_only,
        )
    except Exception as exc:
        _write_last_run_log(
            LastRunLog(
                started_at=started_at,
                finished_at=_utc_now(),
                success=False,
                limit=limit,
                dry_run=dry_run,
                local_only=local_only,
                error=str(exc),
            )
        )
        raise

    _write_last_run_log(
        LastRunLog(
            started_at=started_at,
            finished_at=_utc_now(),
            success=response.failed == 0,
            limit=limit,
            dry_run=dry_run,
            local_only=local_only,
            summary=response,
        )
    )
    return response


def _run_ingestion_sync(
    limit: int | None,
    dry_run: bool,
    local_only: bool,
) -> SyncResponse:
    settings = get_settings()
    ingestion = run_ingestion(
        base_url=str(settings.support_base_url),
        output_dir=ARTICLES_DIR,
        manifest_path=MANIFEST_PATH,
        limit=limit,
        dry_run=dry_run,
    )
    response = ingestion.response
    if dry_run or local_only:
        return response

    gateway = GeminiFileSearchGateway(build_gemini_client(settings))
    file_search = sync_markdown_files(
        gateway=gateway,
        manifest_path=MANIFEST_PATH,
        article_keys=ingestion.article_keys,
        configured_store_name=settings.gemini_file_search_store_name,
        store_display_name=settings.gemini_file_search_store_display_name,
    )
    return response.model_copy(
        update={
            "uploaded": file_search.uploaded,
            "upload_skipped": file_search.skipped,
            "upload_failed": file_search.failed,
            "file_search_store_name": file_search.store_name,
            "failed": response.failed + file_search.failed,
            "failures": [*response.failures, *file_search.failures],
        }
    )


def _write_last_run_log(log: LastRunLog) -> None:
    LAST_RUN_LOG_PATH.parent.mkdir(parents=True, exist_ok=True)
    LAST_RUN_LOG_PATH.write_text(
        json.dumps(log.model_dump(mode="json"), ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )


def _utc_now() -> str:
    return datetime.now(UTC).replace(microsecond=0).isoformat()
