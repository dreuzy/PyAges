# Copyright (c) 2021-2026 Centre national de la recherche scientifique (CNRS)
# Contributor: Jean-Raynald de Dreuzy
# SPDX-License-Identifier: CECILL-2.1

from __future__ import annotations

import os
from pathlib import Path
from shutil import copy2, copytree
from typing import Any

os.environ.setdefault("MPLBACKEND", "Agg")

import matplotlib
import numpy as np
import pandas as pd
import pytest

matplotlib.use("Agg")

from examples.natural.holten import holten_case as holten_case_module
from examples.natural.holten.holten_benchmark import compare_with_reference_results
from examples.natural.holten.holten_case import HoltenPaths
from examples.natural.holten.holten_four_bin import (
    FRACTION_COLUMNS,
    LOCAL_4BIN_TRACER_ORDER,
    run_local_4bin,
    run_local_4bin_mh,
)
from examples.natural.holten.holten_prepare import prepare_holten_inputs

SOURCE_EXAMPLE_DIR = (
    Path(__file__).resolve().parents[2] / "examples" / "natural" / "holten"
)
SOURCE_CORE_TRACER_DIR = (
    Path(__file__).resolve().parents[2] / "data_core" / "data_tracer" / "39Ar"
)
EXPECTED_SELECTED_WELLS = [
    "59-05",
    "67-19",
    "72-22",
    "73-29",
    "85-33",
    "85-34",
    "85-35",
]
EXPECTED_PRE_MODEL_FIGURES = {
    "helium_3h3he_diagnostic_panel.png",
    "helium_ratio_age_check.png",
    "tracer_39Ar_history_and_observations.png",
    "tracer_39Ar_value_range_position.png",
    "tracer_3H_history_and_observations.png",
    "tracer_3H_value_range_position.png",
    "tracer_kr85_history_and_observations.png",
    "tracer_kr85_value_range_position.png",
    "well_59-05_multi_tracer_panel.png",
    "well_67-19_multi_tracer_panel.png",
    "well_72-22_multi_tracer_panel.png",
    "well_73-29_multi_tracer_panel.png",
    "well_85-33_multi_tracer_panel.png",
    "well_85-34_multi_tracer_panel.png",
    "well_85-35_multi_tracer_panel.png",
}


def _copy_example_tree(repo_root: Path) -> Path:
    example_dir = repo_root / "examples" / "natural" / "holten"
    core_tracer_dir = repo_root / "data_core" / "data_tracer"
    example_dir.mkdir(parents=True, exist_ok=True)
    core_tracer_dir.mkdir(parents=True, exist_ok=True)
    copy2(SOURCE_EXAMPLE_DIR / "holten.yaml", example_dir / "holten.yaml")
    copytree(SOURCE_EXAMPLE_DIR / "doc", example_dir / "doc")
    copytree(SOURCE_EXAMPLE_DIR / "tracers", example_dir / "tracers")
    copytree(SOURCE_EXAMPLE_DIR / "data_lpm", example_dir / "data_lpm")
    copytree(SOURCE_CORE_TRACER_DIR, core_tracer_dir / "39Ar")
    (example_dir / "data").mkdir(parents=True, exist_ok=True)
    (example_dir / "generated").mkdir(parents=True, exist_ok=True)
    return example_dir


def _sandboxed_paths(
    example_dir: Path, repo_root: Path, config_path: Path | None = None
) -> HoltenPaths:
    yaml_path = (
        Path(config_path) if config_path is not None else (example_dir / "holten.yaml")
    )
    data_dir = example_dir / "data"
    doc_dir = example_dir / "doc"
    generated_dir = example_dir / "generated"
    launcher_config_dir = generated_dir / "launcher_configs"
    tracer_source_dir = example_dir / "tracers"
    prepared_tracer_dir = example_dir / "prepared_tracers" / "data_tracer"
    lpm_data_dir = example_dir / "data_lpm"
    benchmark_dir = generated_dir / "benchmark"
    return HoltenPaths(
        repo_root=repo_root,
        example_dir=example_dir,
        data_dir=data_dir,
        doc_dir=doc_dir,
        generated_dir=generated_dir,
        launcher_config_dir=launcher_config_dir,
        tracer_source_dir=tracer_source_dir,
        prepared_tracer_dir=prepared_tracer_dir,
        lpm_data_dir=lpm_data_dir,
        yaml_path=yaml_path,
        sampling_raw_path=doc_dir / "sampling_data.txt",
        tritium_raw_path=doc_dir / "local_tritium.txt",
        kr85_raw_path=doc_dir / "freiburg_krypton.txt",
        reference_results_path=doc_dir / "calibration_results.txt",
        aggregated_dataset_path=data_dir / "holten_2010_selected_wells.txt",
        benchmark_dir=benchmark_dir,
    )


