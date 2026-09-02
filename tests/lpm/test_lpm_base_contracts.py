# Copyright (c) 2021-2026 Centre national de la recherche scientifique (CNRS)
# Contributor: Jean-Raynald de Dreuzy
# SPDX-License-Identifier: CECILL-2.1

"""Direct contract tests for the common LPM base class."""

from __future__ import annotations

import inspect
import math

import numpy as np
import pandas as pd
import pytest

from pyages.convolution import Convolution, ConvolutionError
from pyages.lpm import build_lpm
from pyages.lpm.core.lpm_base import LpmBase
from pyages.lpm.core.lpm_scipy import LpmScipy
from pyages.lpm.core.parameter_manager import ParameterManager
from pyages.tracer.simple_tracers import ConstantTracer
from tests.utils import paths as test_paths


class _MinimalContinuousLpm(LpmBase):
    """Small exponential law used to exercise base implementations directly."""

    def __init__(self, parameter_values=None, parameter_units=None):
        values = {"mu": 10.0} if parameter_values is None else parameter_values
        units = {"mu": "year"} if parameter_units is None else parameter_units
        super().__init__("exp", values, units, test_paths.lpm_data_dir())

    def pdf(self, t):
        values = np.asarray(t, dtype=float)
        result = np.exp(-values / self.p["mu"]) / self.p["mu"]
        return float(result) if values.ndim == 0 else result

    def cdf(self, t):
        values = np.asarray(t, dtype=float)
        result = np.where(values >= 0.0, -np.expm1(-values / self.p["mu"]), 0.0)
        return float(result) if values.ndim == 0 else result

    def mean(self):
        return float(self.p["mu"])

    def std(self):
        return float(self.p["mu"])


def _lpm(name: str):
    return build_lpm(name, directory_lpm=test_paths.lpm_data_dir())


def test_scipy_adapter_requires_a_concrete_parameter_mapping() -> None:
    assert inspect.isabstract(LpmScipy)
    assert LpmScipy.__abstractmethods__ == frozenset({"_scipy_params"})


def test_constructor_copies_parameter_metadata_and_units_property() -> None:
    values = {"mu": 10.0}
    units = {"mu": "year"}
    model = _MinimalContinuousLpm(values, units)

    values["mu"] = 20.0
    units["mu"] = "day"
    exposed_units = model.parameter_units
    exposed_units["mu"] = "second"

    assert model.p == {"mu": 10.0}
    assert model.parameter_units == {"mu": "year"}


def test_constructor_rejects_inconsistent_or_nonfinite_metadata() -> None:
    with pytest.raises(ValueError, match="parameter_units must match"):
        _MinimalContinuousLpm({"mu": 10.0}, {})
    with pytest.raises(ValueError, match="finite numeric"):
        _MinimalContinuousLpm({"mu": math.nan}, {"mu": "year"})


@pytest.mark.parametrize("value", [math.nan, math.inf, -math.inf, "invalid"])
def test_calibration_ranges_reject_nonfinite_or_nonnumeric_values(value) -> None:
    model = _lpm("exp")

    assert not model.param_within_calibration_range({"mu": value})
    assert not model.param_within_calibration_range_array([value])


def test_calibration_ranges_require_complete_names_and_vector_shape() -> None:
    model = _lpm("gamma")

    assert not model.param_within_calibration_range({})
    assert not model.param_within_calibration_range({"k": 2.0})
    assert not model.param_within_calibration_range({"k": 2.0, "scale": 10.0, "x": 1.0})
    assert not model.param_within_calibration_range_array([2.0])
    assert not model.param_within_calibration_range_array([2.0, 10.0, 30.0])
    assert not model.param_within_calibration_range_array([[2.0, 10.0]])


def test_legacy_bounds_methods_delegate_to_calibration_range_methods() -> None:
    model = _lpm("exp")

    assert model.param_within_bounds(model.p) == model.param_within_calibration_range(
        model.p
    )
    assert model.param_within_bounds_array(
        model.get_parameters_to_array()
    ) == model.param_within_calibration_range_array(model.get_parameters_to_array())
    assert model.get_param_interval() == (
        [model.get_p_min("mu")],
        [model.get_p_max("mu")],
    )
    assert model.get_calibration_range("mu") == (
        model.get_p_min("mu"),
        model.get_p_max("mu"),
    )
    assert model.get_param_range("mu") == model.get_calibration_range_width("mu")


