# -*- coding: utf-8 -*-
# Copyright (c) 2021-2026 Centre national de la recherche scientifique (CNRS)
# Contributor: Jean-Raynald de Dreuzy
# SPDX-License-Identifier: CECILL-2.1

"""
Golden tests for LPM distribution moments under fixed random parameters.
"""

from pathlib import Path

import numpy as np
import pytest

from pyages.lpm import build_lpm, list_available_lpms
from tests.utils import golden as golden_utils
from tests.utils import paths as test_paths


def _lpm_types() -> list[str]:
    types = list_available_lpms()
    return sorted(t for t in types if t != "mix_exp_shifted")


def _golden_path() -> Path:
    return test_paths.repo_root() / "tests" / "golden" / "lpm_moments_values.json"


def _round_list(values: list[float], ndigits: int = 10) -> list[float]:
    return [float(np.round(v, ndigits)) for v in values]


@pytest.mark.parametrize("lpm_type", _lpm_types())
def test_lpm_golden_moments(lpm_type, update_golden):
    rng = np.random.default_rng(12345)
    lpm = build_lpm(lpm_type, directory_lpm=str(test_paths.lpm_data_dir()))
    lpm.random_uniform(rng=rng)
    moments = _round_list(lpm.moments())

    key = lpm_type
    store = golden_utils.load_golden(_golden_path())
    record = {
        "moments": moments,
        "names": lpm.moments_name(),
    }

    if update_golden:
        store[key] = record
        golden_utils.save_golden(_golden_path(), store)
        pytest.skip(f"Golden updated for {key}")

    if key not in store:
        pytest.fail(f"Golden value missing for {key}. Run: pytest -s --update-golden")

    expected = store[key]["moments"]
    assert moments == pytest.approx(expected, rel=1e-6, abs=1e-6)
