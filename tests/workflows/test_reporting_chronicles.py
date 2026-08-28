# Copyright (c) 2021-2026 Centre national de la recherche scientifique (CNRS)
# Contributor: Jean-Raynald de Dreuzy
# SPDX-License-Identifier: CECILL-2.1

"""Focused contracts for reporting concentration chronicles."""

from types import SimpleNamespace
from unittest.mock import Mock

import pandas as pd

from pyages.reporting import chronicles


def test_export_concentration_chronicles_uses_custom_tracer_directory(
    tmp_path, monkeypatch
) -> None:
    result_directory = tmp_path / "result"
    method_directory = result_directory / "Metropolis_Hastings"
    method_directory.mkdir(parents=True)
    (method_directory / "lpm_dist_calibrated.txt").write_text(
        "mu\n10\n", encoding="utf-8"
    )
    observations = SimpleNamespace(
        frame=pd.DataFrame({"date": [2010.0]}),
        unique_tracer_names=lambda: ["custom_tracer"],
    )
    tracers = Mock()
    tracer_factory = Mock(return_value=tracers)
    monkeypatch.setattr(
        chronicles.Concentrations,
        "from_file",
        Mock(return_value=observations),
    )
    monkeypatch.setattr(chronicles, "ConvolutionTracers", tracer_factory)
    monkeypatch.setattr(chronicles, "read_distribution", Mock(return_value=object()))
    monkeypatch.setattr(
        chronicles,
        "select_model_realizations",
        Mock(return_value=([], object(), object())),
    )
    monkeypatch.setattr(chronicles, "save_distributions_tables", Mock())
    tracer_data_dir = tmp_path / "custom_tracers"

    chronicles.export_concentration_chronicles(
        [result_directory],
        object(),
        SimpleNamespace(),
        tracer_data_dir=tracer_data_dir,
    )

    tracer_factory.assert_called_once_with(
        names=["custom_tracer"],
        date=2010.0,
        tracer_data_dir=tracer_data_dir,
    )
    tracers.validate_observation_units.assert_called_once_with(observations)
