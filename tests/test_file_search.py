from __future__ import annotations

from pathlib import Path

from app.ingestion.manifest import load_manifest, save_manifest
from app.rag.file_search import UploadOperation, sync_markdown_files
from app.schemas import ManifestArticle, ManifestState


class FakeFileSearchGateway:
    def __init__(self, upload_error: str | None = None) -> None:
        self.store_name = "fileSearchStores/test-store"
        self.upload_error = upload_error
        self.events: list[str] = []
        self.operations: dict[str, UploadOperation] = {}
        self.upload_count = 0

    def get_store(self, name: str) -> str:
        self.events.append(f"get_store:{name}")
        return name

    def create_store(self, display_name: str, embedding_model: str) -> str:
        self.events.append(f"create_store:{display_name}:{embedding_model}")
        return self.store_name

    def upload_document(
        self,
        store_name: str,
        file_path: Path,
        display_name: str,
        metadata: dict[str, str],
    ) -> UploadOperation:
        self.upload_count += 1
        operation_name = f"operations/upload-{self.upload_count}"
        document_name = f"{store_name}/documents/doc-{self.upload_count}"
        self.events.append(f"upload:{file_path.name}")
        operation = UploadOperation(
            name=operation_name,
            done=True,
            document_name=document_name,
            error=self.upload_error,
        )
        self.operations[operation_name] = operation
        return operation

    def get_upload_operation(self, operation_name: str) -> UploadOperation:
        self.events.append(f"poll:{operation_name}")
        return self.operations[operation_name]

    def delete_document(self, document_name: str) -> None:
        self.events.append(f"delete:{document_name}")


def test_first_upload_creates_store_and_persists_remote_state(tmp_path: Path) -> None:
    manifest_path = _write_manifest(tmp_path, content_hash="hash-a")
    gateway = FakeFileSearchGateway()

    result = sync_markdown_files(
        gateway=gateway,
        manifest_path=manifest_path,
        article_keys=["1"],
        configured_store_name=None,
        store_display_name="Test KB",
    )

    manifest = load_manifest(manifest_path)
    article = manifest.articles["1"]
    assert result.uploaded == 1
    assert result.skipped == 0
    assert result.failed == 0
    assert manifest.gemini_file_search_store_name == gateway.store_name
    assert article.gemini_document_name == f"{gateway.store_name}/documents/doc-1"
    assert article.uploaded_content_hash == "hash-a"
    assert article.upload_status == "uploaded"
    assert article.pending_upload_operation_name is None
    assert gateway.events[0] == "create_store:Test KB:models/gemini-embedding-2"


def test_unchanged_uploaded_article_is_skipped(tmp_path: Path) -> None:
    gateway = FakeFileSearchGateway()
    manifest_path = _write_manifest(
        tmp_path,
        content_hash="hash-a",
        store_name=gateway.store_name,
        document_name=f"{gateway.store_name}/documents/doc-existing",
        uploaded_content_hash="hash-a",
    )

    result = sync_markdown_files(
        gateway=gateway,
        manifest_path=manifest_path,
        article_keys=["1"],
        configured_store_name=None,
        store_display_name="Test KB",
    )

    assert result.uploaded == 0
    assert result.skipped == 1
    assert result.failed == 0
    assert not any(event.startswith("upload:") for event in gateway.events)


def test_changed_article_uploads_new_document_before_deleting_old(
    tmp_path: Path,
) -> None:
    gateway = FakeFileSearchGateway()
    old_document = f"{gateway.store_name}/documents/doc-old"
    manifest_path = _write_manifest(
        tmp_path,
        content_hash="hash-new",
        store_name=gateway.store_name,
        document_name=old_document,
        uploaded_content_hash="hash-old",
    )

    result = sync_markdown_files(
        gateway=gateway,
        manifest_path=manifest_path,
        article_keys=["1"],
        configured_store_name=None,
        store_display_name="Test KB",
    )

    article = load_manifest(manifest_path).articles["1"]
    upload_index = gateway.events.index("upload:1-Sample.md")
    delete_index = gateway.events.index(f"delete:{old_document}")
    assert upload_index < delete_index
    assert result.uploaded == 1
    assert article.gemini_document_name != old_document
    assert article.uploaded_content_hash == "hash-new"
    assert article.pending_delete_document_name is None
    assert article.upload_status == "uploaded"


