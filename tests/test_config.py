from __future__ import annotations

from app.config import Settings


def test_settings_defaults() -> None:
    settings = Settings(_env_file=None)

    assert settings.app_name == "Northstar Index"
    assert settings.app_port == 8000
    assert str(settings.support_base_url) == "https://support.optisigns.com/"
    assert settings.gemini_model == "gemini-3.1-flash-lite"
    assert settings.gemini_file_search_store_display_name == "Northstar OptiSigns KB"
