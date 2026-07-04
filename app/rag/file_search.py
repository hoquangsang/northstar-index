from __future__ import annotations

import time
from collections.abc import Callable, Iterable
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Protocol

from app.ingestion.manifest import load_manifest, save_manifest
from app.schemas import ManifestArticle, ManifestState


@dataclass(frozen=True)
class UploadOperation:
    name: str
    done: bool
    document_name: str | None = None
    error: str | None = None


class FileSearchGateway(Protocol):
    def get_store(self, name: str) -> str: ...

    def create_store(self, display_name: str, embedding_model: str) -> str: ...

    def upload_document(
        self,
        store_name: str,
        file_path: Path,
        display_name: str,
        metadata: dict[str, str],
    ) -> UploadOperation: ...

    def get_upload_operation(self, operation_name: str) -> UploadOperation: ...

    def delete_document(self, document_name: str) -> None: ...


@dataclass(frozen=True)
class FileSearchSyncResult:
    uploaded: int
    skipped: int
    failed: int
    failures: tuple[str, ...]
    store_name: str


def sync_markdown_files(
    gateway: FileSearchGateway,
    manifest_path: Path,
    article_keys: Iterable[str],
    configured_store_name: str | None,
    store_display_name: str,
    embedding_model: str = "models/gemini-embedding-2",
    operation_timeout_seconds: float = 300,
    poll_interval_seconds: float = 5,
    sleep: Callable[[float], None] = time.sleep,
    monotonic: Callable[[], float] = time.monotonic,
) -> FileSearchSyncResult:
    manifest = load_manifest(manifest_path)
    store_name = _resolve_store(
        gateway=gateway,
        manifest=manifest,
        manifest_path=manifest_path,
        configured_store_name=configured_store_name,
        display_name=store_display_name,
        embedding_model=embedding_model,
    )
    uploaded = 0
    skipped = 0
    failures: list[str] = []

    for article_key in dict.fromkeys(article_keys):
        article = manifest.articles.get(article_key)
        if article is None:
            continue
        try:
            was_uploaded = _sync_article(
                gateway=gateway,
                manifest=manifest,
                manifest_path=manifest_path,
                article=article,
                store_name=store_name,
                operation_timeout_seconds=operation_timeout_seconds,
                poll_interval_seconds=poll_interval_seconds,
                sleep=sleep,
                monotonic=monotonic,
            )
            if was_uploaded:
                uploaded += 1
            else:
                skipped += 1
        except Exception as exc:
            if article.pending_upload_operation_name:
                article.upload_status = "indexing"
            elif article.pending_delete_document_name:
                article.upload_status = "cleanup_pending"
            else:
                article.upload_status = "failed"
            save_manifest(manifest_path, manifest)
            failures.append(f"{article.article_id}: Gemini File Search: {exc}")

    return FileSearchSyncResult(
        uploaded=uploaded,
        skipped=skipped,
        failed=len(failures),
        failures=tuple(failures),
        store_name=store_name,
    )


def _resolve_store(
    gateway: FileSearchGateway,
    manifest: ManifestState,
    manifest_path: Path,
    configured_store_name: str | None,
    display_name: str,
    embedding_model: str,
) -> str:
    saved_store_name = manifest.gemini_file_search_store_name
    selected_store_name = configured_store_name or saved_store_name
    if selected_store_name:
        store_name = gateway.get_store(selected_store_name)
    else:
        store_name = gateway.create_store(display_name, embedding_model)

    if not store_name:
        raise RuntimeError("Gemini returned a File Search Store without a name.")

    if manifest.gemini_file_search_store_name != store_name:
        manifest.gemini_file_search_store_name = store_name
        save_manifest(manifest_path, manifest)
    return store_name


