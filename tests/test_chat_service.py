from __future__ import annotations

from datetime import UTC, datetime

import pytest
from app.config import Settings
from app.errors import KnowledgeBaseNotReadyError
from app.schemas import (
    AnswerLanguage,
    AskResponse,
    ManifestArticle,
    ManifestState,
)
from app.services import chat_service

MANIFEST_STORE = "fileSearchStores/manifest-store"
ENV_STORE = "fileSearchStores/env-store"


def test_answer_question_prefers_configured_store(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    settings = Settings(
        _env_file=None,
        gemini_api_key="test-key",
        gemini_file_search_store_name=ENV_STORE,
        gemini_model="gemini-test",
    )
    manifest = _manifest(ENV_STORE)
    received: dict[str, object] = {}

    monkeypatch.setattr(chat_service, "get_settings", lambda: settings)
    monkeypatch.setattr(chat_service, "load_manifest", lambda path: manifest)
    monkeypatch.setattr(chat_service, "build_gemini_client", lambda value: object())
    monkeypatch.setattr(
        chat_service,
        "GeminiQuestionGateway",
        lambda client: object(),
    )

    def fake_retrieve_answer(**kwargs: object) -> AskResponse:
        received.update(kwargs)
        return AskResponse(
            status="not_found",
            answer="Not found.",
            model="gemini-test",
        )

    monkeypatch.setattr(chat_service, "retrieve_answer", fake_retrieve_answer)

    response = chat_service.answer_question(
        "Question",
        AnswerLanguage.ENGLISH,
    )

    assert response.status == "not_found"
    assert received["store_name"] == ENV_STORE
    assert received["language"] is AnswerLanguage.ENGLISH


def test_answer_question_falls_back_to_manifest_store(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    settings = Settings(
        _env_file=None,
        gemini_api_key="test-key",
        gemini_file_search_store_name=None,
    )
    manifest = _manifest(MANIFEST_STORE)
    received: dict[str, object] = {}

    monkeypatch.setattr(chat_service, "get_settings", lambda: settings)
    monkeypatch.setattr(chat_service, "load_manifest", lambda path: manifest)
    monkeypatch.setattr(chat_service, "build_gemini_client", lambda value: object())
    monkeypatch.setattr(
        chat_service,
        "GeminiQuestionGateway",
        lambda client: object(),
    )

    def fake_retrieve_answer(**kwargs: object) -> AskResponse:
        received.update(kwargs)
        return AskResponse(
            status="not_found",
            answer="Not found.",
            model=settings.gemini_model,
        )

    monkeypatch.setattr(chat_service, "retrieve_answer", fake_retrieve_answer)

    chat_service.answer_question("Question")

    assert received["store_name"] == MANIFEST_STORE


def test_answer_question_requires_api_key(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    settings = Settings(_env_file=None, gemini_api_key=None)
    monkeypatch.setattr(chat_service, "get_settings", lambda: settings)

    with pytest.raises(KnowledgeBaseNotReadyError, match="GEMINI_API_KEY"):
        chat_service.answer_question("Question")


def test_answer_question_requires_uploaded_articles(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    settings = Settings(
        _env_file=None,
        gemini_api_key="test-key",
        gemini_file_search_store_name=ENV_STORE,
    )
    monkeypatch.setattr(chat_service, "get_settings", lambda: settings)
    monkeypatch.setattr(
        chat_service,
        "load_manifest",
        lambda path: ManifestState(gemini_file_search_store_name=ENV_STORE),
    )

    with pytest.raises(KnowledgeBaseNotReadyError, match="No current articles"):
        chat_service.answer_question("Question")


def _manifest(store_name: str) -> ManifestState:
    now = datetime.now(UTC).replace(microsecond=0).isoformat()
    article = ManifestArticle(
        article_id=1,
        slug="sample",
        title="Sample",
        source_url="https://support.optisigns.com/hc/en-us/articles/1-Sample",
        content_hash="hash",
        local_path="data/articles/sample.md",
        last_synced_at=now,
        gemini_document_name=f"{store_name}/documents/1",
        gemini_file_search_store_name=store_name,
        uploaded_content_hash="hash",
        uploaded_at=now,
        upload_status="uploaded",
    )
    return ManifestState(
        gemini_file_search_store_name=store_name,
        articles={"1": article},
    )
