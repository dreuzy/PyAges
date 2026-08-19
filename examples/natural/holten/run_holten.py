# -*- coding: utf-8 -*-
"""
Launcher/orchestrator for the Holten benchmark workflow.
"""

from __future__ import annotations

import argparse
from pathlib import Path

import pandas as pd
from pyage.config.paths import ROOT_DIRECTORY_RESULTS

from examples.natural.holten.holten_benchmark import (
    build_article_reference_figures,
    build_pre_model_figures,
    build_reference_comparison_figures,
    compare_with_reference_results,
    write_benchmark_summary,
)
from examples.natural.holten.holten_case import PreparedHoltenCase, build_context, write_well_launcher_config
from examples.natural.holten.holten_four_bin import run_local_4bin, run_local_4bin_mh
from examples.natural.holten.holten_prepare import prepare_holten_inputs


def _lpm_ready(context) -> bool:
    params_path = context.paths.lpm_data_dir / context.lpm_name / "params.yaml"
    return bool(context.lpm_name) and params_path.exists()


def existing_results_for_wells(prepared) -> dict[str, Path]:
    results: dict[str, Path] = {}
    base = ROOT_DIRECTORY_RESULTS / "test_cases"
    for well_id in prepared.context.selected_wells:
        result_dir = base / f"holten_2010_{well_id}.txt"
        if result_dir.exists():
            results[well_id] = result_dir
    return results


def run_launcher_for_wells(prepared, inline: bool = False) -> dict[str, Path]:
    from scripts.launcher import run_workflow

    if not _lpm_ready(prepared.context):
        return {}

    results: dict[str, Path] = {}
    prepared.context.paths.launcher_config_dir.mkdir(parents=True, exist_ok=True)
    for well_id in prepared.context.selected_wells:
        config_path = write_well_launcher_config(prepared.context, well_id)
        results[well_id] = Path(run_workflow(str(config_path), force_inline=inline))
    return results


def write_prepared_artifacts(prepared: PreparedHoltenCase, output_dir: Path) -> None:
    prepared_dir = output_dir / "prepared"
    tracer_dir = prepared_dir / "tracer_histories"
    wells_dir = prepared_dir / "wells"
    prepared_dir.mkdir(parents=True, exist_ok=True)
    tracer_dir.mkdir(parents=True, exist_ok=True)
    wells_dir.mkdir(parents=True, exist_ok=True)

    prepared.preparation_log.to_csv(prepared_dir / "preparation_log.txt", sep="\t", index=False)
    prepared.observed_aggregated.to_csv(prepared_dir / "holten_2010_selected_wells.txt", sep="\t", index=False)
    prepared.helium_diagnostics.to_csv(prepared_dir / "helium_diagnostics.txt", sep="\t", index=False)
    for well_id, frame in prepared.observed_by_well.items():
        frame.to_csv(wells_dir / f"holten_{well_id}.txt", sep="\t", index=False)
    for tracer_name, frame in prepared.tracer_histories.items():
        frame.to_csv(tracer_dir / f"{tracer_name}_local_prepared.txt", sep="\t", index=False)


def _selected_wells_from_args(config_path: Path, wells_arg: str) -> list[str]:
    context = build_context(config_path)
    if not wells_arg.strip():
        return list(context.selected_wells)
    return [item.strip() for item in wells_arg.split(",") if item.strip()]


def _prepare_case(config_path: Path, selected_wells: list[str]) -> PreparedHoltenCase:
    prepared = prepare_holten_inputs(config_path)
    if selected_wells != prepared.context.selected_wells:
        prepared = prepared.subset(selected_wells)
    return prepared


def _ensure_prepared(
    prepared: PreparedHoltenCase | None,
    config_path: Path,
    selected_wells: list[str],
) -> PreparedHoltenCase:
    return prepared if prepared is not None else _prepare_case(config_path, selected_wells)


def _ensure_local_4bin_summary(
    prepared: PreparedHoltenCase,
    local_4bin_summary: pd.DataFrame | None,
) -> pd.DataFrame:
    if local_4bin_summary is not None:
        return local_4bin_summary
    _, summary, _, _ = run_local_4bin(prepared, prepared.context.paths.benchmark_dir / "four_bin")
    return summary


