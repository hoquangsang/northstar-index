from __future__ import annotations

from typing import Any

import httpx

from app.schemas import Article

ARTICLES_ENDPOINT = "/api/v2/help_center/en-us/articles.json"
YOUTUBE_ARTICLE_ID = 360051014713
PER_PAGE = 100


def _parse_article(raw: dict[str, Any]) -> Article | None:
    if raw.get("draft") is True or not raw.get("body"):
        return None

    article_id = raw.get("id")
    title = raw.get("title") or raw.get("name")
    html_url = raw.get("html_url")
    body = raw.get("body")

    if not isinstance(article_id, int) or not title or not html_url or not body:
        return None

    return Article(
        article_id=article_id,
        title=str(title),
        html_url=str(html_url),
        body=str(body),
        updated_at=str(raw["updated_at"]) if raw.get("updated_at") else None,
    )


def fetch_articles(
    base_url: str,
    limit: int | None = None,
    timeout_seconds: float = 20.0,
) -> list[Article]:
    target = limit or 50
    if target < 1:
        return []

    articles: list[Article] = []
    seen_ids: set[int] = set()
    base = base_url.rstrip("/")

    with httpx.Client(base_url=base, timeout=timeout_seconds, follow_redirects=True) as client:
        youtube = _fetch_single_article(client, YOUTUBE_ARTICLE_ID)
        if youtube is not None:
            articles.append(youtube)
            seen_ids.add(youtube.article_id)

        page = 1
        while len(articles) < target:
            payload = _get_json(
                client,
                ARTICLES_ENDPOINT,
                params={"per_page": PER_PAGE, "page": page},
            )
            raw_articles = payload.get("articles")
            if not isinstance(raw_articles, list) or not raw_articles:
                break

            for raw_article in raw_articles:
                if not isinstance(raw_article, dict):
                    continue
                article = _parse_article(raw_article)
                if article is None or article.article_id in seen_ids:
                    continue
                articles.append(article)
                seen_ids.add(article.article_id)
                if len(articles) >= target:
                    break

            if not payload.get("next_page") or len(raw_articles) < PER_PAGE:
                break
            page += 1

    return articles


def _fetch_single_article(client: httpx.Client, article_id: int) -> Article | None:
    payload = _get_json(client, f"/api/v2/help_center/en-us/articles/{article_id}.json")
    raw_article = payload.get("article")
    if not isinstance(raw_article, dict):
        return None
    return _parse_article(raw_article)


def _get_json(
    client: httpx.Client,
    url: str,
    params: dict[str, int] | None = None,
) -> dict[str, Any]:
    try:
        response = client.get(url, params=params)
        response.raise_for_status()
        payload = response.json()
    except httpx.HTTPError as exc:
        raise RuntimeError(f"Zendesk request failed for {url}: {exc}") from exc
    except ValueError as exc:
        raise RuntimeError(f"Zendesk returned invalid JSON for {url}") from exc

    if not isinstance(payload, dict):
        raise RuntimeError(f"Zendesk returned unexpected payload for {url}")
    return payload