@pytest.mark.parametrize(
    "values",
    [[3.0], [3.0, 12.0, 99.0], [[3.0, 12.0]], [3.0, math.nan]],
)
def test_set_param_from_array_is_atomic(values) -> None:
    model = _lpm("gamma")
    before = model.p.copy()

    with pytest.raises(ValueError):
        model.set_param_from_array(values)

    assert model.p == before


def test_set_param_from_array_replaces_all_values_in_order() -> None:
    model = _lpm("gamma")

    model.set_param_from_array(np.array([3.0, 12.0]))

    assert model.p == {"k": 3.0, "scale": 12.0}


@pytest.mark.parametrize(
    "name",
    [
        "exp",
        "ig",
        "dirac",
        "dirac_double",
        "dirac_double_1_set",
        "mix_exp_shifted",
        "shapefree_n_oldbin",
    ],
)
@pytest.mark.parametrize("probability", [-0.1, 1.1, math.nan, math.inf])
def test_all_quantile_families_reject_invalid_probabilities(name, probability) -> None:
    with pytest.raises(ValueError, match="Probabilities"):
        _lpm(name).cdf_inv(probability)


def test_discrete_quantiles_are_vectorized() -> None:
    model = _lpm("dirac_double")
    model.p.update({"mu1": 10.0, "mu2": 5.0, "rate": 0.2})

    assert model.cdf_inv(np.array([0.0, 0.2, 0.200001, 1.0])) == pytest.approx(
        [10.0, 10.0, 15.0, 15.0]
    )


def test_default_quantile_solver_and_invalid_endpoint() -> None:
    model = _MinimalContinuousLpm()

    assert model.cdf_inv(0.5) == pytest.approx(10.0 * np.log(2.0))
    with pytest.raises(ValueError, match="0 <= p < 1"):
        model.cdf_inv(1.0)


def test_moment_labels_use_consistent_percentile_names() -> None:
    model = _MinimalContinuousLpm()

    assert model.moments_name() == [
        "mean",
        "std",
        "p10",
        "p25",
        "p50",
        "p75",
        "p90",
    ]


def test_continuous_base_stub_is_rejected_before_convolution() -> None:
    tracer = ConstantTracer(concentration=1.0, datemin=1900.0)

    with pytest.raises(
        ConvolutionError,
        match="must implement cdf_and_partial_first_moment",
    ):
        Convolution(tracer, date=2010.0).convolve(_MinimalContinuousLpm())


@pytest.mark.parametrize("kind,count", [("density", 10), ("pdf", 1), ("cdf", 2.5)])
def test_sample_curve_validates_kind_and_count(kind, count) -> None:
    with pytest.raises(ValueError):
        _lpm("exp").sample_curve(kind, count)


def test_load_sample_is_atomic_and_rejects_invalid_rows() -> None:
    model = _lpm("gamma")
    frame = pd.DataFrame({"k": [2.0, 3.0], "scale": [10.0, math.nan]})
    before = model.p.copy()

    with pytest.raises(IndexError):
        model.load_sample(frame, row=-1)
    with pytest.raises(IndexError):
        model.load_sample(frame, row=2)
    with pytest.raises(ValueError, match="finite"):
        model.load_sample(frame, row=1)

    assert model.p == before


def test_load_sample_requires_all_parameter_columns() -> None:
    model = _lpm("gamma")

    with pytest.raises(KeyError, match="scale"):
        model.load_sample(pd.DataFrame({"k": [2.0]}))


def test_load_sample_returns_the_selected_row_position() -> None:
    model = _lpm("gamma")
    frame = pd.DataFrame({"k": [2.0, 3.0], "scale": [10.0, 12.0]})

    selected_row = model.load_sample(frame, row=1)

    assert selected_row == 1
    assert model.p == {"k": 3.0, "scale": 12.0}


