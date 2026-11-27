# Copyright (c) 2021-2026 Centre national de la recherche scientifique (CNRS)
# Contributor: Jean-Raynald de Dreuzy
# SPDX-License-Identifier: CECILL-2.1

"""Accept a Sphinx linkcheck failure only when every failure is a timeout."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any


def _load_records(path: Path) -> list[dict[str, Any]]:
    if not path.is_file():
        raise ValueError(f"linkcheck report does not exist: {path}")

    records: list[dict[str, Any]] = []
    for line_number, line in enumerate(
        path.read_text(encoding="utf-8").splitlines(), 1
    ):
        if not line.strip():
            continue
        try:
            record = json.loads(line)
        except json.JSONDecodeError as error:
            raise ValueError(
                f"invalid JSON on line {line_number} of {path}: {error.msg}"
            ) from error
        if not isinstance(record, dict) or not isinstance(record.get("status"), str):
            raise ValueError(
                f"invalid linkcheck record on line {line_number} of {path}"
            )
        records.append(record)

    if not records:
        raise ValueError(f"linkcheck report is empty: {path}")
    return records


def check_report(path: Path) -> tuple[bool, str]:
    """Return whether a failed linkcheck contains timeouts and no broken link."""
    try:
        records = _load_records(path)
    except ValueError as error:
        return False, str(error)

    broken = [record for record in records if record["status"] == "broken"]
    if broken:
        urls = ", ".join(str(record.get("uri", "<unknown>")) for record in broken)
        return False, f"linkcheck found {len(broken)} broken link(s): {urls}"

    timeouts = [record for record in records if record["status"] == "timeout"]
    if not timeouts:
        return False, "linkcheck failed without reporting a broken link or timeout"

    urls = ", ".join(str(record.get("uri", "<unknown>")) for record in timeouts)
    return True, (
        f"linkcheck found no broken link; allowing {len(timeouts)} transient "
        f"timeout(s): {urls}"
    )


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("report", type=Path, help="Sphinx linkcheck output.json")
    args = parser.parse_args()

    accepted, message = check_report(args.report)
    print(message)
    return 0 if accepted else 1


if __name__ == "__main__":
    raise SystemExit(main())
