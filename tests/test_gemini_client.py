from __future__ import annotations

import pytest
from app.config import Settings
from app.integrations.gemini_client import build_gemini_client


def test_build_gemini_client_requires_api_key() -> None:
    settings = Settings(_env_file=None, gemini_api_key=None)

    with pytest.raises(RuntimeError, match="GEMINI_API_KEY is required"):
        build_gemini_client(settings)
