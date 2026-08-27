# Copyright (c) 2021-2026 Centre national de la recherche scientifique (CNRS)
# Contributor: Jean-Raynald de Dreuzy
# SPDX-License-Identifier: CECILL-2.1

"""Contracts for the calibrated LPM sample container."""

from __future__ import annotations

import math

import numpy as np
import pandas as pd
import pytest

from pyages.data_io.lpm_distribution import (
    read_distribution,
    read_histograms,
    read_statistics,
    write_distribution,
    write_frame,
    write_histograms,
    write_statistics,
)
from pyages.lpm import build_lpm
from pyages.lpm.samples.table import LpmSampleTable


def _distribution() -> tuple[LpmSampleTable, str, float]:
    model = build_lpm("exp")
    name = model.get_param_names()[0]
    initial = float(model.p[name])
    distribution = LpmSampleTable(model, c_names=["cfc11_2010_0"])
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


def test_append_rejects_misaligned_concentrations() -> None:
    distribution, name, initial = _distribution()

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


def test_analysis_helpers_do_not_mutate_the_model_template() -> None:
    distribution, name, initial = _distribution()
    for offset in (1.0, 2.0, 3.0):
        distribution.append_sample(
            {name: initial + offset},
            obj_function=offset,
            concentrations=[offset],
        )
    before = distribution.lpm_template.p.copy()

    distribution.select(count=3, rng=np.random.default_rng(7))
    assert distribution.lpm_template.p == before

    distribution.add_moments()
    assert distribution.lpm_template.p == before


def test_best_row_ignores_nonfinite_objectives() -> None:
    distribution, name, initial = _distribution()
    for offset, objective in enumerate((math.inf, -math.inf, math.nan, 3.0), start=1):
        distribution.append_sample(
            {name: initial + offset},
            obj_function=objective,
            concentrations=[float(offset)],
        )

    assert distribution.best_row()[name] == pytest.approx(initial + 4.0)


def test_replace_frame_validates_atomically() -> None:
    distribution, name, initial = _distribution()
    before = distribution.frame.copy()

    with pytest.raises(ValueError, match="Missing sample columns"):
        distribution.replace_frame(pd.DataFrame([[initial]], columns=[name]))
    pd.testing.assert_frame_equal(distribution.frame, before)

    with pytest.raises(ValueError, match="Duplicate sample columns"):
        distribution.replace_frame(
            pd.DataFrame(
                [[initial, 0.0, 1.0, initial]],
                columns=[name, "obj_function", "cfc11_2010_0", name],
            )
        )
    pd.testing.assert_frame_equal(distribution.frame, before)


def test_append_rejects_different_concentration_schemas() -> None:
    distribution, _, _ = _distribution()
    other = LpmSampleTable(distribution.lpm_template, c_names=["sf6_2010_0"])

    with pytest.raises(ValueError, match="different concentrations"):
        distribution.append(other)


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

    loaded_samples = read_distribution(samples_path)
    loaded_histograms = read_histograms(histogram_path, [name])
    loaded_statistics = read_statistics(statistics_path)
    pd.testing.assert_frame_equal(loaded_samples, distribution.frame)
    pd.testing.assert_frame_equal(
        loaded_histograms[name],
        pd.DataFrame(
            {
                "val": distribution.histograms()[name]["bins"][:-1],
                "hist": distribution.histograms()[name]["hist"],
            }
        ),
    )
    pd.testing.assert_frame_equal(loaded_statistics, distribution.statistics())


def test_read_histograms_rejects_an_unexpected_layout(tmp_path) -> None:
    histogram_path = tmp_path / "histogram.txt"
    write_frame(
        pd.DataFrame({"value": [1.0], "density": [0.5]}),
        tmp_path / "histogram_mu.txt",
        index=False,
    )

    with pytest.raises(ValueError, match="Invalid histogram columns"):
        read_histograms(histogram_path, ["mu"])


@pytest.mark.parametrize(
    "writer",
    [write_distribution, write_histograms, write_statistics],
)
def test_tabular_outputs_reject_an_invalid_sample_table(writer, tmp_path) -> None:
    distribution, _, _ = _distribution()
    distribution.frame.drop(columns=["obj_function"], inplace=True)
    target = tmp_path / "invalid.txt"

    with pytest.raises(ValueError, match="Missing sample columns"):
        writer(distribution, target)

    assert not target.exists()


def test_write_frame_replaces_the_target_only_after_a_complete_write(
    tmp_path, monkeypatch
) -> None:
    target = tmp_path / "samples.txt"
    target.write_text("previous content\n", encoding="utf-8")
    frame = pd.DataFrame({"value": [1.0]})

    def interrupted_to_csv(self, stream, **kwargs):
        del self, kwargs
        stream.write("partial content\n")
        raise RuntimeError("interrupted write")

    monkeypatch.setattr(pd.DataFrame, "to_csv", interrupted_to_csv)

    with pytest.raises(RuntimeError, match="interrupted write"):
        write_frame(frame, target, index=False)

    assert target.read_text(encoding="utf-8") == "previous content\n"
    assert list(tmp_path.iterdir()) == [target]
