from __future__ import annotations

from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parents[2]
DATA_DIR = ROOT_DIR / "data"
ARTICLES_DIR = DATA_DIR / "articles"
LOGS_DIR = ROOT_DIR / "logs"
SCREENSHOTS_DIR = ROOT_DIR / "screenshots"
MANIFEST_PATH = DATA_DIR / "manifest.json"
LAST_RUN_LOG_PATH = LOGS_DIR / "last_run.json"


def ensure_runtime_dirs() -> None:
    """Create runtime directories used by sync, logs, and screenshots."""
    for path in (ARTICLES_DIR, LOGS_DIR, SCREENSHOTS_DIR):
        path.mkdir(parents=True, exist_ok=True)
