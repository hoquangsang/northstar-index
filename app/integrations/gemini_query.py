from __future__ import annotations

import re
from collections.abc import Callable
from typing import Literal, TypeVar, cast

import httpx
from google import genai
from google.genai import errors, interactions
from google.genai._gaos.lib import compat_errors as interaction_errors
from pydantic import ValidationError
from tenacity import Retrying, retry_if_exception, stop_after_attempt, wait_exponential

from app.errors import GeminiQueryError
from app.rag.prompts import build_system_prompt
from app.rag.retrieval import (
    FileCitation,
    GeneratedAnswer,
    GeneratedAnswerPayload,
)
from app.schemas import AnswerLanguage

_RETRYABLE_API_CODES = frozenset({429, 500, 502, 503, 504})
_BULLET_PATTERN = re.compile(r"^(?P<indent>\s*)(?:[-*]|\d+[.)])\s+(?P<text>.+)$")
_MARKDOWN_LINK_PATTERN = re.compile(r"\[([^\]]+)]\(https?://[^)]+\)")
_RAW_URL_PATTERN = re.compile(r"https?://\S+", flags=re.IGNORECASE)
_VIETNAMESE_CHARACTERS = frozenset(
    "ăâđêôơưáàảãạấầẩẫậắằẳẵặéèẻẽẹếềểễệíìỉĩị"
    "óòỏõọốồổỗộớờởỡợúùủũụứừửữựýỳỷỹỵ"
)
_ResultT = TypeVar("_ResultT")


class GeminiQuestionGateway:
    def __init__(self, client: genai.Client) -> None:
        self._client = client

    def query(
        self,
        *,
        question: str,
        store_name: str,
        model: str,
        language: AnswerLanguage,
    ) -> GeneratedAnswer:
        response_language = _resolve_response_language(question, language)
        try:
            raw_response = self._run_with_retry(
                lambda: self._client.interactions.create(
                    model=model,
                    input=question,
                    system_instruction=build_system_prompt(language),
                    tools=[
                        {
                            "type": "file_search",
                            "file_search_store_names": [store_name],
                        }
                    ],
                    generation_config={
                        "temperature": 0,
                        "thinking_level": "minimal",
                        "max_output_tokens": 512,
                    },
                    store=False,
                    timeout=120,
                )
            )
        except (
            errors.APIError,
            httpx.TransportError,
            interaction_errors.APIError,
        ) as exc:
            error_name = type(exc).__name__
            detail = str(exc).strip().replace("\n", " ")[:500]
            raise GeminiQueryError(
                f"Gemini query failed after retries ({error_name}): {detail}"
            ) from exc

        response = cast(interactions.Interaction, raw_response)
        if response.status != "completed":
            raise GeminiQueryError(
                f"Gemini query did not complete successfully: {response.status}."
            )

        try:
            payload = _parse_answer(
                _extract_output_text(response),
                response_language,
            )
        except ValidationError as exc:
            raise GeminiQueryError(
                "Gemini returned an answer that violates the response format."
            ) from exc

        return GeneratedAnswer(
            payload=payload,
            citations=tuple(_extract_citations(response)),
        )

    @staticmethod
    def _run_with_retry(operation: Callable[[], _ResultT]) -> _ResultT:
        retrying = Retrying(
            retry=retry_if_exception(_is_retryable_error),
            stop=stop_after_attempt(3),
            wait=wait_exponential(multiplier=2, min=2, max=10),
            reraise=True,
        )
        for attempt in retrying:
            with attempt:
                return operation()
        raise RuntimeError("Gemini query exhausted retries without a result.")


def _extract_output_text(response: interactions.Interaction) -> str:
    if response.output_text:
        return response.output_text

    text_blocks: list[str] = []
    for step in response.steps or []:
        if not isinstance(step, interactions.ModelOutputStep):
            continue
        for content in step.content or []:
            if isinstance(content, interactions.TextContent):
                text_blocks.append(content.text)

    if not text_blocks:
        raise GeminiQueryError("Gemini returned no answer content.")
    return "".join(text_blocks)


def _extract_citations(
    response: interactions.Interaction,
) -> list[FileCitation]:
    citations: list[FileCitation] = []
    for step in response.steps or []:
        if not isinstance(step, interactions.ModelOutputStep):
            continue
        for content in step.content or []:
            if not isinstance(content, interactions.TextContent):
                continue
            for annotation in content.annotations or []:
                if not isinstance(annotation, interactions.FileCitation):
                    continue
                metadata = annotation.custom_metadata or {}
                citations.append(
                    FileCitation(
                        article_id=_metadata_string(metadata, "article_id"),
                        source_url=_metadata_string(metadata, "source_url"),
                    )
                )
    return citations


def _parse_answer(
    text: str,
    language: Literal["en", "vi"],
) -> GeneratedAnswerPayload:
    bullets: list[str] = []
    fallback_lines: list[str] = []

    for line in text.splitlines():
        stripped = line.strip()
        if not stripped or "article url:" in stripped.casefold():
            continue

        match = _BULLET_PATTERN.match(line)
        if match:
            bullet = _sanitize_answer_text(match.group("text"))
            if not bullet:
                continue
            if match.group("indent") and bullets:
                bullets[-1] = f"{bullets[-1]} {bullet}"
            else:
                bullets.append(bullet)
            continue

        if stripped.startswith("#"):
            continue
        if bullets:
            bullets[-1] = f"{bullets[-1]} {_sanitize_answer_text(stripped)}".strip()
        else:
            fallback_lines.append(_sanitize_answer_text(stripped))

    if not bullets:
        fallback = " ".join(line for line in fallback_lines if line).strip()
        if fallback:
            bullets = [fallback]

    return GeneratedAnswerPayload(
        status="answered",
        language=language,
        bullets=bullets,
    )


def _sanitize_answer_text(text: str) -> str:
    without_markdown_links = _MARKDOWN_LINK_PATTERN.sub(r"\1", text)
    return _RAW_URL_PATTERN.sub("", without_markdown_links).strip()


def _resolve_response_language(
    question: str,
    requested: AnswerLanguage,
) -> Literal["en", "vi"]:
    if requested is AnswerLanguage.ENGLISH:
        return "en"
    if requested is AnswerLanguage.VIETNAMESE:
        return "vi"
    lowered = question.casefold()
    return "vi" if any(char in lowered for char in _VIETNAMESE_CHARACTERS) else "en"


def _metadata_string(metadata: dict[str, object], key: str) -> str | None:
    value = metadata.get(key)
    if isinstance(value, str) and value:
        return value
    if isinstance(value, dict):
        nested_value = value.get("string_value")
        if isinstance(nested_value, str) and nested_value:
            return nested_value
    return None


def _is_retryable_error(exception: BaseException) -> bool:
    if isinstance(exception, errors.APIError):
        return exception.code in _RETRYABLE_API_CODES
    if isinstance(exception, interaction_errors.APIConnectionError):
        return True
    if isinstance(exception, interaction_errors.APIStatusError):
        status_code = exception.response.status_code
        return status_code in _RETRYABLE_API_CODES or (
            status_code == 400
            and "too many tool calls" in str(exception).casefold()
        )
    return isinstance(exception, httpx.TransportError)