@pytest.mark.parametrize(
    "yaml_text,match",
    [
        (
            """model: other
parameters:
  - name: mu
    bounds: [0.1, 100.0]
    init: 10.0
""",
            "declares model",
        ),
        (
            """model: custom
parameters:
  - name: other
    bounds: [0.1, 100.0]
    init: 10.0
""",
            "names do not match",
        ),
        (
            """model: custom
parameters:
  - name: mu
    bounds: [0.1, 100.0]
    init: .nan
""",
            "must be finite and within",
        ),
    ],
)
def test_parameter_manager_rejects_inconsistent_yaml(
    tmp_path, yaml_text, match
) -> None:
    model_dir = tmp_path / "custom"
    model_dir.mkdir()
    (model_dir / "params.yaml").write_text(yaml_text, encoding="utf-8")

    with pytest.raises(ValueError, match=match):
        ParameterManager("custom", tmp_path, ["mu"])


def test_parameter_manager_rejects_duplicate_constructor_names(tmp_path) -> None:
    with pytest.raises(ValueError, match="must not contain duplicates"):
        ParameterManager("custom", tmp_path, ["mu", "mu"])


@pytest.mark.parametrize("parameter_names", [[], [""], [None]])
def test_parameter_manager_rejects_empty_or_non_string_names(
    tmp_path, parameter_names
) -> None:
    with pytest.raises(ValueError, match="non-empty strings"):
        ParameterManager("custom", tmp_path, parameter_names)


def test_parameter_manager_requires_parameter_file(tmp_path) -> None:
    with pytest.raises(FileNotFoundError, match="Missing params.yaml"):
        ParameterManager("custom", tmp_path, ["mu"])


def test_loading_initial_values_requires_exact_target_names() -> None:
    manager = ParameterManager("exp", test_paths.lpm_data_dir(), ["mu"])
    target = {"other": 12.0}

    with pytest.raises(ValueError, match="target_params must match"):
        manager.load_initial_values(target)

    assert target == {"other": 12.0}


@pytest.mark.parametrize(
    "params",
    [
        {},
        {"other": 1.0},
        {"mu": "invalid"},
        {"mu": math.nan},
        {"mu": math.inf},
        {"mu": -1.0},
        {"mu": 101.0},
    ],
)
def test_parameter_manager_mapping_checks_reject_invalid_values(params) -> None:
    manager = ParameterManager("exp", test_paths.lpm_data_dir(), ["mu"])

    assert not manager.param_within_calibration_range(params)
    assert not manager.param_within_bounds(params)


@pytest.mark.parametrize(
    ("values", "order"),
    [
        ([1.0], ["other"]),
        (None, ["mu"]),
        ([], ["mu"]),
        (["invalid"], ["mu"]),
        ([math.nan], ["mu"]),
        ([math.inf], ["mu"]),
        ([-1.0], ["mu"]),
        ([101.0], ["mu"]),
    ],
)
def test_parameter_manager_vector_checks_reject_invalid_values(values, order) -> None:
    manager = ParameterManager("exp", test_paths.lpm_data_dir(), ["mu"])

    assert not manager.param_within_calibration_range_array(values, order)
    assert not manager.param_within_bounds_array(values, order)


@pytest.mark.parametrize(
    ("values", "order"),
    [
        ([1.0], ["other"]),
        (None, ["mu"]),
        ([], ["mu"]),
        (["invalid"], ["mu"]),
        ([-1.0], ["mu"]),
    ],
)
def test_parameter_manager_domain_vector_rejects_invalid_values(values, order) -> None:
    manager = ParameterManager("exp", test_paths.lpm_data_dir(), ["mu"])

    assert not manager.param_within_domain_array(values, order)


def test_parameter_manager_legacy_accessors_delegate_to_calibration_ranges() -> None:
    manager = ParameterManager("exp", test_paths.lpm_data_dir(), ["mu"])
    interval = manager.get_calibration_range("mu")

    assert manager.get_param_range("mu") == manager.get_calibration_range_width("mu")
    assert manager.get_param_interval() == ([interval[0]], [interval[1]])
    assert manager.get_p_min("mu") == interval[0]
    assert manager.get_p_max("mu") == interval[1]
