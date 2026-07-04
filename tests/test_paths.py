from __future__ import annotations

from app.utils import paths


def test_runtime_paths_are_under_repo_root() -> None:
    assert paths.DATA_DIR.parent == paths.ROOT_DIR
    assert paths.ARTICLES_DIR.parent == paths.DATA_DIR
    assert paths.LOGS_DIR.parent == paths.ROOT_DIR
    assert paths.SCREENSHOTS_DIR.parent == paths.ROOT_DIR
