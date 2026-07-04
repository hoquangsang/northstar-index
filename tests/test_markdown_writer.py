from __future__ import annotations

from app.ingestion.markdown_writer import render_article_markdown, slug_from_article
from app.schemas import Article


def test_slug_from_article_uses_html_url_tail() -> None:
    article = Article(
        article_id=123,
        title="Test",
        html_url="https://support.optisigns.com/hc/en-us/articles/123-Test-Article",
        body="<p>Hello</p>",
    )

    assert slug_from_article(article) == "123-Test-Article"


def test_slug_from_article_falls_back_to_article_id() -> None:
    article = Article(
        article_id=123,
        title="Test",
        html_url="https://support.optisigns.com/",
        body="<p>Hello</p>",
    )

    assert slug_from_article(article) == "123"


def test_render_article_markdown_includes_metadata_and_article_url() -> None:
    article = Article(
        article_id=123,
        title='YouTube "Video"',
        html_url="https://support.optisigns.com/hc/en-us/articles/123-Test",
        body="<h1>Hello</h1><p>Body</p>",
        updated_at="2026-01-01T00:00:00Z",
    )

    markdown = render_article_markdown(article, base_url="https://support.optisigns.com")

    assert 'title: "YouTube \\"Video\\""' in markdown
    assert "article_id: 123" in markdown
    assert 'source_url: "https://support.optisigns.com/hc/en-us/articles/123-Test"' in markdown
    assert "# Hello" in markdown
    assert markdown.endswith(
        "---\nArticle URL: https://support.optisigns.com/hc/en-us/articles/123-Test\n"
    )
