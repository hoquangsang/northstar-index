from __future__ import annotations

from app.api.app import create_app
from app.api.routes import chat, sync
from app.errors import GeminiQueryError, KnowledgeBaseNotReadyError
from app.schemas import AnswerLanguage, AskResponse, AskSource, SyncResponse
from fastapi.testclient import TestClient
from pytest import MonkeyPatch


def test_health_endpoint() -> None:
    client = TestClient(create_app())

    response = client.get("/health")

    assert response.status_code == 200
    assert response.json()["status"] == "ok"


def test_sync_endpoint_forwards_local_only(monkeypatch: MonkeyPatch) -> None:
    received: dict[str, object] = {}

    def fake_sync(
        limit: int | None,
        dry_run: bool,
        local_only: bool,
    ) -> SyncResponse:
        received.update(
            limit=limit,
            dry_run=dry_run,
            local_only=local_only,
        )
        return SyncResponse(
            total_fetched=0,
            markdown_written=0,
            dry_run=dry_run,
        )

    monkeypatch.setattr(sync, "run_ingestion_sync", fake_sync)
    client = TestClient(create_app())

    response = client.post(
        "/sync",
        json={"limit": 3, "dry_run": False, "local_only": True},
    )

    assert response.status_code == 200
    assert received == {"limit": 3, "dry_run": False, "local_only": True}


def test_ask_endpoint_forwards_language(monkeypatch: MonkeyPatch) -> None:
    received: dict[str, object] = {}

    def fake_answer(question: str, language: AnswerLanguage) -> AskResponse:
        received.update(question=question, language=language)
        return AskResponse(
            status="answered",
            answer="- Answer",
            sources=[
                AskSource(
                    title="Article",
                    url="https://support.optisigns.com/hc/en-us/articles/1",
                )
            ],
            model="gemini-test",
        )

    monkeypatch.setattr(chat, "answer_question", fake_answer)
    client = TestClient(create_app())

    response = client.post(
        "/ask",
        json={"question": "Câu hỏi", "language": "vi"},
    )

    assert response.status_code == 200
    assert response.json()["status"] == "answered"
    assert received == {
        "question": "Câu hỏi",
        "language": AnswerLanguage.VIETNAMESE,
    }


def test_ask_endpoint_maps_service_errors(monkeypatch: MonkeyPatch) -> None:
    client = TestClient(create_app())

    monkeypatch.setattr(
        chat,
        "answer_question",
        lambda question, language: _raise(KnowledgeBaseNotReadyError("not ready")),
    )
    assert client.post("/ask", json={"question": "Question"}).status_code == 503

    monkeypatch.setattr(
        chat,
        "answer_question",
        lambda question, language: _raise(GeminiQueryError("upstream failed")),
    )
    assert client.post("/ask", json={"question": "Question"}).status_code == 502


def _raise(exception: Exception) -> None:
    raise exception
