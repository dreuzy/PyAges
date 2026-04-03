# -*- coding: utf-8 -*-
"""
Launcher/orchestrator for the Holten benchmark workflow.
"""

from __future__ import annotations

import argparse
from contextlib import contextmanager
import copy
from pathlib import Path
import sys
from typing import Iterator

try:
    from pyage.config.bootstrap import ensure_repo_imports
except ModuleNotFoundError:
    repo_root = Path(__file__).resolve().parents[3]
    sys.path.insert(0, str(repo_root))
    from pyage.config.bootstrap import ensure_repo_imports


ensure_repo_imports()

from holten_benchmark import (
    build_article_reference_figures,
    build_pre_model_figures,
    build_reference_comparison_figures,
    compare_with_reference_results,
    write_benchmark_summary,
)
from holten_case import build_context, dump_yaml
from holten_four_bin import run_local_4bin
from holten_prepare import prepare_holten_inputs


@contextmanager
def patched_tracer_directory(tracer_dir: Path) -> Iterator[None]:
    import pyage.config.paths as cfg_paths
    import pyage.global_parameters as gp
    from pyage.config.context import get_default_context, set_default_context

    old_gp = gp.DIRECTORY_TRACER_DATA
    old_cfg = cfg_paths.DIRECTORY_TRACER_DATA
    old_ctx = get_default_context()
    tracer_dir = tracer_dir.resolve()
    gp.DIRECTORY_TRACER_DATA = tracer_dir
    cfg_paths.DIRECTORY_TRACER_DATA = tracer_dir
    set_default_context(old_ctx.with_tracer_dir(tracer_dir))
    try:
        yield
    finally:
        gp.DIRECTORY_TRACER_DATA = old_gp
        cfg_paths.DIRECTORY_TRACER_DATA = old_cfg
        set_default_context(old_ctx)


def _lpm_ready(context) -> bool:
    params_path = context.paths.lpm_data_dir / context.lpm_name / "params.yaml"
    return bool(context.lpm_name) and params_path.exists()


def _launcher_yaml_for_well(context, well_id: str) -> Path:
    payload = copy.deepcopy(context.config)
    payload["dataset"] = {
        "name": f"holten_2010_{well_id}.txt",
        "label": f"Holten {well_id}",
        "year": 2010,
        "data_dir": str(context.paths.data_dir.relative_to(context.paths.repo_root)),
        "verbose": True,
    }
    out_path = context.paths.launcher_config_dir / f"holten_{well_id}_launcher.yaml"
    dump_yaml(out_path, payload)
    return out_path


def existing_results_for_wells(prepared) -> dict[str, Path]:
    import pyage.global_parameters as gp

    results: dict[str, Path] = {}
    base = Path(gp.ROOT_DIRECTORY_RESULTS) / "test_cases"
    for well_id in prepared.context.selected_wells:
        result_dir = base / f"holten_2010_{well_id}.txt"
        if result_dir.exists():
            results[well_id] = result_dir
    return results


def run_launcher_for_wells(prepared, inline: bool = False) -> dict[str, Path]:
    import scripts.launcher as launcher

    if not _lpm_ready(prepared.context):
        return {}

    results: dict[str, Path] = {}
    prepared.context.paths.launcher_config_dir.mkdir(parents=True, exist_ok=True)
    with patched_tracer_directory(prepared.context.paths.prepared_tracer_dir):
        for well_id in prepared.context.selected_wells:
            config_path = _launcher_yaml_for_well(prepared.context, well_id)
            results[well_id] = Path(launcher.main(str(config_path), force_inline=inline))
    return results


def write_prepared_artifacts(prepared, output_dir: Path) -> None:
    prepared_dir = output_dir / "prepared"
    tracer_dir = prepared_dir / "tracer_histories"
    wells_dir = prepared_dir / "wells"
    prepared_dir.mkdir(parents=True, exist_ok=True)
    tracer_dir.mkdir(parents=True, exist_ok=True)
    wells_dir.mkdir(parents=True, exist_ok=True)

    prepared.preparation_log.to_csv(prepared_dir / "preparation_log.txt", sep="\t", index=False)
    prepared.observed_aggregated.to_csv(prepared_dir / "holten_2010_selected_wells.txt", sep="\t", index=False)
    for well_id, frame in prepared.observed_by_well.items():
        frame.to_csv(wells_dir / f"holten_{well_id}.txt", sep="\t", index=False)
    for tracer_name, frame in prepared.tracer_histories.items():
        frame.to_csv(tracer_dir / f"{tracer_name}_local_prepared.txt", sep="\t", index=False)


def _subset_prepared(prepared, selected_wells: list[str]):
    prepared.context = copy.copy(prepared.context)
    object.__setattr__(prepared.context, "selected_wells", selected_wells)
    prepared.observed_aggregated = prepared.observed_aggregated.loc[
        prepared.observed_aggregated["well_id"].isin(selected_wells)
    ].reset_index(drop=True)
    prepared.observed_by_well = {
        well_id: frame for well_id, frame in prepared.observed_by_well.items() if well_id in selected_wells
    }
    prepared.preparation_log = prepared.preparation_log.loc[
        prepared.preparation_log["well_id"].isin(selected_wells)
    ].reset_index(drop=True)
    return prepared


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

    context = build_context(Path(args.config))
    selected_wells = context.selected_wells
    if args.wells.strip():
        selected_wells = [item.strip() for item in args.wells.split(",") if item.strip()]

    prepared = None
    results_by_well: dict[str, Path] = {}
    local_4bin_summary = None

    if args.mode in ("full", "prepare_only"):
        prepared = prepare_holten_inputs(Path(args.config))
        if selected_wells != prepared.context.selected_wells:
            prepared = _subset_prepared(prepared, selected_wells)
        benchmark_root = prepared.context.paths.benchmark_dir
        write_prepared_artifacts(prepared, benchmark_root)
        build_pre_model_figures(prepared, benchmark_root / "pre_model")
        try:
            build_article_reference_figures(prepared.context, benchmark_root / "article_reference")
        except RuntimeError as exc:
            print(f"Article figure extraction skipped: {exc}")
        _, local_4bin_summary, _, _ = run_local_4bin(prepared, benchmark_root / "four_bin")

    if args.mode in ("full", "calibration_only"):
        if prepared is None:
            prepared = prepare_holten_inputs(Path(args.config))
            if selected_wells != prepared.context.selected_wells:
                prepared = _subset_prepared(prepared, selected_wells)
        if local_4bin_summary is None:
            _, local_4bin_summary, _, _ = run_local_4bin(prepared, prepared.context.paths.benchmark_dir / "four_bin")
        if prepared.context.launcher_enabled and _lpm_ready(prepared.context):
            inline = bool(prepared.context.config.get("holten", {}).get("launcher", {}).get("inline", False))
            results_by_well = run_launcher_for_wells(prepared, inline=inline)
        else:
            print("Launcher skipped: local LPM parameters are not ready or launcher disabled.")
            results_by_well = existing_results_for_wells(prepared)

    if args.mode in ("full", "prepare_only", "compare_only", "calibration_only"):
        if prepared is None:
            prepared = prepare_holten_inputs(Path(args.config))
            if selected_wells != prepared.context.selected_wells:
                prepared = _subset_prepared(prepared, selected_wells)
        if local_4bin_summary is None:
            _, local_4bin_summary, _, _ = run_local_4bin(prepared, prepared.context.paths.benchmark_dir / "four_bin")
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


if __name__ == "__main__":
    main()
