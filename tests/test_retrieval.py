from __future__ import annotations

from datetime import UTC, datetime

import pytest
from app.rag.retrieval import (
    FileCitation,
    GeneratedAnswer,
    GeneratedAnswerPayload,
    retrieve_answer,
)
from app.schemas import AnswerLanguage, ManifestArticle, ManifestState
from pydantic import ValidationError

STORE_NAME = "fileSearchStores/test-store"


class FakeQuestionGateway:
    def __init__(self, answer: GeneratedAnswer) -> None:
        self.answer = answer
        self.received_language: AnswerLanguage | None = None

    def query(
        self,
        *,
        question: str,
        store_name: str,
        model: str,
        language: AnswerLanguage,
    ) -> GeneratedAnswer:
        self.received_language = language
        return self.answer


def test_retrieve_answer_returns_bullets_and_verified_sources() -> None:
    manifest = _manifest_with_articles(4)
    generated = GeneratedAnswer(
        payload=GeneratedAnswerPayload(
            status="answered",
            language="en",
            bullets=["Open Files/Assets.", "Choose the YouTube app."],
        ),
        citations=(
            FileCitation(article_id="1", source_url=_source_url(1)),
            FileCitation(article_id="1", source_url=_source_url(1)),
            FileCitation(article_id="2", source_url=_source_url(2)),
            FileCitation(article_id="3", source_url=_source_url(3)),
            FileCitation(article_id="4", source_url=_source_url(4)),
        ),
    )
    gateway = FakeQuestionGateway(generated)

    response = retrieve_answer(
        gateway=gateway,
        manifest=manifest,
        question="How do I add YouTube?",
        store_name=STORE_NAME,
        model="gemini-test",
        language=AnswerLanguage.AUTO,
    )

    assert response.status == "answered"
    assert response.answer == "- Open Files/Assets.\n- Choose the YouTube app."
    assert [source.url for source in response.sources] == [
        _source_url(1),
        _source_url(2),
        _source_url(3),
    ]
    assert gateway.received_language is AnswerLanguage.AUTO


@pytest.mark.parametrize(
    "citations",
    [
        (),
        (FileCitation(article_id="999", source_url="https://example.com/fake"),),
        (
            FileCitation(
                article_id="1",
                source_url="https://support.optisigns.com/hc/en-us/articles/2-Article",
            ),
        ),
    ],
)
def test_retrieve_answer_requires_a_valid_citation(
    citations: tuple[FileCitation, ...],
) -> None:
    generated = GeneratedAnswer(
        payload=GeneratedAnswerPayload(
            status="answered",
            language="en",
            bullets=["An unsupported answer."],
        ),
        citations=citations,
    )

    response = retrieve_answer(
        gateway=FakeQuestionGateway(generated),
        manifest=_manifest_with_articles(1),
        question="Unsupported question",
        store_name=STORE_NAME,
        model="gemini-test",
        language=AnswerLanguage.AUTO,
    )

    assert response.status == "not_found"
    assert response.sources == []


def test_retrieve_answer_uses_forced_language_for_not_found() -> None:
    generated = GeneratedAnswer(
        payload=GeneratedAnswerPayload(
            status="not_found",
            language="en",
            bullets=[],
        ),
        citations=(),
    )

    response = retrieve_answer(
        gateway=FakeQuestionGateway(generated),
        manifest=_manifest_with_articles(1),
        question="Không có trong tài liệu",
        store_name=STORE_NAME,
        model="gemini-test",
        language=AnswerLanguage.VIETNAMESE,
    )

    assert response.status == "not_found"
    assert response.answer.startswith("Tôi không tìm thấy")


def test_generated_answer_payload_enforces_five_bullets_and_no_urls() -> None:
    with pytest.raises(ValidationError, match="at most 5 items"):
        GeneratedAnswerPayload(
            status="answered",
            language="en",
            bullets=["one", "two", "three", "four", "five", "six"],
        )

    with pytest.raises(ValidationError, match="must not contain URLs"):
        GeneratedAnswerPayload(
            status="answered",
            language="en",
            bullets=["Read https://example.com"],
        )


def _manifest_with_articles(count: int) -> ManifestState:
    return ManifestState(
        gemini_file_search_store_name=STORE_NAME,
        articles={
            str(index): _manifest_article(index)
            for index in range(1, count + 1)
        },
    )


def _manifest_article(index: int) -> ManifestArticle:
    now = datetime.now(UTC).replace(microsecond=0).isoformat()
    content_hash = f"hash-{index}"
    return ManifestArticle(
        article_id=index,
        slug=f"article-{index}",
        title=f"Article {index}",
        source_url=_source_url(index),
        content_hash=content_hash,
        local_path=f"data/articles/article-{index}.md",
        last_synced_at=now,
        gemini_document_name=f"{STORE_NAME}/documents/{index}",
        gemini_file_search_store_name=STORE_NAME,
        uploaded_content_hash=content_hash,
        uploaded_at=now,
        upload_status="uploaded",
    )


def _source_url(index: int) -> str:
    return f"https://support.optisigns.com/hc/en-us/articles/{index}-Article"
