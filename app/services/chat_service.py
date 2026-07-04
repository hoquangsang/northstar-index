from __future__ import annotations

from app.config import get_settings
from app.errors import KnowledgeBaseNotReadyError
from app.ingestion.manifest import load_manifest
from app.integrations.gemini_client import build_gemini_client
from app.integrations.gemini_query import GeminiQuestionGateway
from app.rag.retrieval import retrieve_answer
from app.schemas import AnswerLanguage, AskResponse, ManifestArticle
from app.utils.paths import MANIFEST_PATH


def answer_question(
    question: str,
    language: AnswerLanguage = AnswerLanguage.AUTO,
) -> AskResponse:
    settings = get_settings()
    if not settings.gemini_api_key:
        raise KnowledgeBaseNotReadyError(
            "GEMINI_API_KEY is required for grounded questions."
        )

    manifest = load_manifest(MANIFEST_PATH)
    store_name = (
        settings.gemini_file_search_store_name
        or manifest.gemini_file_search_store_name
    )
    if not store_name:
        raise KnowledgeBaseNotReadyError(
            "Gemini File Search Store is not configured. Run sync first."
        )
    if not any(
        _is_current_remote_article(article, store_name)
        for article in manifest.articles.values()
    ):
        raise KnowledgeBaseNotReadyError(
            "No current articles are uploaded to the selected File Search Store. "
            "Run sync first."
        )

    gateway = GeminiQuestionGateway(build_gemini_client(settings))
    return retrieve_answer(
        gateway=gateway,
        manifest=manifest,
        question=question,
        store_name=store_name,
        model=settings.gemini_model,
        language=language,
    )


def _is_current_remote_article(
    article: ManifestArticle,
    store_name: str,
) -> bool:
    return bool(
        article.gemini_document_name
        and article.gemini_file_search_store_name == store_name
        and article.uploaded_content_hash == article.content_hash
    )
