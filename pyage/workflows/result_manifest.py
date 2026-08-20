"""Versioned manifest for public workflow result directories."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Mapping

from pyage import __version__

RESULT_SCHEMA_VERSION = 1


def write_result_manifest(
    directory: str | Path,
    *,
    workflow: str,
    config_name: str,
    details: Mapping[str, Any] | None = None,
) -> Path:
    """Write deterministic metadata describing one public result directory."""
    output_directory = Path(directory)
    output_directory.mkdir(parents=True, exist_ok=True)
    payload: dict[str, Any] = {
        "schema_version": RESULT_SCHEMA_VERSION,
        "pyage_version": __version__,
        "workflow": workflow,
        "config_name": config_name,
    }
    if details:
        payload["details"] = dict(details)
    target = output_directory / "result_manifest.json"
    target.write_text(
        json.dumps(payload, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    return target


__all__ = ["RESULT_SCHEMA_VERSION", "write_result_manifest"]
