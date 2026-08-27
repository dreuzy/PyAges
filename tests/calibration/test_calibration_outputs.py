# Copyright (c) 2021-2026 Centre national de la recherche scientifique (CNRS)
# Contributor: Jean-Raynald de Dreuzy
# SPDX-License-Identifier: CECILL-2.1

"""Output routing contracts shared by calibration methods."""

from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock

import pytest

from pyages.calibration import outputs


def test_posterior_directory_builds_the_requested_shared_location(tmp_path) -> None:
    reference = tmp_path / "a" / "b" / "c" / "d" / "result.txt"
    reference.parent.mkdir(parents=True)

    destination = outputs.posterior_directory(
        reference, parent_levels=3, subdirectory="exp"
    )

    assert destination == reference.resolve().parents[2] / "prior_distributions" / "exp"
    assert destination.is_dir()


@pytest.mark.parametrize("parent_levels", [0, -1])
def test_posterior_directory_rejects_non_positive_levels(
    tmp_path, parent_levels
) -> None:
    with pytest.raises(ValueError, match="must be positive"):
        outputs.posterior_directory(
            tmp_path / "result.txt", parent_levels=parent_levels
        )


def test_posterior_directory_rejects_traversal_above_the_root(tmp_path) -> None:
    with pytest.raises(ValueError, match="goes above the root"):
        outputs.posterior_directory(tmp_path / "result.txt", parent_levels=10_000)


def test_output_naming_and_key_value_serialization(tmp_path) -> None:
    assert outputs.posterior_file_stem("F09", 0.1, "ig") == "F09_err_0.1_lpm_ig"
    target = tmp_path / "values.txt"

    outputs.write_key_values(target, {"method": "MH", "seed": 123})

    assert target.read_text(encoding="utf-8") == "method\tMH\nseed\t123\n"


def test_display_calibrated_models_dispatches_text_and_figure(monkeypatch) -> None:
    reference = object()
    best_model = object()
    results = SimpleNamespace(best_model=lambda: best_model)
    comparison = Mock()
    diagnostics = Mock()
    monkeypatch.setattr(outputs, "print_parameter_comparison", comparison)
    monkeypatch.setattr(outputs, "plot_parameter_diagnostics", diagnostics)
    problem = SimpleNamespace(
        display_options=SimpleNamespace(directory=Path("figures"))
    )

    outputs.display_calibrated_models(
        SimpleNamespace(method="Simplex"),
        problem,
        results,
        SimpleNamespace(text=True, figure=False),
        reference=reference,
    )
    comparison.assert_called_once_with(best_model, reference)
    diagnostics.assert_not_called()

    outputs.display_calibrated_models(
        SimpleNamespace(method="Metropolis_Hastings"),
        problem,
        results,
        SimpleNamespace(text=False, figure=True),
        reference=reference,
    )
    diagnostics.assert_called_once_with(
        results,
        self_method="Metropolis_Hastings",
        lpm_reference=reference,
        directory=Path("figures"),
    )


@pytest.mark.parametrize(
    ("method_name", "with_prior", "expected_distribution_calls", "expected_histograms"),
    [
        ("Simplex", False, 0, 0),
        ("forward_uncertainty_quantification", False, 1, 1),
        ("Metropolis_Hastings", True, 1, 2),
    ],
)
def test_write_calibrated_result_emits_the_method_specific_artifact_set(
    tmp_path,
    method_name,
    with_prior,
    expected_distribution_calls,
    expected_histograms,
    monkeypatch,
) -> None:
    method = SimpleNamespace(
        method=method_name,
        write_parameters=Mock(),
        write_results=Mock(),
    )
    problem = SimpleNamespace(
        display_options=SimpleNamespace(directory=tmp_path / "run")
    )
    results = object()
    write_distribution = Mock()
    write_histograms = Mock()
    write_statistics = Mock()
    prior_directory = tmp_path / "priors"
    monkeypatch.setattr(outputs, "write_distribution", write_distribution)
    monkeypatch.setattr(outputs, "write_histograms", write_histograms)
    monkeypatch.setattr(outputs, "write_statistics", write_statistics)
    monkeypatch.setattr(
        outputs, "posterior_directory", lambda *_args, **_kwargs: prior_directory
    )

    outputs.write_calibrated_result(
        method,
        problem,
        results,
        prior_file="posterior" if with_prior else None,
        prior_folder="audit",
    )

    base = tmp_path / "run"
    method.write_parameters.assert_called_once_with(base / "parameters_calibration.txt")
    method.write_results.assert_called_once_with(base / "results_calibration.txt")
    assert write_distribution.call_count == expected_distribution_calls
    assert write_histograms.call_count == expected_histograms
    assert write_statistics.call_count == expected_distribution_calls
    if with_prior:
        assert write_histograms.call_args_list[-1].args == (
            results,
            prior_directory / "posterior.txt",
        )
