# Copyright (c) 2021-2026 Centre national de la recherche scientifique (CNRS)
# Contributor: Jean-Raynald de Dreuzy
# SPDX-License-Identifier: CECILL-2.1

"""Focused contracts for temporal workflow preparation and orchestration."""

from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import Mock

import pandas as pd

from pyages.config.models import TemporalCalibrationCfg
from pyages.workflows import temporal


def test_temporal_mh_uses_an_explicit_fresh_seed_when_fixed_seed_is_disabled(
    monkeypatch,
) -> None:
    random_seed = Mock(return_value=987654321)
    monkeypatch.setattr(temporal.secrets, "randbits", random_seed)

    config = temporal._build_mh_config(TemporalCalibrationCfg(seed_enabled=False))

    assert config.seed == 987654321
    random_seed.assert_called_once_with(63)


def test_temporal_mh_preserves_an_enabled_fixed_seed(monkeypatch) -> None:
    random_seed = Mock(side_effect=AssertionError("fresh seed must not be requested"))
    monkeypatch.setattr(temporal.secrets, "randbits", random_seed)

    config = temporal._build_mh_config(
        TemporalCalibrationCfg(seed_enabled=True, seed=42)
    )

    assert config.seed == 42
    random_seed.assert_not_called()


def test_successive_date_labels_preserve_close_distinct_dates() -> None:
    observations = SimpleNamespace(
        frame=pd.DataFrame(
            {
                "element": ["cfc11", "cfc11"],
                "concentration": [1.0, 2.0],
                "error": [0.1, 0.2],
                "unit": ["pptv", "pptv"],
                "date": [2005.4300001, 2005.4300002],
            }
        )
    )

    labels = [
        label for label, _frame in temporal._case_frames(observations, "successive")
    ]

    assert labels == ["date_2005_4300001", "date_2005_4300002"]


def test_load_concentrations_resolves_errors_after_optional_override(
    tmp_path, monkeypatch
) -> None:
    dataset = tmp_path / "observations.txt"
    pd.DataFrame(
        {
            "element": ["cfc11", "cfc12"],
            "concentration": [10.0, 20.0],
            "error": [0.0, 5.0],
            "unit": ["pptv", "pptv"],
            "date": [2010.0, 2010.0],
        }
    ).to_csv(dataset, sep="\t", index=False)
    resolved = Mock()
    monkeypatch.setattr(temporal, "resolve_observation_errors", resolved)

    observations = temporal._load_concentrations(dataset, error_rel=0.2)

    assert observations.frame["error"].tolist() == [2.0, 4.0]
    resolved.assert_called_once_with(
        observations,
        missing_error_relative_fraction=0.01,
    )


def test_run_temporal_invalidates_manifest_and_writes_effective_observations(
    tmp_path, monkeypatch
) -> None:
    output = tmp_path / "results"
    output.mkdir()
    observations = SimpleNamespace(
        frame=pd.DataFrame(
            {
                "element": ["cfc11"],
                "concentration": [1.0],
                "error": [0.1],
                "unit": ["pptv"],
                "date": [2010.0],
            }
        ),
        observation_tracer_names=lambda: ["cfc11"],
        error_provenance=[],
    )
    context = SimpleNamespace(
        config_path=tmp_path / "config.yaml",
        dataset_path=tmp_path / "observations.txt",
        mode="span",
        models=["exp"],
        lpm_directory=tmp_path / "lpm",
        observations=observations,
        output_directory=output,
        params=SimpleNamespace(
            dataset=SimpleNamespace(error_rel=None, missing_error_rel=0.01),
            calibration=TemporalCalibrationCfg(seed_enabled=True, seed=1),
            figures=SimpleNamespace(),
        ),
    )
    begin = Mock()
    manifest = Mock()
    case_directory = output / "span_full"
    monkeypatch.setattr(temporal, "_prepare_context", lambda _path: context)
    monkeypatch.setattr(temporal, "begin_result_run", begin)
    monkeypatch.setattr(
        temporal,
        "_run_temporal_cases",
        lambda *_args, **_kwargs: [case_directory],
    )
    monkeypatch.setattr(temporal, "write_result_manifest", manifest)

    result = temporal.run_temporal(context.config_path)

    assert result == case_directory
    begin.assert_called_once_with(output)
    written = pd.read_table(output / "concentrations.txt")
    pd.testing.assert_frame_equal(written, observations.frame)
    assert manifest.call_args.kwargs["input_paths"][0] == context.dataset_path
    assert manifest.call_args.kwargs["details"]["observation_error_policy"] == {
        "error_rel": None,
        "missing_error_rel": 0.01,
        "transformations": [],
    }
