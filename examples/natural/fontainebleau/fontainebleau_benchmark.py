# -*- coding: utf-8 -*-
"""
Pre-model figures and lightweight benchmark helpers for Fontainebleau.
"""

from __future__ import annotations

from pathlib import Path
import sys

import matplotlib.pyplot as plt
import pandas as pd

try:
    from pyage.config.bootstrap import ensure_repo_imports
except ModuleNotFoundError:
    repo_root = Path(__file__).resolve().parents[3]
    sys.path.insert(0, str(repo_root))
    from pyage.config.bootstrap import ensure_repo_imports


ensure_repo_imports()

try:
    from .fontainebleau_case import PreparedFontainebleauCase, build_context
except ImportError:
    from fontainebleau_case import PreparedFontainebleauCase, build_context


REQUIRED_COLUMNS = {"element", "concentration", "error", "unit", "date"}


def _validate_dataset_conventions(frame: pd.DataFrame, dataset_path: Path) -> None:
    ar39 = frame.loc[frame["element"] == "39Ar", "concentration"].astype(float)
    if not ar39.empty and ar39.max() > 10:
        raise ValueError(
            f"{dataset_path}: 39Ar values appear to still be in percent modern, "
            "not in fraction-of-modern storage."
        )


def read_dataset(dataset_path: Path) -> pd.DataFrame:
    frame = pd.read_csv(dataset_path, sep=r"\s+", engine="python")
    missing = REQUIRED_COLUMNS.difference(frame.columns)
    if missing:
        missing_text = ", ".join(sorted(missing))
        raise ValueError(f"{dataset_path}: missing required columns: {missing_text}")
    _validate_dataset_conventions(frame, dataset_path)
    return frame


def load_all_datasets(context=None) -> pd.DataFrame:
    ctx = context or build_context()
    frames: list[pd.DataFrame] = []
    for dataset_name in ctx.available_datasets:
        frame = read_dataset(ctx.params.dataset_data_dir / dataset_name).copy()
        frame.insert(0, "dataset_name", dataset_name)
        frame.insert(1, "site_code", dataset_name.removeprefix("fontainebleau_"))
        frame.insert(2, "selected", dataset_name == ctx.params.dataset_name)
        frames.append(frame)
    if not frames:
        return pd.DataFrame(columns=["dataset_name", "site_code", "selected", *sorted(REQUIRED_COLUMNS)])
    return pd.concat(frames, ignore_index=True)


def _build_dataset_summary(all_observations: pd.DataFrame) -> pd.DataFrame:
    grouped = all_observations.groupby(["dataset_name", "site_code", "selected"], sort=False)
    summary = grouped.agg(
        tracer_count=("element", "size"),
        tracers=("element", lambda values: ",".join(values.astype(str))),
        sampling_date=("date", "first"),
        mean_concentration=("concentration", "mean"),
        mean_error=("error", "mean"),
    )
    return summary.reset_index()


def _build_tracer_summary(all_observations: pd.DataFrame) -> pd.DataFrame:
    grouped = all_observations.groupby("element", sort=False)
    summary = grouped.agg(
        unit=("unit", "first"),
        dataset_count=("dataset_name", "nunique"),
        min_concentration=("concentration", "min"),
        median_concentration=("concentration", "median"),
        max_concentration=("concentration", "max"),
        mean_error=("error", "mean"),
    )
    return summary.reset_index()


def prepare_fontainebleau_case(config_path: Path | None = None) -> PreparedFontainebleauCase:
    context = build_context(config_path)
    selected_observations = read_dataset(context.dataset_path).copy()
    selected_observations.insert(0, "dataset_name", context.params.dataset_name)
    selected_observations.insert(1, "site_code", context.params.dataset_name.removeprefix("fontainebleau_"))
    all_observations = load_all_datasets(context)
    return PreparedFontainebleauCase(
        context=context,
        selected_observations=selected_observations,
        all_observations=all_observations,
        dataset_summary=_build_dataset_summary(all_observations),
        tracer_summary=_build_tracer_summary(all_observations),
    )


def write_prepared_tables(prepared: PreparedFontainebleauCase, output_dir: Path) -> list[Path]:
    output_dir.mkdir(parents=True, exist_ok=True)
    outputs = [
        output_dir / f"{prepared.context.params.dataset_name}_observations.txt",
        output_dir / "fontainebleau_all_sites.txt",
        output_dir / "fontainebleau_dataset_summary.txt",
        output_dir / "fontainebleau_tracer_summary.txt",
    ]
    prepared.selected_observations.to_csv(outputs[0], sep="\t", index=False)
    prepared.all_observations.to_csv(outputs[1], sep="\t", index=False)
    prepared.dataset_summary.to_csv(outputs[2], sep="\t", index=False)
    prepared.tracer_summary.to_csv(outputs[3], sep="\t", index=False)
    return outputs


