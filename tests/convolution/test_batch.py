# Copyright (c) 2021-2026 Centre national de la recherche scientifique (CNRS)
# Contributor: Jean-Raynald de Dreuzy
# SPDX-License-Identifier: CECILL-2.1

"""
Synthetic non-regression tests for ConvolutionTracers.

Focus:
- deterministic sampling via fixed RNG
- stable aggregate stats for golden checks
"""

from pathlib import Path

import numpy as np
import pytest

from pyages.config.runtime import DisplayOptions
from pyages.convolution import ConvolutionTracers
from pyages.lpm import build_lpm, build_random_lpm, list_available_lpms
from tests.utils import golden as golden_utils
from tests.utils import paths as test_paths


def _golden_path() -> Path:
    return test_paths.repo_root() / "tests" / "golden" / "convolution_batch_values.json"


def _lpm_types() -> list[str]:
    types = list_available_lpms()
    return sorted(t for t in types if t != "mix_exp_shifted")


LPM_NAMES = _lpm_types()
TRACER_NAMES = ["cfc11", "cfc12", "cfc113"]
DATE = 2010.0


def test_date_count_must_match_tracer_count() -> None:
    with pytest.raises(ValueError, match="Expected 2 tracer dates, received 1"):
        ConvolutionTracers(names=["cfc11", "cfc12"], date=[DATE])


@pytest.mark.parametrize("date", [np.nan, True, "2010"])
def test_batch_rejects_invalid_observation_dates(date) -> None:
    with pytest.raises(ValueError, match="observation date"):
        ConvolutionTracers(names=["cfc11"], date=date)


def test_batch_exposes_explicit_convolution_collection() -> None:
    tracers = ConvolutionTracers(names=["cfc11", "cfc12"], date=DATE)

    assert tracers.tracer_names() == ["cfc11", "cfc12"]
    assert [item.tracer.name for item in tracers.convolutions] == [
        "cfc11",
        "cfc12",
    ]


def test_display_delegates_to_the_underlying_tracers(monkeypatch) -> None:
    tracers = ConvolutionTracers(names=["cfc11"], date=DATE)
    options = DisplayOptions()
    calls = []
    monkeypatch.setattr(
        tracers.convolutions[0].tracer,
        "display",
        lambda received: calls.append(received),
    )

    tracers.display(options)

    assert calls == [options]


def test_unknown_return_type_is_rejected_before_convolution() -> None:
    tracers = ConvolutionTracers(names=["cfc11"], date=DATE)
    lpm = build_lpm("exp", directory_lpm=str(test_paths.lpm_data_dir()))

    with pytest.raises(ValueError, match="Unknown return_type"):
        tracers.convolve(lpm, return_type="unknown")

    assert tracers.convolutions[0].prepared_grid is None


def test_date_range_rejects_duplicate_tracer_names_before_convolution() -> None:
    tracers = ConvolutionTracers(
        names=["cfc11", "cfc11"],
        date=[2010.0, 2011.0],
    )
    lpm = build_lpm("exp", directory_lpm=str(test_paths.lpm_data_dir()))

    with pytest.raises(ValueError, match=r"unique tracer names.*cfc11"):
        tracers.convolve_date_range(lpm, 2000.0, 2005.0)

    assert all(item.prepared_grid is None for item in tracers.convolutions)


@pytest.mark.parametrize("lpm_name", LPM_NAMES)
def test_convolution_batch_golden(lpm_name, update_golden):
    rng = np.random.default_rng(12345)
    lpm = build_random_lpm(lpm_name, rng=rng)
    tracers = ConvolutionTracers(names=TRACER_NAMES, date=DATE)

    concentrations = tracers.convolve(
        lpm,
        return_type="concentrations",
    )
    df = tracers.convolve(lpm, return_type="dataframe")

    stats = {
        "mean_concentration": float(concentrations.frame["concentration"].mean()),
        "mean_error": float(concentrations.frame["error"].mean()),
        "dataframe_mean_concentration": float(df["concentration"].mean()),
    }

    key = f"{lpm_name}:date={DATE}:tracers={','.join(TRACER_NAMES)}"
    store = golden_utils.load_golden(_golden_path())

    if update_golden:
        store[key] = stats
        golden_utils.save_golden(_golden_path(), store)
        pytest.skip(f"Golden updated for {key}")

    if key not in store:
        pytest.fail(f"Golden value missing for {key}. Run: pytest -s --update-golden")

    expected = store[key]
    assert stats["mean_concentration"] == pytest.approx(
        expected["mean_concentration"], rel=1e-6, abs=1e-6
    )
    assert stats["mean_error"] == pytest.approx(
        expected["mean_error"], rel=1e-6, abs=1e-6
    )
    assert stats["dataframe_mean_concentration"] == pytest.approx(
        expected["dataframe_mean_concentration"], rel=1e-6, abs=1e-6
    )
