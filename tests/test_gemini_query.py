from __future__ import annotations

from typing import cast
from unittest.mock import MagicMock

import httpx
import pytest
from app.errors import GeminiQueryError
from app.integrations.gemini_query import GeminiQuestionGateway
from app.schemas import AnswerLanguage
from google import genai
from google.genai import interactions
from google.genai._gaos.lib import compat_errors as interaction_errors


def test_gateway_parses_structured_answer_and_file_citations() -> None:
    response = _interaction_response(
        text=(
            "Setup:\n\n"
            "* Open [Files/Assets](https://app.optisigns.com/assets).\n"
            "* Choose YouTube.\n"
            "    * Use the actual video URL.\n"
            "Verified Article URL:\n"
        ),
        metadata={
            "article_id": "360051014713",
            "source_url": "https://support.optisigns.com/hc/en-us/articles/360051014713",
        },
    )
    client = MagicMock()
    client.interactions.create.return_value = response
    gateway = GeminiQuestionGateway(cast(genai.Client, client))

    result = gateway.query(
        question="How do I add YouTube?",
        store_name="fileSearchStores/test",
        model="gemini-test",
        language=AnswerLanguage.ENGLISH,
    )

    assert result.payload.bullets == [
        "Open Files/Assets.",
        "Choose YouTube. Use the actual video URL.",
    ]
    assert result.citations[0].article_id == "360051014713"
    request = client.interactions.create.call_args.kwargs
    assert request["store"] is False
    assert "response_format" not in request
    assert request["tools"][0]["file_search_store_names"] == [
        "fileSearchStores/test"
    ]
    assert request["generation_config"]["max_output_tokens"] == 512
    assert "Answer in English." in request["system_instruction"]


def test_gateway_rejects_invalid_structured_output() -> None:
    response = _interaction_response(
        text="\n".join(f"* Bullet {index}" for index in range(6)),
        metadata={},
    )
    client = MagicMock()
    client.interactions.create.return_value = response
    gateway = GeminiQuestionGateway(cast(genai.Client, client))

    with pytest.raises(GeminiQueryError, match="violates the response format"):
        gateway.query(
            question="Question",
            store_name="fileSearchStores/test",
            model="gemini-test",
            language=AnswerLanguage.AUTO,
        )


def test_gateway_wraps_interactions_timeout(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    timeout_error = interaction_errors.APITimeoutError(
        httpx.Request("POST", "https://generativelanguage.googleapis.com")
    )
    client = MagicMock()
    gateway = GeminiQuestionGateway(cast(genai.Client, client))

    def raise_timeout(operation: object) -> None:
        raise timeout_error

    monkeypatch.setattr(gateway, "_run_with_retry", raise_timeout)

    with pytest.raises(GeminiQueryError, match="failed after retries"):
        gateway.query(
            question="Question",
            store_name="fileSearchStores/test",
            model="gemini-test",
            language=AnswerLanguage.AUTO,
        )


def _interaction_response(
    text: str,
    metadata: dict[str, str],
) -> interactions.Interaction:
    return interactions.Interaction.model_validate(
        {
            "status": "completed",
            "output_text": text,
            "steps": [
                {
                    "type": "model_output",
                    "content": [
                        {
                            "type": "text",
                            "text": text,
                            "annotations": [
                                {
                                    "type": "file_citation",
                                    "custom_metadata": metadata,
                                }
                            ],
                        }
                    ],
                }
            ],
        }
    )
