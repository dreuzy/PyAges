# Copyright (c) 2021-2026 Centre national de la recherche scientifique (CNRS)
# Contributor: Jean-Raynald de Dreuzy
# SPDX-License-Identifier: CECILL-2.1

from __future__ import annotations

import json
from pathlib import Path

import pytest

from scripts.maintenance.check_linkcheck_results import check_report


def _write_report(path: Path, *records: dict[str, object]) -> None:
    path.write_text(
        "".join(f"{json.dumps(record)}\n" for record in records), encoding="utf-8"
    )


def test_accepts_timeout_only_failure(tmp_path: Path) -> None:
    report = tmp_path / "output.json"
    _write_report(
        report,
        {"status": "working", "uri": "https://example.test/ok"},
        {"status": "timeout", "uri": "https://example.test/slow"},
    )

    accepted, message = check_report(report)

    assert accepted is True
    assert "1 transient timeout" in message
    assert "https://example.test/slow" in message


@pytest.mark.parametrize(
    "records",
    [
        ({"status": "broken", "uri": "https://example.test/missing"},),
        (
            {"status": "timeout", "uri": "https://example.test/slow"},
            {"status": "broken", "uri": "https://example.test/missing"},
        ),
    ],
)
def test_rejects_every_report_with_a_broken_link(
    tmp_path: Path, records: tuple[dict[str, object], ...]
) -> None:
    report = tmp_path / "output.json"
    _write_report(report, *records)

    accepted, message = check_report(report)

    assert accepted is False
    assert "broken link" in message


@pytest.mark.parametrize("content", ["", "not JSON\n", '{"uri": "missing status"}\n'])
def test_rejects_an_unusable_report(tmp_path: Path, content: str) -> None:
    report = tmp_path / "output.json"
    report.write_text(content, encoding="utf-8")

    accepted, _ = check_report(report)

    assert accepted is False


def test_rejects_a_failed_run_without_a_failure_record(tmp_path: Path) -> None:
    report = tmp_path / "output.json"
    _write_report(report, {"status": "working", "uri": "https://example.test/ok"})

    accepted, message = check_report(report)

    assert accepted is False
    assert "without reporting" in message
