# Copyright (c) 2021-2026 Centre national de la recherche scientifique (CNRS)
# Contributor: Jean-Raynald de Dreuzy
# SPDX-License-Identifier: CECILL-2.1

import csv
from pathlib import Path

import pytest

from pyages.convolution.settings import ConvolutionSettings
from validation.tracerlpm.benchmark.scripts import (
    compare_pyages,
    study_pyages_convergence,
)
from validation.tracerlpm.benchmark.scripts.compare_pyages import (
    ForwardQualificationThresholds,
    compare,
    input_concentration_scale,
    load_qualification_thresholds,
    parse_parameters,
    pyages_parameters,
    qualify_forward_case,
    symmetric_relative_difference,
)
from validation.tracerlpm.benchmark.scripts.study_pyages_convergence import (
    qualification_by_scale,
)


def test_parameter_parser_and_dm_mapping():
    parameters = parse_parameters("tau=40;DP=0.2")
    assert pyages_parameters("DM", parameters) == pytest.approx(
        {"mu": 40, "sigma": 40 * (0.4**0.5)}
    )


def test_symmetric_relative_difference_is_signed_and_bounded():
    assert symmetric_relative_difference(10, 10) == 0
    assert symmetric_relative_difference(11, 10) > 0
    assert symmetric_relative_difference(9, 10) < 0
    assert abs(symmetric_relative_difference(1, 0)) <= 2


def test_reference_contains_expected_number_of_cases():
    path = Path(__file__).parents[1] / "references" / "forward_reference.csv"
    with path.open(encoding="utf-8", newline="") as stream:
        rows = list(csv.DictReader(stream))
    assert len(rows) == 270


def test_invalid_grid_settings_are_rejected():
    with pytest.raises(ValueError, match="relative_tolerance"):
        ConvolutionSettings(relative_tolerance=-1.0)


def test_versioned_forward_qualification_thresholds():
    thresholds = load_qualification_thresholds()

    assert thresholds == ForwardQualificationThresholds()
    assert thresholds.maximum_significant_symmetric_relative_difference == 5e-4
    assert (
        thresholds.maximum_near_zero_absolute_difference_fraction_of_input_scale == 2e-5
    )
    assert thresholds.require_all_cases


def test_forward_qualification_rejects_nonfinite_thresholds():
    with pytest.raises(ValueError, match="must be positive"):
        ForwardQualificationThresholds(
            maximum_significant_symmetric_relative_difference=float("nan")
        )


def test_forward_qualification_uses_relative_metric_for_significant_values():
    thresholds = ForwardQualificationThresholds()

    passing = qualify_forward_case(5.503883, 5.502699, 100.0, thresholds)
    failing = qualify_forward_case(5.51, 5.50, 100.0, thresholds)

    assert passing["qualification_regime"] == "significant"
    assert passing["qualification_threshold"] == 5e-4
    assert passing["qualified"]
    assert not failing["qualified"]


def test_forward_qualification_uses_absolute_metric_near_zero():
    thresholds = ForwardQualificationThresholds()

    passing = qualify_forward_case(0.014192, 0.013100, 100.0, thresholds)
    failing = qualify_forward_case(0.016, 0.013, 100.0, thresholds)

    assert passing["qualification_regime"] == "near_zero"
    assert passing["qualification_threshold"] == pytest.approx(0.002)
    assert passing["qualified"]
    assert not failing["qualified"]


def test_forward_qualification_rejects_nonfinite_or_nonphysical_values():
    thresholds = ForwardQualificationThresholds()

    invalid = qualify_forward_case(float("nan"), 1.0, 100.0, thresholds)
    assert invalid["qualification_regime"] == "invalid"
    assert invalid["qualification_budget_fraction"] is None
    assert not invalid["qualified"]
    assert not qualify_forward_case(-1.0, 1.0, 100.0, thresholds)["qualified"]
    assert not qualify_forward_case(101.0, 100.0, 100.0, thresholds)["qualified"]


def test_default_forward_matrix_qualifies_all_cases(tmp_path):
    report = compare(output_dir=tmp_path)
    qualification = report["qualification"]

    assert report["status"] == "qualified"
    assert report["case_count"] == 270
    assert qualification["significant_case_count"] == 237
    assert qualification["near_zero_case_count"] == 33
    assert qualification["qualified_case_count"] == 270
    assert qualification["failed_case_count"] == 0
    assert qualification["all_cases_qualified"]
    assert qualification[
        "maximum_significant_absolute_symmetric_relative_difference"
    ] == pytest.approx(2.14993141976e-4)
    assert qualification["maximum_near_zero_absolute_difference"] == pytest.approx(
        1.09216008739e-3
    )
    assert all(item["failed_case_count"] == 0 for item in report["families"].values())


def test_input_scales_match_the_versioned_histories():
    root = Path(__file__).parents[1] / "inputs" / "synthetic"

    assert input_concentration_scale(root / "constant.csv") == 100.0
    assert input_concentration_scale(root / "multi_peak.csv") == pytest.approx(
        100.09004157023
    )


def test_convergence_gate_requires_default_and_tighter_scales_only():
    def report(status, passed):
        return {
            "status": status,
            "qualification": {
                "qualified_case_count": passed,
                "failed_case_count": 270 - passed,
            },
        }

    qualified = qualification_by_scale(
        [
            (4.0, report("failed_qualification", 260)),
            (2.0, report("failed_qualification", 269)),
            (1.0, report("qualified", 270)),
            (0.5, report("qualified", 270)),
            (0.25, report("qualified", 270)),
        ]
    )
    failed = qualification_by_scale(
        [(1.0, report("qualified", 270)), (0.5, report("failed_qualification", 269))]
    )

    assert qualified["status"] == "qualified"
    assert failed["status"] == "failed_qualification"
    assert qualification_by_scale([])["status"] == "failed_qualification"


def test_forward_cli_returns_nonzero_for_failed_qualification(monkeypatch, tmp_path):
    monkeypatch.setattr(
        compare_pyages,
        "compare",
        lambda *unused_args, **unused_kwargs: {"status": "failed_qualification"},
    )

    assert compare_pyages.main(["--output", str(tmp_path)]) == 1


def test_convergence_cli_returns_nonzero_for_failed_required_scale(
    monkeypatch, tmp_path
):
    monkeypatch.setattr(
        study_pyages_convergence,
        "study",
        lambda *unused_args, **unused_kwargs: {"status": "failed_qualification"},
    )

    assert study_pyages_convergence.main(["--output", str(tmp_path)]) == 1
