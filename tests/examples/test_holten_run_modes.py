# Copyright (c) 2021-2026 Centre national de la recherche scientifique (CNRS)
# Contributor: Jean-Raynald de Dreuzy
# SPDX-License-Identifier: CECILL-2.1

from __future__ import annotations

import sys
from pathlib import Path

from examples.natural.holten import run_holten


def _patch_main_dependencies(monkeypatch, calls: list[str]) -> None:
    monkeypatch.setattr(
        run_holten, "_selected_wells_from_args", lambda *_args: ["67-19"]
    )
    monkeypatch.setattr(
        run_holten, "_ensure_prepared", lambda prepared, *_args: prepared or object()
    )
    monkeypatch.setattr(
        run_holten,
        "_run_prepare_phase",
        lambda prepared, local_4bin_summary, local_4bin_mh_done: (
            calls.append("prepare"),
            local_4bin_summary,
            local_4bin_mh_done,
        )[1:],
    )
    monkeypatch.setattr(
        run_holten,
        "_run_calibration_phase",
        lambda prepared: (calls.append("calibration"), {})[1],
    )
    monkeypatch.setattr(
        run_holten,
        "_run_compare_phase",
        lambda prepared, results_by_well, local_4bin_summary: calls.append("compare"),
    )


def test_run_holten_prepare_only_runs_prepare_phase_only(monkeypatch):
    calls: list[str] = []
    _patch_main_dependencies(monkeypatch, calls)
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "run_holten.py",
            "--config",
            str(Path("dummy.yaml")),
            "--mode",
            "prepare_only",
        ],
    )

    run_holten.main()

    assert calls == ["prepare"]


def test_run_holten_calibration_only_runs_calibration_phase_only(monkeypatch):
    calls: list[str] = []
    _patch_main_dependencies(monkeypatch, calls)
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "run_holten.py",
            "--config",
            str(Path("dummy.yaml")),
            "--mode",
            "calibration_only",
        ],
    )

    run_holten.main()

    assert calls == ["calibration"]


def test_run_holten_compare_only_runs_compare_phase_only(monkeypatch):
    calls: list[str] = []
    _patch_main_dependencies(monkeypatch, calls)
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "run_holten.py",
            "--config",
            str(Path("dummy.yaml")),
            "--mode",
            "compare_only",
        ],
    )

    run_holten.main()

    assert calls == ["compare"]


def test_run_holten_full_runs_all_phases_in_order(monkeypatch):
    calls: list[str] = []
    _patch_main_dependencies(monkeypatch, calls)
    monkeypatch.setattr(
        sys,
        "argv",
        ["run_holten.py", "--config", str(Path("dummy.yaml")), "--mode", "full"],
    )

    run_holten.main()

    assert calls == ["prepare", "calibration", "compare"]
