"""Contracts for the calibrated LPM sample container."""

from __future__ import annotations

import pandas as pd
import pytest

from pyage.data_io.lpm_distribution import (
    write_distribution,
    write_histograms,
    write_statistics,
)
from pyage.lpm.core.lpm_dist import LpmDist
from pyage.lpm.lpm_build import lpm_build


def _distribution() -> tuple[LpmDist, str, float]:
    model = lpm_build("exp")
    name = model.get_param_names()[0]
    initial = float(model.p[name])
    distribution = LpmDist(model, c_names=["cfc11_2010_0"])
    return distribution, name, initial


def test_samples_have_an_explicit_frame_and_best_model() -> None:
    distribution, name, initial = _distribution()
    distribution.append_sample(
        {name: initial + 2.0}, obj_function=4.0, concentrations=[1.5]
    )
    distribution.append_sample(
        {name: initial + 1.0}, obj_function=1.0, concentrations=[1.0]
    )

    distribution.validate()
    assert distribution.best_row()[name] == pytest.approx(initial + 1.0)

    best = distribution.best_model()
    assert best is not None
    assert best is not distribution.lpm_template
    assert best.p[name] == pytest.approx(initial + 1.0)


def test_append_rejects_misaligned_vectors() -> None:
    distribution, name, initial = _distribution()

    with pytest.raises(ValueError, match="parameter count"):
        distribution.append_values([initial, initial])
    with pytest.raises(ValueError, match="concentration names"):
        distribution.append_sample({name: initial}, concentrations=[])


def test_analysis_helpers_preserve_the_sample_table_contract() -> None:
    distribution, name, initial = _distribution()
    for offset in (1.0, 2.0, 3.0):
        distribution.append_sample(
            {name: initial + offset},
            obj_function=offset,
            concentrations=[offset],
        )

    histograms = distribution.histograms(bin_count=2)
    assert set(histograms) == {name}
    assert len(histograms[name]["hist"]) == 2
    assert len(histograms[name]["bins"]) == 3

    distribution.add_moments().add_moments()
    for moment_name in distribution.lpm_template.moments_name():
        assert list(distribution.frame.columns).count(moment_name) == 1
    assert len(distribution.frame) == 3


def test_tabular_outputs_keep_the_existing_tsv_layout(tmp_path) -> None:
    distribution, name, initial = _distribution()
    distribution.append_sample({name: initial}, obj_function=0.0, concentrations=[1.0])

    samples_path = tmp_path / "lpm_dist_calibrated.txt"
    histogram_path = tmp_path / "histogram.txt"
    statistics_path = tmp_path / "statistics.txt"
    write_distribution(distribution, samples_path)
    write_histograms(distribution, histogram_path)
    write_statistics(distribution, statistics_path)

    samples = pd.read_table(samples_path)
    histogram = pd.read_table(tmp_path / f"histogram_{name}.txt")
    statistics = pd.read_table(statistics_path)
    assert {name, "obj_function", "cfc11_2010_0"}.issubset(samples.columns)
    assert list(histogram.columns) == ["val", "hist"]
    assert name in statistics.columns
    assert "mean" in set(statistics.iloc[:, 0])