def build_pre_model_figures(prepared: PreparedFontainebleauCase, output_dir: Path) -> list[Path]:
    output_dir.mkdir(parents=True, exist_ok=True)
    selected = prepared.selected_observations.copy()
    summary = prepared.tracer_summary.rename(columns={"unit": "summary_unit"})
    normalized = selected.merge(
        summary[["element", "summary_unit", "min_concentration", "max_concentration"]],
        on="element",
        how="left",
    )
    normalized["position_0_1"] = 0.5
    non_constant = normalized["max_concentration"] > normalized["min_concentration"]
    normalized.loc[non_constant, "position_0_1"] = (
        (normalized.loc[non_constant, "concentration"] - normalized.loc[non_constant, "min_concentration"])
        / (normalized.loc[non_constant, "max_concentration"] - normalized.loc[non_constant, "min_concentration"])
    )

    fig, axes = plt.subplots(1, 2, figsize=(13, 4.8), constrained_layout=True)

    table_frame = selected[["element", "concentration", "error", "unit", "date"]].copy()
    for column in ("concentration", "error", "date"):
        table_frame[column] = table_frame[column].map(lambda value: f"{float(value):g}")
    axes[0].axis("off")
    axes[0].set_title(
        f"{prepared.context.params.dataset_name}: selected observations",
        loc="left",
    )
    table = axes[0].table(
        cellText=table_frame.values,
        colLabels=table_frame.columns,
        loc="center",
        cellLoc="center",
    )
    table.auto_set_font_size(False)
    table.set_fontsize(9)
    table.scale(1.05, 1.35)

    axes[1].set_title("Selected site within the Fontainebleau ensemble", loc="left")
    for idx, row in enumerate(normalized.itertuples(index=False)):
        tracer_rows = prepared.all_observations.loc[prepared.all_observations["element"] == row.element].copy()
        min_value = float(row.min_concentration)
        max_value = float(row.max_concentration)
        tracer_rows["position_0_1"] = 0.5
        if max_value > min_value:
            tracer_rows["position_0_1"] = (
                (tracer_rows["concentration"] - min_value) / (max_value - min_value)
            )
        others = tracer_rows.loc[~tracer_rows["selected"]]
        axes[1].hlines(idx, 0.0, 1.0, color="0.85", linewidth=2)
        axes[1].scatter(others["position_0_1"], [idx] * len(others), color="0.6", s=28, zorder=2)
        axes[1].scatter(row.position_0_1, idx, color="tab:blue", s=70, zorder=3)
        axes[1].text(
            1.03,
            idx,
            f"{row.element} ({row.unit})",
            va="center",
            ha="left",
            fontsize=9,
        )
    axes[1].set_xlim(-0.05, 1.22)
    axes[1].set_ylim(-0.7, len(normalized) - 0.3)
    axes[1].set_xlabel("Normalized position within Fontainebleau sites")
    axes[1].set_yticks([])
    axes[1].set_xticks([0.0, 0.5, 1.0])
    axes[1].grid(axis="x", color="0.9", linestyle="--")

    out_path = output_dir / "fontainebleau_selected_dataset_overview.png"
    fig.savefig(out_path, dpi=160, bbox_inches="tight")
    plt.close(fig)
    return [out_path]


def write_benchmark_summary(prepared: PreparedFontainebleauCase, output_dir: Path) -> Path:
    output_dir.mkdir(parents=True, exist_ok=True)
    selected = prepared.dataset_summary.loc[prepared.dataset_summary["selected"]]
    if selected.empty:
        raise ValueError("Selected Fontainebleau dataset summary is empty.")
    selected_row = selected.iloc[0]
    lines = [
        "Fontainebleau benchmark summary",
        f"dataset: {prepared.context.params.dataset_name}",
        f"dataset_path: {prepared.context.dataset_path}",
        f"dataset_label: {prepared.context.params.dataset_label or prepared.context.params.dataset_name}",
        "source_article: Corcho Alvarado et al. (2007), WRR 43, W03427",
        "sampling_campaign: October 2001",
        f"lpm_model: {prepared.context.params.lpm_model_name}",
        f"results_dir: {prepared.context.expected_results_dir}",
        f"available_datasets: {', '.join(prepared.context.available_datasets)}",
        f"available_lpm_models: {', '.join(prepared.context.available_lpm_models)}",
        f"sampling_date: {float(selected_row['sampling_date']):g}",
        f"tracers: {selected_row['tracers']}",
        "39Ar_storage: fraction_of_modern_numeric_under_%modern_label",
        f"mean_concentration: {float(selected_row['mean_concentration']):.6g}",
        f"mean_error: {float(selected_row['mean_error']):.6g}",
    ]
    out_path = output_dir / "benchmark_summary.txt"
    out_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return out_path


__all__ = [
    "build_pre_model_figures",
    "load_all_datasets",
    "prepare_fontainebleau_case",
    "read_dataset",
    "write_benchmark_summary",
    "write_prepared_tables",
]
