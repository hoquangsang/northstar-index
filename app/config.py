from __future__ import annotations

import os
from functools import lru_cache

from pydantic import Field, HttpUrl, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    app_env: str = "local"
    app_name: str = "Northstar Index"
    app_host: str = "0.0.0.0"
    app_port: int = 8000

    gemini_api_key: str | None = Field(default=None, repr=False)
    gemini_file_search_store_name: str | None = None
    gemini_file_search_store_display_name: str = "Northstar OptiSigns KB"
    gemini_model: str = "gemini-3.1-flash-lite"

    support_base_url: HttpUrl = HttpUrl("https://support.optisigns.com")

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    @model_validator(mode="after")
    def use_render_port_when_app_port_is_unset(self) -> Settings:
        if "APP_PORT" not in os.environ and (render_port := os.getenv("PORT")):
            self.app_port = int(render_port)
        return self


@lru_cache
def get_settings() -> Settings:
    return Settings()
