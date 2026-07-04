from __future__ import annotations

from collections.abc import Callable
from pathlib import Path
from typing import TypeVar

import httpx
from google import genai
from google.genai import errors, types
from tenacity import Retrying, retry_if_exception, stop_after_attempt, wait_exponential

from app.rag.file_search import UploadOperation

_RETRYABLE_API_CODES = frozenset({429, 500, 502, 503, 504})
_ResultT = TypeVar("_ResultT")


class GeminiFileSearchGateway:
    def __init__(self, client: genai.Client) -> None:
        self._client = client

    def get_store(self, name: str) -> str:
        store = self._run_with_retry(lambda: self._client.file_search_stores.get(name=name))
        if not store.name:
            raise RuntimeError("Gemini returned a File Search Store without a name.")
        return store.name

    def create_store(self, display_name: str, embedding_model: str) -> str:
        config = types.CreateFileSearchStoreConfig(
            display_name=display_name,
            embedding_model=embedding_model,
        )
        store = self._run_with_retry(
            lambda: self._client.file_search_stores.create(config=config)
        )
        if not store.name:
            raise RuntimeError("Gemini returned a File Search Store without a name.")
        return store.name

    def upload_document(
        self,
        store_name: str,
        file_path: Path,
        display_name: str,
        metadata: dict[str, str],
    ) -> UploadOperation:
        custom_metadata = [
            types.CustomMetadata(key=key, string_value=value)
            for key, value in metadata.items()
        ]
        config = types.UploadToFileSearchStoreConfig(
            display_name=display_name,
            mime_type="text/markdown",
            custom_metadata=custom_metadata,
        )
        operation = self._run_with_retry(
            lambda: self._client.file_search_stores.upload_to_file_search_store(
                file_search_store_name=store_name,
                file=file_path,
                config=config,
            )
        )
        return _operation_snapshot(operation)

    def get_upload_operation(self, operation_name: str) -> UploadOperation:
        operation = types.UploadToFileSearchStoreOperation.model_validate(
            {"name": operation_name}
        )
        refreshed = self._run_with_retry(lambda: self._client.operations.get(operation))
        return _operation_snapshot(refreshed)

    def delete_document(self, document_name: str) -> None:
        config = types.DeleteDocumentConfig(force=True)
        self._run_with_retry(
            lambda: self._client.file_search_stores.documents.delete(
                name=document_name,
                config=config,
            )
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
        raise RuntimeError("Gemini operation exhausted retries without a result.")


def _operation_snapshot(
    operation: types.UploadToFileSearchStoreOperation,
) -> UploadOperation:
    document_name = operation.response.document_name if operation.response else None
    return UploadOperation(
        name=operation.name or "",
        done=bool(operation.done),
        document_name=document_name,
        error=str(operation.error) if operation.error else None,
    )


def _is_retryable_error(exception: BaseException) -> bool:
    if isinstance(exception, errors.APIError):
        return exception.code in _RETRYABLE_API_CODES
    return isinstance(exception, httpx.TransportError)
