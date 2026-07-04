from __future__ import annotations

import json
import time
from pathlib import Path

from pydantic import ValidationError

from app.schemas import ManifestState


def load_manifest(path: Path) -> ManifestState:
    if not path.exists():
        return ManifestState()
    with path.open("r", encoding="utf-8") as file:
        loaded = json.load(file)
    if not isinstance(loaded, dict):
        raise ValueError(f"Manifest must be a JSON object: {path}")
    try:
        return ManifestState.model_validate(loaded)
    except ValidationError as exc:
        raise ValueError(f"Manifest has invalid shape: {path}") from exc


def save_manifest(path: Path, manifest: ManifestState) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = manifest.model_dump(mode="json")
    temporary_path = path.with_suffix(f"{path.suffix}.tmp")
    temporary_path.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    _replace_with_retry(temporary_path, path)


def _replace_with_retry(source: Path, target: Path) -> None:
    for attempt in range(3):
        try:
            source.replace(target)
            return
        except PermissionError:
            if attempt == 2:
                raise
            time.sleep(0.05)
