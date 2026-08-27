# Copyright (c) 2021-2026 Centre national de la recherche scientifique (CNRS)
# Contributor: Jean-Raynald de Dreuzy
# SPDX-License-Identifier: CECILL-2.1

"""Posterior predictions must preserve complete parameter rows."""

from __future__ import annotations

import pandas as pd

from pyages.lpm import build_lpm
from pyages.lpm.samples.analysis import select_model_realizations


def _encoded_posterior() -> pd.DataFrame:
    # Each valid row satisfies shift == 10 * mu. Any cross-row pairing breaks it.
    return pd.DataFrame(
        {
            "mu": [1.0, 2.0, 3.0, 4.0],
            "shift": [10.0, 20.0, 30.0, 40.0],
        }
    )


def test_span_posterior_selection_keeps_mu_shift_pairing() -> None:
    model = build_lpm("exp_shifted")
    before = model.p.copy()

    selected, pdf, statistics = select_model_realizations(
        model,
        _encoded_posterior(),
        count=40,
        resolution=50,
    )

    assert len(selected) == 40
    assert pdf.columns[0] == "t"
    assert all(name[1:].isdigit() for name in pdf.columns[1:])
    assert statistics.notna().all().all()
    assert all(item.p["shift"] == 10.0 * item.p["mu"] for item in selected)
    assert model.p == before
