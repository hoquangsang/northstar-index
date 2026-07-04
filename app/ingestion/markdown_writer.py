from __future__ import annotations

import re
from pathlib import Path
from urllib.parse import urlparse

from markdownify import markdownify as to_markdown

from app.ingestion.html_cleaner import clean_html
from app.schemas import Article, WrittenArticle


def slug_from_article(article: Article) -> str:
    parsed = urlparse(article.html_url)
    slug = parsed.path.rstrip("/").split("/")[-1].strip()
    if slug:
        return _safe_filename(slug)
    return str(article.article_id)


def render_article_markdown(article: Article, base_url: str) -> str:
    cleaned_html = clean_html(article.body, base_url=base_url)
    markdown = to_markdown(cleaned_html, heading_style="ATX")
    markdown = _normalize_markdown(markdown)
    metadata = _render_metadata(article)
    return f"{metadata}\n{markdown}\n\n---\nArticle URL: {article.html_url}\n"


def write_article_markdown(article: Article, output_dir: Path, base_url: str) -> WrittenArticle:
    rendered = preview_article_markdown(article, base_url=base_url)
    return write_rendered_article_markdown(rendered, output_dir=output_dir)


def preview_article_markdown(article: Article, base_url: str) -> WrittenArticle:
    slug = slug_from_article(article)
    markdown = render_article_markdown(article, base_url=base_url)
    return WrittenArticle(article=article, slug=slug, markdown=markdown, path=None)


def write_rendered_article_markdown(
    written_article: WrittenArticle,
    output_dir: Path,
) -> WrittenArticle:
    output_dir.mkdir(parents=True, exist_ok=True)
    path = output_dir / f"{written_article.slug}.md"
    path.write_text(written_article.markdown, encoding="utf-8")
    return written_article.model_copy(update={"path": path})


def _render_metadata(article: Article) -> str:
    updated_at = article.updated_at or ""
    return "\n".join(
        [
            "---",
            f'title: "{_escape_yaml_string(article.title)}"',
            f"article_id: {article.article_id}",
            f'updated_at: "{_escape_yaml_string(updated_at)}"',
            f'source_url: "{_escape_yaml_string(article.html_url)}"',
            "---",
        ]
    )


def _normalize_markdown(markdown: str) -> str:
    normalized = markdown.replace("\r\n", "\n").replace("\r", "\n")
    normalized = normalized.replace("\u00c2\u00a0", " ")
    normalized = normalized.replace("\u00a0", " ")
    normalized = normalized.replace("\u00c2", "")
    normalized = re.sub(r"\n{3,}", "\n\n", normalized)
    return normalized.strip()


def _safe_filename(value: str) -> str:
    safe = re.sub(r'[<>:"/\\|?*\x00-\x1f]', "-", value)
    safe = re.sub(r"\s+", "-", safe)
    safe = re.sub(r"-{2,}", "-", safe)
    return safe.strip("-.") or "article"


def _escape_yaml_string(value: str) -> str:
    return value.replace("\\", "\\\\").replace('"', '\\"')
