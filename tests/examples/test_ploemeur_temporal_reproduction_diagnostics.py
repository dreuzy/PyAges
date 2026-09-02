# Copyright (c) 2021-2026 Centre national de la recherche scientifique (CNRS)
# Contributor: Jean-Raynald de Dreuzy
# SPDX-License-Identifier: CECILL-2.1

"""Compatibility checks for the frozen Figure 4 diagnostic implementation."""

from __future__ import annotations

import numpy as np

from examples.natural.ploemeur_temporal import reproduction_diagnostics as frozen
from pyages.calibration.methods.mh import diagnostics as canonical


def test_frozen_and_canonical_diagnostics_agree_on_mixing_classification() -> None:
    """Both formulas must distinguish mixed chains from a shifted chain."""
    rng = np.random.default_rng(20_260_902)
    mixed = rng.normal(size=(4, 2_000))
    shifted = mixed.copy()
    shifted[0] += 2.0

    assert frozen.split_rhat(mixed) < 1.01
    assert canonical.split_rhat(mixed) < 1.01
    assert frozen.split_rhat(shifted) > 1.1
    assert canonical.split_rhat(shifted) > 1.1
    assert frozen.effective_sample_size(mixed) > 1_000
    assert canonical.ess(mixed) > 1_000


def test_frozen_summary_keeps_registered_parameter_columns() -> None:
    """Extraction must preserve the table consumed by the reproduction report."""
    chains = np.arange(4 * 20 * 3, dtype=float).reshape(4, 20, 3)

    summary = frozen.summarize_chains(chains, "temporal")

    assert summary["parameter"].tolist() == ["mu", "sigma", "t0", "mu_plus_t0"]
    assert set(("experiment", "mean", "median", "sd", "q05", "q95")) <= set(
        summary.columns
    )