def _round_float(value: float, ndigits: int = 8) -> float:
    return float(np.round(value, ndigits))


def _normalize_value(value: Any) -> Any:
    if value is None:
        return None
    if isinstance(value, np.generic):
        value = value.item()
    if pd.isna(value):
        return None
    if isinstance(value, float):
        return _round_float(value)
    return value


def frame_records(
    frame: pd.DataFrame,
    *,
    columns: list[str],
    sort_by: list[str],
    order_map: dict[str, int] | None = None,
) -> list[dict[str, Any]]:
    payload = frame.loc[:, columns].copy()
    if order_map is not None:
        for column_name, mapping in order_map.items():
            helper = f"__order_{column_name}"
            payload[helper] = payload[column_name].map(mapping)
            sort_by = [helper if key == column_name else key for key in sort_by]
    payload = payload.sort_values(sort_by).reset_index(drop=True)
    payload = payload.drop(
        columns=[col for col in payload.columns if col.startswith("__order_")],
        errors="ignore",
    )
    records: list[dict[str, Any]] = []
    for _, row in payload.iterrows():
        records.append({column: _normalize_value(row[column]) for column in columns})
    return records


def history_summary(history: pd.DataFrame) -> dict[str, Any]:
    conc = history["concentration"].astype(float)
    summary = {
        "count": int(len(history)),
        "date_min": _round_float(float(history["date"].min())),
        "date_max": _round_float(float(history["date"].max())),
        "concentration_min": _round_float(float(conc.min())),
        "concentration_median": _round_float(float(conc.median())),
        "concentration_max": _round_float(float(conc.max())),
    }
    if "error" in history.columns:
        err = pd.to_numeric(history["error"], errors="coerce").dropna()
        if not err.empty:
            summary["error_median"] = _round_float(float(err.median()))
    return summary


def build_prepare_record(prepared) -> dict[str, Any]:
    helium_columns = [
        "well_id",
        "date",
        "3He_err_source",
        "3He_err",
        "tritium_initial_TU",
        "tritium_initial_err",
        "H3_He_age_yr",
        "H3_He_age_ratio_yr",
        "H3_He_age_ratio_delta_yr",
        "He4_terr",
        "DeltaNe_pct",
        "DeltaNe_screening",
    ]
    return {
        "selected_wells": list(prepared.context.selected_wells),
        "calibration_tracers": list(prepared.context.calibration_tracers),
        "observed_aggregated": frame_records(
            prepared.observed_aggregated,
            columns=["well_id", "element", "concentration", "error", "unit", "date"],
            sort_by=["well_id", "element"],
        ),
        "preparation_log": frame_records(
            prepared.preparation_log,
            columns=[
                "well_id",
                "element",
                "raw_value",
                "raw_unit",
                "converted_value",
                "converted_unit",
                "conversion_rule",
                "source_field",
            ],
            sort_by=["well_id", "element"],
        ),
        "helium_diagnostics": frame_records(
            prepared.helium_diagnostics,
            columns=helium_columns,
            sort_by=["well_id"],
        ),
        "tracer_histories": {
            tracer_name: history_summary(history)
            for tracer_name, history in sorted(prepared.tracer_histories.items())
        },
    }


def build_local_4bin_record(outputs: dict[str, Any]) -> dict[str, Any]:
    endmember_order = {
        "tracer": {name: idx for idx, name in enumerate(LOCAL_4BIN_TRACER_ORDER)}
    }
    return {
        "endmembers": frame_records(
            outputs["endmembers"],
            columns=[
                "tracer",
                "bin_name",
                "representative_age",
                "concentration",
                "unit",
            ],
            sort_by=["tracer", "bin_name"],
            order_map=endmember_order,
        ),
        "summary": frame_records(
            outputs["summary"],
            columns=[
                "well_id",
                "n_observations_local_4bin",
                "tracers_local_4bin",
                *FRACTION_COLUMNS,
                "chi2_local_4bin",
                "rmse_local_4bin",
                "weighted_rmse_local_4bin",
                "mean_age_local_4bin",
                "optimization_success",
            ],
            sort_by=["well_id"],
        ),
        "fit": frame_records(
            outputs["fit"],
            columns=[
                "well_id",
                "tracer",
                "unit",
                "observed",
                "error",
                "modeled",
                "residual",
                "weighted_residual",
            ],
            sort_by=["well_id", "tracer"],
            order_map=endmember_order,
        ),
    }


