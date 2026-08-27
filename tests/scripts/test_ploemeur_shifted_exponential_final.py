# Copyright (c) 2021-2026 Centre national de la recherche scientifique (CNRS)
# Contributor: Jean-Raynald de Dreuzy
# SPDX-License-Identifier: CECILL-2.1

from types import SimpleNamespace

import pandas as pd
import pytest

from scripts import run_ploemeur_shifted_exponential_final as runner


def test_tracer_fit_preserves_duplicate_observations_and_float_roundtrip(
    monkeypatch, tmp_path
):
    case = runner.Case("case", "F11", "full_record", None)
    observations = pd.DataFrame(
        {
            "element": ["cfc11", "cfc11"],
            "date": [2004.704918032787, 2004.704918032787],
            "concentration": [8.0, 12.0],
            "error": [2.0, 2.0],
        }
    )
    intervals = pd.DataFrame(
        {
            "well": ["F11"],
            "calibration": ["full_record"],
            "tracer": ["cfc11"],
            "date": [2004.7049180327872],
            "median": [10.0],
        }
    )
    monkeypatch.setattr(runner, "CASES", (case,))
    monkeypatch.setattr(runner, "TRACERS", ("cfc11",))
    monkeypatch.setattr(
        runner, "_observations", lambda unused_case: SimpleNamespace(frame=observations)
    )

    result = runner._tracer_fit_diagnostics(tmp_path, intervals)

    assert result.loc[0, "observations"] == 2
    assert result.loc[0, "posterior_median_normalized_RMSE"] == pytest.approx(1.0)
    assert (tmp_path / "tracer_fit_diagnostics.csv").is_file()
