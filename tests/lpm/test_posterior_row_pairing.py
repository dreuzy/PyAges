"""Posterior predictions must preserve complete parameter rows."""

from __future__ import annotations

import pandas as pd

from pyage.lpm.distribution_analysis import select_models
from pyage.lpm.lpm_build import lpm_build


def _encoded_posterior() -> pd.DataFrame:
    # Each valid row satisfies shift == 10 * mu. Any cross-row pairing breaks it.
    return pd.DataFrame(
        {
            "mu": [1.0, 2.0, 3.0, 4.0],
            "shift": [10.0, 20.0, 30.0, 40.0],
        }
    )


def test_span_posterior_selection_keeps_mu_shift_pairing() -> None:
    model = lpm_build("exp_shifted")

    selected, _, statistics = select_models(
        model,
        _encoded_posterior(),
        count=40,
        resolution=50,
    )

    assert len(selected) == 40
    assert statistics.notna().all().all()
    assert all(item.p["shift"] == 10.0 * item.p["mu"] for item in selected)
