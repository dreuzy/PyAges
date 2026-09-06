# Copyright (c) 2021-2026 Centre national de la recherche scientifique (CNRS)
# Contributor: Jean-Raynald de Dreuzy
# SPDX-License-Identifier: CECILL-2.1

from subprocess import CompletedProcess

from scripts.maintenance import check_dev


def test_profiles_keep_slow_checks_out_of_quick_feedback() -> None:
    quick = check_dev.steps_for("quick")
    full = check_dev.steps_for("full")

    assert full[: len(quick)] == quick
    assert [step.label for step in full[len(quick) :]] == [
        "Generated test inventory",
        "Standard tests",
        "Strict documentation build",
    ]
    assert all("pytest" not in step.command for step in quick)


def test_checks_stop_at_the_first_failure(monkeypatch) -> None:
    calls: list[tuple[str, ...]] = []

    def fake_run(command, *, cwd, check):
        calls.append(command)
        return CompletedProcess(command, 7 if len(calls) == 2 else 0)

    monkeypatch.setattr(check_dev.subprocess, "run", fake_run)
    steps = (
        check_dev.CheckStep("first", ("first",)),
        check_dev.CheckStep("second", ("second",)),
        check_dev.CheckStep("third", ("third",)),
    )

    assert check_dev.run_checks(steps) == 7
    assert calls == [("first",), ("second",)]


def test_main_runs_the_selected_profile(monkeypatch) -> None:
    selected = None

    def fake_run_checks(steps):
        nonlocal selected
        selected = steps
        return 0

    monkeypatch.setattr(check_dev, "run_checks", fake_run_checks)

    assert check_dev.main(["quick"]) == 0
    assert selected == check_dev.QUICK_STEPS