def test_configured_store_overrides_manifest_store(tmp_path: Path) -> None:
    gateway = FakeFileSearchGateway()
    old_store = "fileSearchStores/old-store"
    new_store = "fileSearchStores/new-store"
    old_document = f"{old_store}/documents/doc-old"
    manifest_path = _write_manifest(
        tmp_path,
        content_hash="hash-a",
        store_name=old_store,
        document_name=old_document,
        uploaded_content_hash="hash-a",
    )

    result = sync_markdown_files(
        gateway=gateway,
        manifest_path=manifest_path,
        article_keys=["1"],
        configured_store_name=new_store,
        store_display_name="Test KB",
    )

    manifest = load_manifest(manifest_path)
    article = manifest.articles["1"]
    assert result.store_name == new_store
    assert result.uploaded == 1
    assert manifest.gemini_file_search_store_name == new_store
    assert article.gemini_file_search_store_name == new_store
    assert f"delete:{old_document}" in gateway.events


def test_indexing_failure_keeps_old_document_for_retry(tmp_path: Path) -> None:
    gateway = FakeFileSearchGateway(upload_error="indexing unavailable")
    old_document = f"{gateway.store_name}/documents/doc-old"
    manifest_path = _write_manifest(
        tmp_path,
        content_hash="hash-new",
        store_name=gateway.store_name,
        document_name=old_document,
        uploaded_content_hash="hash-old",
    )

    result = sync_markdown_files(
        gateway=gateway,
        manifest_path=manifest_path,
        article_keys=["1"],
        configured_store_name=None,
        store_display_name="Test KB",
    )

    article = load_manifest(manifest_path).articles["1"]
    assert result.failed == 1
    assert article.gemini_document_name == old_document
    assert article.uploaded_content_hash == "hash-old"
    assert article.upload_status == "failed"
    assert not any(event.startswith("delete:") for event in gateway.events)


def test_pending_cleanup_is_resumed_without_reuploading(tmp_path: Path) -> None:
    gateway = FakeFileSearchGateway()
    old_document = f"{gateway.store_name}/documents/doc-old"
    manifest_path = _write_manifest(
        tmp_path,
        content_hash="hash-a",
        store_name=gateway.store_name,
        document_name=f"{gateway.store_name}/documents/doc-new",
        uploaded_content_hash="hash-a",
        pending_delete_document_name=old_document,
    )

    result = sync_markdown_files(
        gateway=gateway,
        manifest_path=manifest_path,
        article_keys=["1"],
        configured_store_name=None,
        store_display_name="Test KB",
    )

    article = load_manifest(manifest_path).articles["1"]
    assert gateway.events.index(f"delete:{old_document}") > 0
    assert result.uploaded == 0
    assert result.skipped == 1
    assert article.pending_delete_document_name is None
    assert article.upload_status == "uploaded"


def test_pending_upload_operation_is_resumed_without_starting_another(
    tmp_path: Path,
) -> None:
    gateway = FakeFileSearchGateway()
    operation_name = "operations/existing-upload"
    gateway.operations[operation_name] = UploadOperation(
        name=operation_name,
        done=True,
        document_name=f"{gateway.store_name}/documents/doc-resumed",
    )
    manifest_path = _write_manifest(
        tmp_path,
        content_hash="hash-a",
        store_name=gateway.store_name,
        pending_upload_operation_name=operation_name,
        pending_upload_content_hash="hash-a",
    )

    result = sync_markdown_files(
        gateway=gateway,
        manifest_path=manifest_path,
        article_keys=["1"],
        configured_store_name=None,
        store_display_name="Test KB",
    )

    article = load_manifest(manifest_path).articles["1"]
    assert result.uploaded == 1
    assert gateway.upload_count == 0
    assert f"poll:{operation_name}" in gateway.events
    assert article.gemini_document_name == f"{gateway.store_name}/documents/doc-resumed"
    assert article.pending_upload_operation_name is None
    assert article.upload_status == "uploaded"


def _write_manifest(
    tmp_path: Path,
    content_hash: str,
    store_name: str | None = None,
    document_name: str | None = None,
    uploaded_content_hash: str | None = None,
    pending_delete_document_name: str | None = None,
    pending_upload_operation_name: str | None = None,
    pending_upload_content_hash: str | None = None,
) -> Path:
    article_path = tmp_path / "1-Sample.md"
    article_path.write_text("# Sample\n", encoding="utf-8")
    manifest_path = tmp_path / "manifest.json"
    save_manifest(
        manifest_path,
        ManifestState(
            gemini_file_search_store_name=store_name,
            articles={
                "1": ManifestArticle(
                    article_id=1,
                    slug="1-Sample",
                    title="Sample",
                    source_url="https://support.optisigns.com/hc/en-us/articles/1-Sample",
                    content_hash=content_hash,
                    local_path=str(article_path),
                    last_synced_at="2026-01-01T00:00:00+00:00",
                    gemini_document_name=document_name,
                    gemini_file_search_store_name=store_name,
                    uploaded_content_hash=uploaded_content_hash,
                    pending_delete_document_name=pending_delete_document_name,
                    pending_upload_operation_name=pending_upload_operation_name,
                    pending_upload_content_hash=pending_upload_content_hash,
                )
            },
        ),
    )
    return manifest_path