def _sync_article(
    gateway: FileSearchGateway,
    manifest: ManifestState,
    manifest_path: Path,
    article: ManifestArticle,
    store_name: str,
    operation_timeout_seconds: float,
    poll_interval_seconds: float,
    sleep: Callable[[float], None],
    monotonic: Callable[[], float],
) -> bool:
    uploaded = False

    while True:
        if article.pending_delete_document_name:
            gateway.delete_document(article.pending_delete_document_name)
            article.pending_delete_document_name = None
            article.upload_status = _settled_status(article, store_name)
            save_manifest(manifest_path, manifest)

        if article.pending_upload_operation_name:
            operation = gateway.get_upload_operation(article.pending_upload_operation_name)
            completed_operation = _wait_for_operation(
                gateway=gateway,
                operation=operation,
                timeout_seconds=operation_timeout_seconds,
                poll_interval_seconds=poll_interval_seconds,
                sleep=sleep,
                monotonic=monotonic,
            )
            _complete_upload(
                manifest=manifest,
                manifest_path=manifest_path,
                article=article,
                store_name=store_name,
                operation=completed_operation,
            )
            uploaded = True
            continue

        if _is_uploaded_version_current(article, store_name):
            if article.upload_status != "uploaded":
                article.upload_status = "uploaded"
                save_manifest(manifest_path, manifest)
            return uploaded

        file_path = Path(article.local_path)
        if not file_path.is_file():
            raise FileNotFoundError(f"Markdown file not found: {file_path}")

        operation = gateway.upload_document(
            store_name=store_name,
            file_path=file_path,
            display_name=file_path.name,
            metadata={
                "article_id": str(article.article_id),
                "slug": article.slug,
                "source_url": article.source_url,
            },
        )
        if not operation.name:
            raise RuntimeError("Gemini returned an upload operation without a name.")

        article.pending_upload_operation_name = operation.name
        article.pending_upload_content_hash = article.content_hash
        article.upload_status = "indexing"
        save_manifest(manifest_path, manifest)

        completed_operation = _wait_for_operation(
            gateway=gateway,
            operation=operation,
            timeout_seconds=operation_timeout_seconds,
            poll_interval_seconds=poll_interval_seconds,
            sleep=sleep,
            monotonic=monotonic,
        )
        _complete_upload(
            manifest=manifest,
            manifest_path=manifest_path,
            article=article,
            store_name=store_name,
            operation=completed_operation,
        )
        uploaded = True


def _wait_for_operation(
    gateway: FileSearchGateway,
    operation: UploadOperation,
    timeout_seconds: float,
    poll_interval_seconds: float,
    sleep: Callable[[float], None],
    monotonic: Callable[[], float],
) -> UploadOperation:
    deadline = monotonic() + timeout_seconds
    current = operation

    while not current.done:
        if monotonic() >= deadline:
            raise TimeoutError(
                f"Gemini indexing timed out after {timeout_seconds:g} seconds "
                f"for operation {current.name}."
            )
        sleep(poll_interval_seconds)
        current = gateway.get_upload_operation(current.name)

    return current


def _complete_upload(
    manifest: ManifestState,
    manifest_path: Path,
    article: ManifestArticle,
    store_name: str,
    operation: UploadOperation,
) -> None:
    pending_content_hash = article.pending_upload_content_hash
    if operation.error:
        _clear_pending_upload(article)
        article.upload_status = "failed"
        save_manifest(manifest_path, manifest)
        raise RuntimeError(f"Gemini indexing failed: {operation.error}")
    if not operation.document_name:
        _clear_pending_upload(article)
        article.upload_status = "failed"
        save_manifest(manifest_path, manifest)
        raise RuntimeError("Gemini completed indexing without returning a document name.")
    if not pending_content_hash:
        _clear_pending_upload(article)
        article.upload_status = "failed"
        save_manifest(manifest_path, manifest)
        raise RuntimeError("Manifest is missing the content hash for the pending upload.")

    previous_document_name = article.gemini_document_name
    article.gemini_document_name = operation.document_name
    article.gemini_file_search_store_name = store_name
    article.uploaded_content_hash = pending_content_hash
    article.uploaded_at = datetime.now(UTC).replace(microsecond=0).isoformat()
    article.pending_delete_document_name = (
        previous_document_name
        if previous_document_name and previous_document_name != operation.document_name
        else None
    )
    _clear_pending_upload(article)
    article.upload_status = (
        "cleanup_pending"
        if article.pending_delete_document_name
        else _settled_status(article, store_name)
    )
    save_manifest(manifest_path, manifest)


def _clear_pending_upload(article: ManifestArticle) -> None:
    article.pending_upload_operation_name = None
    article.pending_upload_content_hash = None


def _settled_status(article: ManifestArticle, store_name: str) -> str:
    return "uploaded" if _is_uploaded_version_current(article, store_name) else "pending"


def _is_uploaded_version_current(article: ManifestArticle, store_name: str) -> bool:
    return bool(
        article.gemini_document_name
        and article.gemini_file_search_store_name == store_name
        and article.uploaded_content_hash == article.content_hash
    )
