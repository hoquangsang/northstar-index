from __future__ import annotations

import json
from pathlib import Path

import pytest
from app.ingestion.pipeline import IngestionResult
from app.schemas import SyncResponse
from app.services import sync_service


@pytest.mark.parametrize(
    ("dry_run", "local_only"),
    [(True, False), (False, True)],
)
def test_non_remote_modes_do_not_build_gemini_client(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    dry_run: bool,
    local_only: bool,
) -> None:
    response = SyncResponse(
        total_fetched=1,
        markdown_written=0,
        dry_run=dry_run,
        skipped=1,
    )
    monkeypatch.setattr(
        sync_service,
        "run_ingestion",
        lambda **kwargs: IngestionResult(response=response, article_keys=("1",)),
    )

    def fail_if_called(*args: object, **kwargs: object) -> None:
        raise AssertionError("Gemini client must not be built")

    monkeypatch.setattr(sync_service, "build_gemini_client", fail_if_called)
    last_run_path = tmp_path / "last_run.json"
    monkeypatch.setattr(sync_service, "LAST_RUN_LOG_PATH", last_run_path)

    result = sync_service.run_ingestion_sync(
        limit=1,
        dry_run=dry_run,
        local_only=local_only,
    )

    assert result == response
    log = json.loads(last_run_path.read_text(encoding="utf-8"))
    assert log["success"] is True
    assert log["summary"]["total_fetched"] == 1


def test_sync_writes_failure_log(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    last_run_path = tmp_path / "last_run.json"
    monkeypatch.setattr(sync_service, "LAST_RUN_LOG_PATH", last_run_path)

    def fail_ingestion(**kwargs: object) -> None:
        raise RuntimeError("network unavailable")

    monkeypatch.setattr(sync_service, "run_ingestion", fail_ingestion)

    with pytest.raises(RuntimeError, match="network unavailable"):
        sync_service.run_ingestion_sync(limit=1, dry_run=True)

    log = json.loads(last_run_path.read_text(encoding="utf-8"))
    assert log["success"] is False
    assert log["error"] == "network unavailable"
