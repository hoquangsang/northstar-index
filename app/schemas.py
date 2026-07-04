from __future__ import annotations

from enum import StrEnum
from pathlib import Path
from typing import Literal

from pydantic import BaseModel, Field, field_validator


class AnswerLanguage(StrEnum):
    AUTO = "auto"
    ENGLISH = "en"
    VIETNAMESE = "vi"


class HealthResponse(BaseModel):
    status: Literal["ok"]
    app: str
    environment: str


class StatsResponse(BaseModel):
    article_count: int = 0
    manifest_exists: bool = False
    last_run_exists: bool = False
    file_search_store_name: str | None = None
    manifest_article_count: int = 0
    uploaded_article_count: int = 0
    pending_article_count: int = 0
    failed_article_count: int = 0
    last_run_success: bool | None = None
    last_run_finished_at: str | None = None


class SyncRequest(BaseModel):
    limit: int | None = Field(default=None, ge=1)
    dry_run: bool = False
    local_only: bool = False


class SyncResponse(BaseModel):
    total_fetched: int
    markdown_written: int
    dry_run: bool
    added: int = 0
    updated: int = 0
    skipped: int = 0
    article_paths: list[str] = Field(default_factory=list)
    uploaded: int = 0
    upload_skipped: int = 0
    upload_failed: int = 0
    file_search_store_name: str | None = None
    failed: int = 0
    failures: list[str] = Field(default_factory=list)


class LastRunLog(BaseModel):
    started_at: str
    finished_at: str
    success: bool
    limit: int | None = None
    dry_run: bool
    local_only: bool
    summary: SyncResponse | None = None
    error: str | None = None


class AskRequest(BaseModel):
    question: str = Field(min_length=1)
    language: AnswerLanguage = AnswerLanguage.AUTO

    @field_validator("question")
    @classmethod
    def question_must_not_be_blank(cls, value: str) -> str:
        stripped = value.strip()
        if not stripped:
            raise ValueError("Question must not be blank.")
        return stripped


class AskSource(BaseModel):
    title: str
    url: str


class AskResponse(BaseModel):
    status: Literal["answered", "not_found"]
    answer: str
    sources: list[AskSource] = Field(default_factory=list, max_length=3)
    model: str


class Article(BaseModel):
    article_id: int
    title: str
    html_url: str
    body: str
    updated_at: str | None = None


class WrittenArticle(BaseModel):
    article: Article
    slug: str
    markdown: str
    path: Path | None = None


class ManifestArticle(BaseModel):
    article_id: int
    slug: str
    title: str
    source_url: str
    updated_at: str | None = None
    content_hash: str
    local_path: str
    last_synced_at: str
    gemini_document_name: str | None = None
    gemini_file_search_store_name: str | None = None
    uploaded_content_hash: str | None = None
    pending_upload_operation_name: str | None = None
    pending_upload_content_hash: str | None = None
    pending_delete_document_name: str | None = None
    uploaded_at: str | None = None
    upload_status: str | None = None


class ManifestState(BaseModel):
    gemini_file_search_store_name: str | None = None
    articles: dict[str, ManifestArticle] = Field(default_factory=dict)
