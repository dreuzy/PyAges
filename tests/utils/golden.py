"""Helpers for reading/writing golden JSON files in tests."""

from __future__ import annotations

import json
import os
from pathlib import Path
import tempfile
import time
from typing import Type


def load_golden(path: Path) -> dict:
    path.parent.mkdir(parents=True, exist_ok=True)
    if not path.exists():
        return {}
    return json.loads(path.read_text(encoding="utf-8"))


def load_golden_or_raise(
    path: Path,
    exc_type: Type[Exception],
    message_prefix: str = "Golden file is not valid JSON",
) -> dict:
    try:
        return load_golden(path)
    except json.JSONDecodeError as exc:
        raise exc_type(f"{message_prefix}: {path}\n{exc}") from exc


def save_golden(path: Path, store: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = json.dumps(store, indent=2, sort_keys=True) + "\n"
    for attempt in range(5):
        tmp_path = None
        try:
            with tempfile.NamedTemporaryFile(
                "w",
                encoding="utf-8",
                delete=False,
                dir=path.parent,
                suffix=".tmp",
            ) as handle:
                handle.write(payload)
                tmp_path = Path(handle.name)
            os.replace(tmp_path, path)
            return
        except PermissionError:
            if tmp_path and tmp_path.exists():
                try:
                    tmp_path.unlink()
                except OSError:
                    pass
            if attempt == 4:
                raise
            time.sleep(0.1 * (attempt + 1))
