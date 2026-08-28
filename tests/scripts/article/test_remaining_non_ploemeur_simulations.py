# Copyright (c) 2021-2026 Centre national de la recherche scientifique (CNRS)
# Contributor: Jean-Raynald de Dreuzy
# SPDX-License-Identifier: CECILL-2.1

from __future__ import annotations

import pandas as pd
import pytest

from scripts.article.run_remaining_non_ploemeur_simulations import (
    MCMC_LENGTHS,
    SHORT_SEEDS,
    _comparison_metrics,
)


def _summary_row(
    parameter: str, *, reference: bool, median: float, sd: float, width: float
):
    return {
        "case": "representative",
        "target_mu": 10.0,
        "target_t0": 10.0,
        "target_value": 20.0 if parameter == "mu_plus_t0" else 10.0,
        "steps": 10_000 if reference else 1_000,
        "seed": 12_345 if reference else SHORT_SEEDS[0],
        "is_reference": reference,
        "parameter": parameter,
        "median": median,
        "sd": sd,
        "q10": median - width / 2.0,
        "q90": median + width / 2.0,
    }


def test_mcmc_campaign_includes_actual_tenfold_and_hundredfold_lengths():
    assert MCMC_LENGTHS == (10_000, 5_000, 2_000, 1_000, 500, 100)
    assert len(set(SHORT_SEEDS)) == 5


def test_comparability_requires_position_and_dispersion_for_every_parameter():
    rows = []
    for parameter in ("mu", "t0", "mu_plus_t0"):
        reference_median = 20.0 if parameter == "mu_plus_t0" else 10.0
        rows.append(
            _summary_row(
                parameter,
                reference=True,
                median=reference_median,
                sd=2.0,
                width=4.0,
            )
        )
        rows.append(
            _summary_row(
                parameter,
                reference=False,
                median=reference_median + 0.1,
                sd=2.1,
                width=4.2,
            )
        )

    comparison = _comparison_metrics(pd.DataFrame(rows))

    assert comparison["parameter_pass"].all()
    assert comparison["sd_relative_difference"].max() == pytest.approx(0.05)
    assert comparison["width_relative_difference"].max() == pytest.approx(0.05)


def test_comparability_rejects_a_dispersion_mismatch_despite_matching_median():
    rows = []
    for parameter in ("mu", "t0", "mu_plus_t0"):
        reference_median = 20.0 if parameter == "mu_plus_t0" else 10.0
        rows.append(
            _summary_row(
                parameter,
                reference=True,
                median=reference_median,
                sd=2.0,
                width=4.0,
            )
        )
        rows.append(
            _summary_row(
                parameter,
                reference=False,
                median=reference_median,
                sd=3.0 if parameter == "mu" else 2.0,
                width=4.0,
            )
        )

    comparison = _comparison_metrics(pd.DataFrame(rows))

    mu = comparison.loc[comparison["parameter"] == "mu"].iloc[0]
    assert bool(mu["position_pass"])
    assert not bool(mu["sd_pass"])
    assert not bool(mu["parameter_pass"])