def _ensure_local_4bin_mh(prepared: PreparedHoltenCase, already_run: bool) -> bool:
    if already_run:
        return True
    run_local_4bin_mh(prepared, prepared.context.paths.benchmark_dir / "four_bin")
    return True


def _run_prepare_phase(
    prepared: PreparedHoltenCase,
    local_4bin_summary: pd.DataFrame | None,
    local_4bin_mh_done: bool,
) -> tuple[pd.DataFrame, bool]:
    benchmark_root = prepared.context.paths.benchmark_dir
    write_prepared_artifacts(prepared, benchmark_root)
    build_pre_model_figures(prepared, benchmark_root / "pre_model")
    try:
        build_article_reference_figures(prepared.context, benchmark_root / "article_reference")
    except Exception as exc:
        print(f"Article figure extraction skipped: {exc}")
    local_4bin_summary = _ensure_local_4bin_summary(prepared, local_4bin_summary)
    local_4bin_mh_done = _ensure_local_4bin_mh(prepared, local_4bin_mh_done)
    return local_4bin_summary, local_4bin_mh_done


def _run_calibration_phase(prepared: PreparedHoltenCase) -> dict[str, Path]:
    if prepared.context.launcher_enabled and _lpm_ready(prepared.context):
        if not prepared.context.generate_per_well_files:
            raise ValueError(
                "Holten calibration launcher requires "
                "`holten.preparation.generate_per_well_files: true` "
                "because each launcher job reads a per-well dataset file."
            )
        return run_launcher_for_wells(prepared, inline=prepared.context.launcher_inline)
    print("Launcher skipped: local LPM parameters are not ready or launcher disabled.")
    return existing_results_for_wells(prepared)


def _run_compare_phase(
    prepared: PreparedHoltenCase,
    results_by_well: dict[str, Path],
    local_4bin_summary: pd.DataFrame | None,
) -> None:
    local_4bin_summary = _ensure_local_4bin_summary(prepared, local_4bin_summary)
    if not results_by_well:
        results_by_well = existing_results_for_wells(prepared)
    comparison = compare_with_reference_results(
        prepared,
        results_by_well=results_by_well,
        local_4bin_summary=local_4bin_summary,
    )
    build_reference_comparison_figures(prepared, comparison, prepared.context.paths.benchmark_dir / "benchmark")
    write_benchmark_summary(comparison, prepared.context.paths.benchmark_dir / "benchmark")
    print(prepared.context.paths.benchmark_dir)


def main() -> None:
    parser = argparse.ArgumentParser(description="Run the Holten benchmark workflow.")
    parser.add_argument("--config", default=str(Path(__file__).resolve().parent / "holten.yaml"))
    parser.add_argument(
        "--mode",
        choices=("full", "prepare_only", "calibration_only", "compare_only"),
        default="full",
    )
    parser.add_argument(
        "--wells",
        default="",
        help="Optional comma-separated subset of wells to run.",
    )
    args = parser.parse_args()

    config_path = Path(args.config)
    selected_wells = _selected_wells_from_args(config_path, args.wells)

    prepared: PreparedHoltenCase | None = None
    results_by_well: dict[str, Path] = {}
    local_4bin_summary: pd.DataFrame | None = None
    local_4bin_mh_done = False

    if args.mode in ("full", "prepare_only"):
        prepared = _ensure_prepared(prepared, config_path, selected_wells)
        local_4bin_summary, local_4bin_mh_done = _run_prepare_phase(
            prepared,
            local_4bin_summary,
            local_4bin_mh_done,
        )

    if args.mode in ("full", "calibration_only"):
        prepared = _ensure_prepared(prepared, config_path, selected_wells)
        results_by_well = _run_calibration_phase(prepared)

    if args.mode in ("full", "compare_only"):
        prepared = _ensure_prepared(prepared, config_path, selected_wells)
        _run_compare_phase(prepared, results_by_well, local_4bin_summary)


if __name__ == "__main__":
    main()