def build_local_4bin_mh_record(outputs: dict[str, Any]) -> dict[str, Any]:
    posterior_columns = [
        "well_id",
        "nsamples",
        "acceptance_rate_mean",
        *[f"{fraction}_q10" for fraction in FRACTION_COLUMNS],
        *[f"{fraction}_median" for fraction in FRACTION_COLUMNS],
        *[f"{fraction}_q90" for fraction in FRACTION_COLUMNS],
        "mean_age_local_4bin_median",
        "chi2_local_4bin_median",
    ]
    return {
        "paper_reference": frame_records(
            outputs["paper"],
            columns=["well_id", *FRACTION_COLUMNS],
            sort_by=["well_id"],
        ),
        "posterior": frame_records(
            outputs["posterior"],
            columns=posterior_columns,
            sort_by=["well_id"],
        ),
        "paper_vs_mh": frame_records(
            outputs["comparison"],
            columns=[
                "well_id",
                *[f"{fraction}_paper" for fraction in FRACTION_COLUMNS],
                *[f"{fraction}_posterior_q10" for fraction in FRACTION_COLUMNS],
                *[f"{fraction}_posterior_median" for fraction in FRACTION_COLUMNS],
                *[f"{fraction}_posterior_q90" for fraction in FRACTION_COLUMNS],
            ],
            sort_by=["well_id"],
        ),
    }


def build_reference_comparison_record(comparison: pd.DataFrame) -> list[dict[str, Any]]:
    return frame_records(
        comparison,
        columns=[
            "well_id",
            "reference_4bin_chi2",
            "reference_4bin_pchi2",
            "reference_best_model",
            "local_4bin_chi2",
            "local_4bin_rmse",
            "local_4bin_mean_age",
            "local_4bin_f_0_20",
            "local_4bin_f_20_40",
            "local_4bin_f_40_60",
            "local_4bin_f_old",
            "calibration_available",
        ],
        sort_by=["well_id"],
    )


def assert_nested_close(
    actual: Any,
    expected: Any,
    *,
    tol: float = 1e-4,
    atol: float = 0.0,
    path: str = "root",
) -> None:
    if isinstance(actual, dict) and isinstance(expected, dict):
        assert actual.keys() == expected.keys(), f"{path}: keys mismatch"
        for key in actual:
            assert_nested_close(
                actual[key],
                expected[key],
                tol=tol,
                atol=atol,
                path=f"{path}.{key}",
            )
        return
    if isinstance(actual, list) and isinstance(expected, list):
        assert len(actual) == len(expected), f"{path}: list length mismatch"
        for idx, (actual_item, expected_item) in enumerate(
            zip(actual, expected, strict=False)
        ):
            assert_nested_close(
                actual_item,
                expected_item,
                tol=tol,
                atol=atol,
                path=f"{path}[{idx}]",
            )
        return
    if isinstance(actual, (int, float)) and isinstance(expected, (int, float)):
        assert np.isclose(actual, expected, atol=atol, rtol=tol), (
            f"{path}: {actual} != {expected} (rtol={tol}, atol={atol})"
        )
        return
    assert actual == expected, f"{path}: {actual!r} != {expected!r}"


@pytest.fixture(scope="module")
def holten_sandbox(tmp_path_factory):
    repo_root = tmp_path_factory.mktemp("holten_repo") / "repo"
    example_dir = _copy_example_tree(repo_root)
    config_path = example_dir / "holten.yaml"

    def _resolve_paths(config_path_override: Path | None = None) -> HoltenPaths:
        return _sandboxed_paths(example_dir, repo_root, config_path_override)

    monkeypatch = pytest.MonkeyPatch()
    monkeypatch.setattr(holten_case_module, "resolve_paths", _resolve_paths)
    try:
        yield {
            "repo_root": repo_root,
            "example_dir": example_dir,
            "config_path": config_path,
        }
    finally:
        monkeypatch.undo()


@pytest.fixture(scope="module")
def prepared_holten_case(holten_sandbox):
    return prepare_holten_inputs(holten_sandbox["config_path"])


@pytest.fixture(scope="module")
def local_4bin_outputs(prepared_holten_case, holten_sandbox):
    output_dir = holten_sandbox["example_dir"] / "generated" / "benchmark" / "four_bin"
    endmembers, summary, fit_df, paths = run_local_4bin(
        prepared_holten_case, output_dir
    )
    return {
        "endmembers": endmembers,
        "summary": summary,
        "fit": fit_df,
        "paths": paths,
    }


@pytest.fixture(scope="module")
def local_4bin_mh_outputs(prepared_holten_case, holten_sandbox):
    output_dir = holten_sandbox["example_dir"] / "generated" / "benchmark" / "four_bin"
    paper, posterior, comparison, paths = run_local_4bin_mh(
        prepared_holten_case,
        output_dir,
        nstep=600,
        burn_in=0.2,
        proposal_scale=0.18,
        seed=12345,
    )
    return {
        "paper": paper,
        "posterior": posterior,
        "comparison": comparison,
        "paths": paths,
    }


@pytest.fixture(scope="module")
def reference_comparison(prepared_holten_case, local_4bin_outputs):
    return compare_with_reference_results(
        prepared_holten_case,
        results_by_well={},
        local_4bin_summary=local_4bin_outputs["summary"],
    )
