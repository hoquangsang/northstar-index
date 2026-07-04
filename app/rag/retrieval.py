from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Literal, Protocol, Self

from pydantic import BaseModel, Field, model_validator

from app.schemas import (
    AnswerLanguage,
    AskResponse,
    AskSource,
    ManifestArticle,
    ManifestState,
)

_URL_PATTERN = re.compile(r"https?://", flags=re.IGNORECASE)


class GeneratedAnswerPayload(BaseModel):
    status: Literal["answered", "not_found"]
    language: Literal["en", "vi"]
    bullets: list[str] = Field(default_factory=list, max_length=5)

    @model_validator(mode="after")
    def validate_answer_shape(self) -> Self:
        cleaned_bullets = [bullet.strip() for bullet in self.bullets if bullet.strip()]
        if any(_URL_PATTERN.search(bullet) for bullet in cleaned_bullets):
            raise ValueError("Answer bullets must not contain URLs.")
        if self.status == "answered" and not cleaned_bullets:
            raise ValueError("An answered response requires at least one bullet.")
        if self.status == "not_found" and cleaned_bullets:
            raise ValueError("A not_found response must not contain bullets.")
        self.bullets = cleaned_bullets
        return self


@dataclass(frozen=True)
class FileCitation:
    article_id: str | None = None
    source_url: str | None = None


@dataclass(frozen=True)
class GeneratedAnswer:
    payload: GeneratedAnswerPayload
    citations: tuple[FileCitation, ...]


class QuestionGateway(Protocol):
    def query(
        self,
        *,
        question: str,
        store_name: str,
        model: str,
        language: AnswerLanguage,
    ) -> GeneratedAnswer: ...


def retrieve_answer(
    *,
    gateway: QuestionGateway,
    manifest: ManifestState,
    question: str,
    store_name: str,
    model: str,
    language: AnswerLanguage,
) -> AskResponse:
    generated = gateway.query(
        question=question,
        store_name=store_name,
        model=model,
        language=language,
    )
    response_language = _response_language(language, generated.payload.language)
    sources = _verified_sources(
        generated.citations,
        manifest.articles,
        store_name,
    )

    if generated.payload.status == "not_found" or not sources:
        return AskResponse(
            status="not_found",
            answer=_not_found_message(response_language),
            sources=[],
            model=model,
        )

    answer = "\n".join(f"- {bullet}" for bullet in generated.payload.bullets)
    return AskResponse(
        status="answered",
        answer=answer,
        sources=sources,
        model=model,
    )


def _verified_sources(
    citations: tuple[FileCitation, ...],
    articles: dict[str, ManifestArticle],
    store_name: str,
) -> list[AskSource]:
    sources: list[AskSource] = []
    seen_urls: set[str] = set()
    articles_by_url = {article.source_url: article for article in articles.values()}

    for citation in citations:
        article = (
            articles.get(citation.article_id)
            if citation.article_id is not None
            else None
        )
        if article is None and citation.source_url is not None:
            article = articles_by_url.get(citation.source_url)
        if article is None or not _is_current_remote_article(article, store_name):
            continue
        if citation.article_id is not None and citation.article_id != str(article.article_id):
            continue
        if citation.source_url is not None and citation.source_url != article.source_url:
            continue
        if article.source_url in seen_urls:
            continue

        sources.append(AskSource(title=article.title, url=article.source_url))
        seen_urls.add(article.source_url)
        if len(sources) == 3:
            break

    return sources


def _is_current_remote_article(article: ManifestArticle, store_name: str) -> bool:
    return bool(
        article.gemini_document_name
        and article.gemini_file_search_store_name == store_name
        and article.uploaded_content_hash == article.content_hash
    )


def _response_language(
    requested: AnswerLanguage,
    generated: Literal["en", "vi"],
) -> Literal["en", "vi"]:
    if requested is AnswerLanguage.ENGLISH:
        return "en"
    if requested is AnswerLanguage.VIETNAMESE:
        return "vi"
    return generated


def _not_found_message(language: Literal["en", "vi"]) -> str:
    if language == "vi":
        return "Tôi không tìm thấy thông tin này trong tài liệu OptiSigns hiện có."
    return "I could not find this information in the available OptiSigns documentation."
