# -*- coding: utf-8 -*-
"""
Smoke tests for the refactored Fontainebleau example helpers.
"""

from pathlib import Path

from examples.natural.fontainebleau.fontainebleau_benchmark import (
    prepare_fontainebleau_case,
)
from examples.natural.fontainebleau.fontainebleau_case import (
    build_context,
    build_effective_config,
    write_effective_config,
)
from pyage.workflows.single_date_config import load_params

CONFIG_PATH = (
    Path(__file__).resolve().parents[2]
    / "examples"
    / "natural"
    / "fontainebleau"
    / "exemple_fontainebleau.yaml"
)


def test_fontainebleau_context_smoke():
    context = build_context(CONFIG_PATH)

    assert context.dataset_path.exists()
    assert context.params.dataset_name == "fontainebleau_CGEB"
    assert context.params.lpm_model_name == "dirac_double"
    assert "fontainebleau_CGEB" in context.available_datasets
    assert "dirac_double" in context.available_lpm_models


def test_fontainebleau_effective_config_override():
    payload = build_effective_config(
        CONFIG_PATH,
        dataset_name="fontainebleau_IMR",
        lpm_model_name="ig",
        mh_nstep=123,
    )

    assert payload["dataset"]["name"] == "fontainebleau_IMR"
    assert payload["dataset"]["label"] == "Fontainebleau IMR"
    assert payload["lpm"]["model_name"] == "ig"
    assert payload["calibration_metropolis_hastings"]["nstep"] == 123


def test_fontainebleau_write_effective_config_smoke(tmp_path):
    context = build_context(CONFIG_PATH)
    out_path = write_effective_config(
        context,
        output_path=tmp_path / "fontainebleau_override.yaml",
        dataset_name="fontainebleau_IMR",
        lpm_model_name="ig",
        mh_nstep=321,
    )
    params = load_params(context.paths.repo_root, out_path)

    assert out_path.exists()
    assert params.dataset_name == "fontainebleau_IMR"
    assert params.lpm_model_name == "ig"
    assert params.mh_nstep == 321


def test_prepare_fontainebleau_case_smoke():
    prepared = prepare_fontainebleau_case(CONFIG_PATH)

    assert prepared.selected_observations.shape[0] == 4
    assert set(prepared.selected_observations["element"]) == {
        "kr85",
        "3H",
        "39Ar",
        "14C",
    }
    assert prepared.dataset_summary["dataset_name"].nunique() >= 1
    assert "fontainebleau_CGEB" in prepared.dataset_summary["dataset_name"].tolist()
    assert set(prepared.tracer_summary["element"]) == {"kr85", "3H", "39Ar", "14C"}
