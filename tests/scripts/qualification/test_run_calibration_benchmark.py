# Copyright (c) 2021-2026 Centre national de la recherche scientifique (CNRS)
# Contributor: Jean-Raynald de Dreuzy
# SPDX-License-Identifier: CECILL-2.1

"""Contract tests for the lightweight calibration benchmark orchestration."""

from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace

from scripts.qualification import run_calibration_benchmark as benchmark


class _Timer:
    def __init__(self) -> None:
        self.initialized_with: int | None = None
        self.actualizations = 0

    def initialize(self, count: int) -> None:
        self.initialized_with = count

    def actualize(self) -> None:
        self.actualizations += 1


class _Calibration:
    def __init__(self, method: str) -> None:
        self.method = method
        self.analysis_calls = 0
        self.problem = SimpleNamespace(analyze=self._analyze)

    def _analyze(self) -> None:
        self.analysis_calls += 1

    def write_parameters(self, unused_path: str | Path) -> None:
        pass

    def write_results(self, unused_path: str | Path) -> None:
        pass


def test_benchmark_pairs_both_methods_with_the_same_target(
    monkeypatch, tmp_path: Path
) -> None:
    """The comparison must not accidentally calibrate two different truths."""
    targets: dict[int, SimpleNamespace] = {}
    calls: list[tuple[str, int]] = []

    class FakeExperiment:
        def __init__(self, *, calib_strategy, **unused_kwargs) -> None:
            self.method = calib_strategy.method
            self.directory = tmp_path / self.method

        def perform_one_case(
            self, case: int, *, lpm_random: bool, lpm_target
        ) -> tuple[SimpleNamespace, _Calibration, SimpleNamespace, object, float]:
            assert lpm_random
            target = targets.setdefault(
                case, SimpleNamespace(name="exp", p={"mu": 12.0})
            )
            calls.append((self.method, id(target)))
            return (
                target,
                _Calibration(self.method),
                SimpleNamespace(),
                object(),
                0.0,
            )

        def get_directory(self) -> Path:
            return self.directory

        def write_parameters_test(self) -> None:
            pass

        def write_results(self) -> None:
            pass

    monkeypatch.setattr(benchmark, "ROOT_DIRECTORY_RESULTS", tmp_path)
    monkeypatch.setattr(benchmark, "timestamp_name", lambda: "run")
    monkeypatch.setattr(benchmark, "SyntheticRecoveryExperiment", FakeExperiment)
    monkeypatch.setattr(benchmark, "plot_parameter_diagnostics", lambda *a, **k: None)
    monkeypatch.setattr(
        benchmark, "plot_concentration_diagnostics", lambda *a, **k: None
    )

    comparison = benchmark.comparison_MH_fuq()
    comparison.models_calib = ["exp"]
    timer = _Timer()

    target, results, _, calibrations = comparison.perform(
        timer, ncase=1, tracer_names=["cfc11"], resolution=10
    )

    assert target is targets[0]
    assert len(results) == len(calibrations) == 2
    assert [method for method, _ in calls] == [
        "forward_uncertainty_quantification",
        "Metropolis_Hastings",
    ]
    assert calls[0][1] == calls[1][1]
    assert timer.initialized_with == 1
    assert timer.actualizations == 1
