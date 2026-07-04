from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path

from app.ingestion.manifest import load_manifest, save_manifest
from app.ingestion.markdown_writer import (
    preview_article_markdown,
    write_rendered_article_markdown,
)
from app.ingestion.zendesk_client import fetch_articles
from app.schemas import ManifestArticle, SyncResponse, WrittenArticle
from app.utils.hashing import sha256_text


@dataclass(frozen=True)
class IngestionResult:
    response: SyncResponse
    article_keys: tuple[str, ...]


def run_sync(
    base_url: str,
    output_dir: Path,
    manifest_path: Path,
    limit: int | None = None,
    dry_run: bool = False,
) -> SyncResponse:
    return run_ingestion(
        base_url=base_url,
        output_dir=output_dir,
        manifest_path=manifest_path,
        limit=limit,
        dry_run=dry_run,
    ).response


def run_ingestion(
    base_url: str,
    output_dir: Path,
    manifest_path: Path,
    limit: int | None = None,
    dry_run: bool = False,
) -> IngestionResult:
    articles = fetch_articles(base_url=base_url, limit=limit)
    manifest = load_manifest(manifest_path)
    written_paths: list[str] = []
    failures: list[str] = []
    article_keys: list[str] = []
    added = 0
    updated = 0
    skipped = 0

    for article in articles:
        try:
            rendered = preview_article_markdown(article, base_url=base_url)
            content_hash = sha256_text(rendered.markdown)
            article_key = str(article.article_id)
            existing = manifest.articles.get(article_key)

            is_added = existing is None
            is_updated = existing is not None and existing.content_hash != content_hash
            if not is_added and not is_updated:
                skipped += 1
                article_keys.append(article_key)
                continue

            output_path = output_dir / f"{rendered.slug}.md"
            if dry_run:
                if is_added:
                    added += 1
                else:
                    updated += 1
                article_keys.append(article_key)
                continue

            written = write_rendered_article_markdown(rendered, output_dir=output_dir)
            if written.path is not None:
                written_paths.append(str(written.path))
                manifest.articles[article_key] = _manifest_article(
                    written,
                    content_hash=content_hash,
                    output_path=output_path,
                    existing=existing,
                )
                if is_added:
                    added += 1
                else:
                    updated += 1
                article_keys.append(article_key)
        except Exception as exc:
            failures.append(f"{article.article_id}: {exc}")

    if not dry_run:
        save_manifest(manifest_path, manifest)

    markdown_written = len(written_paths)
    return IngestionResult(
        response=SyncResponse(
            total_fetched=len(articles),
            markdown_written=markdown_written,
            dry_run=dry_run,
            added=added,
            updated=updated,
            skipped=skipped,
            article_paths=written_paths,
            failed=len(failures),
            failures=failures,
        ),
        article_keys=tuple(article_keys),
    )


def _manifest_article(
    written: WrittenArticle,
    content_hash: str,
    output_path: Path,
    existing: ManifestArticle | None,
) -> ManifestArticle:
    synced_at = datetime.now(UTC).replace(microsecond=0).isoformat()
    local_fields = {
        "article_id": written.article.article_id,
        "slug": written.slug,
        "title": written.article.title,
        "source_url": written.article.html_url,
        "updated_at": written.article.updated_at,
        "content_hash": content_hash,
        "local_path": str(output_path),
        "last_synced_at": synced_at,
    }
    if existing is None:
        return ManifestArticle(
            article_id=written.article.article_id,
            slug=written.slug,
            title=written.article.title,
            source_url=written.article.html_url,
            updated_at=written.article.updated_at,
            content_hash=content_hash,
            local_path=str(output_path),
            last_synced_at=synced_at,
            upload_status="pending",
        )

    if existing.pending_delete_document_name:
        upload_status = "cleanup_pending"
    elif existing.pending_upload_operation_name:
        upload_status = "indexing"
    elif (
        existing.gemini_document_name
        and existing.uploaded_content_hash == content_hash
    ):
        upload_status = "uploaded"
    else:
        upload_status = "pending"

    return existing.model_copy(update={**local_fields, "upload_status": upload_status})
