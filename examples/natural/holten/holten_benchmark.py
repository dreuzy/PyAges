# -*- coding: utf-8 -*-
"""
Pre-model figures and benchmark helpers for Holten.
"""

from __future__ import annotations

from pathlib import Path
import shutil
import subprocess
import tempfile
from typing import Any
import sys

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

try:
    from pyage.config.bootstrap import ensure_repo_imports
except ModuleNotFoundError:
    repo_root = Path(__file__).resolve().parents[3]
    sys.path.insert(0, str(repo_root))
    from pyage.config.bootstrap import ensure_repo_imports


ensure_repo_imports()

from holten_case import PreparedHoltenCase, build_context, load_yaml


ARTICLE_FIGURE_SPECS = {
    "figure_4": {
        "page": 9,
        "crop": (70, 70, 1090, 930),
        "label": "Figure 4 - Historical tritium concentrations in precipitation",
    },
    "figure_8": {
        "page": 12,
        "crop": (70, 70, 1090, 760),
        "label": "Figure 8 - 4He radiogenic and 39Ar / 3H-3He relationships",
    },
    "figure_9": {
        "page": 13,
        "crop": (70, 70, 1120, 1525),
        "label": "Figure 9 - Tracer-tracer plots and 4-bin end-members",
    },
    "figure_10": {
        "page": 14,
        "crop": (70, 70, 1120, 1620),
        "label": "Figure 10 - Cumulative age distributions by model family",
    },
}

REFERENCE_MODEL_COLUMNS = [
    ("3bin_chi2", "3-bin"),
    ("4bin_chi2", "4-bin"),
    ("5bin_chi2", "5-bin"),
    ("9bin_chi2", "9-bin"),
    ("DM_chi2", "DM"),
    ("DMfold_chi2", "DM + old"),
    ("EM_chi2", "EM"),
    ("EMfold_chi2", "EM + old"),
]


def load_reference_results(context=None) -> pd.DataFrame:
    ctx = context or build_context()
    return pd.read_csv(ctx.paths.reference_results_path, sep="\t")


def build_article_reference_figures(context=None, output_dir: Path | None = None) -> dict[str, Path]:
    from PIL import Image

    ctx = context or build_context()
    output_root = output_dir or (ctx.paths.benchmark_dir / "article_reference")
    output_root.mkdir(parents=True, exist_ok=True)
    pdf_path = ctx.paths.doc_dir / "Visser et al, 2013.pdf"
    pdftoppm = shutil.which("pdftoppm")
    if pdftoppm is None:
        raise RuntimeError("pdftoppm is required to extract article figures from the local PDF.")

    generated: dict[str, Path] = {}
    with tempfile.TemporaryDirectory() as tmp_dir_text:
        tmp_dir = Path(tmp_dir_text)
        for name, spec in ARTICLE_FIGURE_SPECS.items():
            prefix = tmp_dir / f"{name}_page"
            subprocess.run(
                [
                    pdftoppm,
                    "-png",
                    "-r",
                    "180",
                    "-f",
                    str(spec["page"]),
                    "-l",
                    str(spec["page"]),
                    str(pdf_path),
                    str(prefix),
                ],
                check=True,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
            )
            page_image = next(tmp_dir.glob(f"{prefix.name}-*.png"))
            with Image.open(page_image) as image:
                cropped = image.crop(spec["crop"])
                out_path = output_root / f"{name}.png"
                cropped.save(out_path)
            generated[name] = out_path
    return generated


def _history_summary(history: pd.DataFrame) -> dict[str, float]:
    conc = history["concentration"].astype(float)
    return {
        "min": float(conc.min()),
        "q05": float(conc.quantile(0.05)),
        "median": float(conc.median()),
        "q95": float(conc.quantile(0.95)),
        "max": float(conc.max()),
    }


def build_reference_curve(
    prepared: PreparedHoltenCase,
    tracer_name: str,
    history: pd.DataFrame,
    observed: pd.DataFrame,
) -> pd.DataFrame:
    display = history.copy()
    reference_year = float(observed["date"].median())
    yaml_path = prepared.context.paths.tracer_source_dir / tracer_name / f"{tracer_name}.yaml"
    tracer_cfg = load_yaml(yaml_path)

    if tracer_name in {"3H", "kr85"}:
        decay_time = float(tracer_cfg["decay_time"])
        display = display.loc[display["date"].astype(float) <= reference_year].copy()
        ages = reference_year - display["date"].astype(float)
        display["concentration"] = display["concentration"].astype(float) * np.exp(-ages / decay_time)
        display.attrs["display_kind"] = "reference_decay"
        display.attrs["reference_year"] = reference_year
        display.attrs["display_label"] = f"Input history after decay to {reference_year:.2f}"
        display.attrs["display_title"] = f"{tracer_name}: reference curve brought to the 2010 sampling year"
        display.attrs["x_label"] = "Equivalent recharge year"
        return display

    if tracer_name == "39Ar":
        display.attrs.setdefault("display_kind", "reference_decay")
        display.attrs.setdefault("reference_year", reference_year)
        display.attrs.setdefault(
            "display_label",
            f"Theoretical decay curve referenced to {display.attrs['reference_year']:.2f}",
        )
        display.attrs.setdefault(
            "display_title",
            f"{tracer_name}: theoretical decay curve referenced to the 2010 sampling year",
        )
        display.attrs.setdefault("x_label", "Equivalent recharge year")
    return display


def _apply_range_axis_scale(ax, min_val: float, max_val: float) -> None:
    if min_val > 0 and max_val / min_val > 50:
        ax.set_xscale("log")


def _set_position_axis_limits(ax, history: pd.DataFrame, observed: pd.DataFrame) -> None:
    values = history["concentration"].astype(float).tolist() + observed["concentration"].astype(float).tolist()
    if ax.get_xscale() == "log":
        positive = [value for value in values if value > 0]
        if not positive:
            return
        ax.set_xlim(min(positive) / 1.2, max(positive) * 1.2)
        return
    min_val = min(values)
    max_val = max(values)
    span = max_val - min_val
    pad = max(abs(min_val) * 0.05, 0.1) if span == 0 else 0.05 * span
    ax.set_xlim(min_val - pad, max_val + pad)


def _plot_value_range_position(ax, tracer_name: str, history: pd.DataFrame, observed: pd.DataFrame) -> None:
    summary = _history_summary(history)
    y0 = 0.0
    ax.hlines(y0, summary["min"], summary["max"], color="#c7d2e2", linewidth=10, zorder=1)
    ax.hlines(y0, summary["q05"], summary["q95"], color="#7f95b8", linewidth=10, zorder=2)
    ax.vlines(summary["median"], y0 - 0.18, y0 + 0.18, color="#23395d", linewidth=2.2, zorder=3)

    y_positions = np.linspace(-0.14, 0.14, max(len(observed), 1))
    for y_pos, (_, row) in zip(y_positions, observed.iterrows()):
        ax.scatter(
            [float(row["concentration"])],
            [y_pos],
            s=70,
            color="#c13b31",
            edgecolor="white",
            linewidth=0.8,
            zorder=4,
        )
        ax.annotate(
            f"{row['well_id']} ({row['concentration']:.2f})",
            (float(row["concentration"]), y_pos),
            textcoords="offset points",
            xytext=(6, 0),
            va="center",
            fontsize=8,
        )

    _apply_range_axis_scale(ax, summary["min"], summary["max"])
    _set_position_axis_limits(ax, history, observed)
    ax.set_yticks([])
    ax.set_title(f"{tracer_name}: sampled values within the range of the reference curve")
    ax.set_xlabel(f"Concentration [{history['unit'].iloc[0]}]")
    ax.grid(axis="x", alpha=0.25)
    ax.text(summary["min"], 0.22, "min", fontsize=8, ha="left", va="bottom", color="#4b5f83")
    ax.text(summary["median"], 0.22, "median", fontsize=8, ha="center", va="bottom", color="#23395d")
    ax.text(summary["max"], 0.22, "max", fontsize=8, ha="right", va="bottom", color="#4b5f83")


def build_pre_model_figures(prepared: PreparedHoltenCase, output_dir: Path) -> list[Path]:
    output_dir.mkdir(parents=True, exist_ok=True)
    generated: list[Path] = []

    for tracer_name, history in prepared.tracer_histories.items():
        observed = prepared.observed_aggregated.loc[
            prepared.observed_aggregated["element"] == tracer_name
        ].copy()
        display_history = build_reference_curve(prepared, tracer_name, history, observed)
        line_label = display_history.attrs.get("display_label", "Recharge history")
        title = display_history.attrs.get("display_title", f"{tracer_name}: recharge history and Holten observations")
        x_label = display_history.attrs.get("x_label", "Decimal year")
        fig, axes = plt.subplots(2, 1, figsize=(10, 7.2), gridspec_kw={"height_ratios": [2.0, 1.0]})
        ax = axes[0]
        ax.plot(
            display_history["date"],
            display_history["concentration"],
            color="#1f4b99",
            linewidth=1.8,
            label=line_label,
        )
        ax.scatter(
            observed["date"],
            observed["concentration"],
            s=55,
            color="#c13b31",
            zorder=3,
            label="2010 samples",
        )
        for _, row in observed.iterrows():
            ax.annotate(
                row["well_id"],
                (row["date"], row["concentration"]),
                textcoords="offset points",
                xytext=(5, 5),
                fontsize=8,
            )
        unit = display_history["unit"].iloc[0]
        ax.set_title(title)
        ax.set_xlabel(x_label)
        ax.set_ylabel(f"Concentration [{unit}]")
        ax.grid(alpha=0.25)
        if display_history["concentration"].nunique() == 1 and not observed.empty:
            center = float(observed["date"].median())
            ax.set_xlim(center - 20.0, center + 20.0)
        ax.legend(loc="best")
        _plot_value_range_position(axes[1], tracer_name, display_history, observed)
        fig.tight_layout()
        out_path = output_dir / f"tracer_{tracer_name}_history_and_observations.png"
        fig.savefig(out_path, dpi=150)
        plt.close(fig)
        generated.append(out_path)

        fig, ax = plt.subplots(figsize=(10, 2.8))
        _plot_value_range_position(ax, tracer_name, display_history, observed)
        fig.tight_layout()
        out_path = output_dir / f"tracer_{tracer_name}_value_range_position.png"
        fig.savefig(out_path, dpi=150)
        plt.close(fig)
        generated.append(out_path)

    for well_id, frame in prepared.observed_by_well.items():
        fig, axes = plt.subplots(len(frame), 1, figsize=(9, 8), sharex=False)
        if len(frame) == 1:
            axes = [axes]
        for ax, (_, row) in zip(axes, frame.iterrows()):
            tracer_name = row["element"]
            raw_history = prepared.tracer_histories[tracer_name]
            display_history = build_reference_curve(prepared, tracer_name, raw_history, frame.loc[frame["element"] == tracer_name])
            ax.plot(display_history["date"], display_history["concentration"], color="#1f4b99", linewidth=1.5)
            ax.scatter([row["date"]], [row["concentration"]], s=60, color="#c13b31", zorder=3)
            ax.set_ylabel(f"{tracer_name} [{row['unit']}]")
            ax.grid(alpha=0.25)
        axes[0].set_title(f"Well {well_id}: multi-tracer panel")
        axes[-1].set_xlabel("Equivalent recharge year")
        fig.tight_layout()
        out_path = output_dir / f"well_{well_id}_multi_tracer_panel.png"
        fig.savefig(out_path, dpi=150)
        plt.close(fig)
        generated.append(out_path)
    return generated


def _reference_subset(reference: pd.DataFrame, selected_wells: list[str]) -> pd.DataFrame:
    subset = reference.loc[reference["Well"].isin(selected_wells)].copy()
    score_cols = [
        "3bin_chi2",
        "4bin_chi2",
        "5bin_chi2",
        "9bin_chi2",
        "DM_chi2",
        "DMfold_chi2",
        "EM_chi2",
        "EMfold_chi2",
    ]
    subset["reference_best_model"] = subset[score_cols].astype(float).idxmin(axis=1)
    return subset


def _load_stats_if_available(results_dir: Path | None) -> pd.DataFrame | None:
    if results_dir is None:
        return None
    stats_path = results_dir / "Metropolis_Hastings" / "lpm_stats_calibrated.txt"
    if not stats_path.exists():
        return None
    return pd.read_csv(stats_path, sep="\t", index_col=0)


def _compute_bootstrap_rmse(prepared: PreparedHoltenCase, well_id: str, stats: pd.DataFrame | None) -> float | None:
    if stats is None or "mean" not in stats.index:
        return None
    if prepared.context.lpm_name != "uniform":
        return None
    tmin = float(stats.loc["mean", "tmin"])
    delta = float(stats.loc["mean", "delta"])
    mid_age = tmin + 0.5 * delta
    obs = prepared.observed_by_well[well_id].copy()
    modeled = []
    for _, row in obs.iterrows():
        tracer = row["element"]
        if tracer == "39Ar":
            modeled.append(float(np.exp(-mid_age / 267.0)))
        elif tracer == "3H":
            history = prepared.tracer_histories["3H"]
            target_year = float(row["date"]) - mid_age
            recharge = float(np.interp(target_year, history["date"], history["concentration"], left=0.0, right=0.0))
            modeled.append(recharge * float(np.exp(-mid_age / 12.32)))
        elif tracer == "kr85":
            history = prepared.tracer_histories["kr85"]
            target_year = float(row["date"]) - mid_age
            recharge = float(np.interp(target_year, history["date"], history["concentration"], left=0.0, right=0.0))
            modeled.append(recharge * float(np.exp(-mid_age / 10.76)))
    residuals = obs["concentration"].to_numpy(dtype=float) - np.asarray(modeled, dtype=float)
    return float(np.sqrt(np.mean(np.square(residuals))))


def compare_with_reference_results(
    prepared: PreparedHoltenCase,
    results_by_well: dict[str, Path] | None = None,
    local_4bin_summary: pd.DataFrame | None = None,
) -> pd.DataFrame:
    reference = _reference_subset(load_reference_results(prepared.context), prepared.context.selected_wells)
    rows: list[dict[str, Any]] = []
    results_by_well = results_by_well or {}
    local_4bin_summary = local_4bin_summary if local_4bin_summary is not None else pd.DataFrame()
    for well_id in prepared.context.selected_wells:
        ref_row = reference.loc[reference["Well"] == well_id].iloc[0]
        result_dir = results_by_well.get(well_id)
        stats = _load_stats_if_available(result_dir)
        local_row = (
            local_4bin_summary.loc[local_4bin_summary["well_id"] == well_id].iloc[0]
            if not local_4bin_summary.empty and (local_4bin_summary["well_id"] == well_id).any()
            else None
        )
        rows.append(
            {
                "well_id": well_id,
                "reference_4bin_chi2": float(ref_row["4bin_chi2"]),
                "reference_4bin_pchi2": float(ref_row["4bin_pchi2"]),
                "reference_best_model": str(ref_row["reference_best_model"]),
                "local_4bin_chi2": float(local_row["chi2_local_4bin"]) if local_row is not None else np.nan,
                "local_4bin_rmse": float(local_row["rmse_local_4bin"]) if local_row is not None else np.nan,
                "local_4bin_mean_age": float(local_row["mean_age_local_4bin"]) if local_row is not None else np.nan,
                "local_4bin_f_0_20": float(local_row["f_0_20"]) if local_row is not None else np.nan,
                "local_4bin_f_20_40": float(local_row["f_20_40"]) if local_row is not None else np.nan,
                "local_4bin_f_40_60": float(local_row["f_40_60"]) if local_row is not None else np.nan,
                "local_4bin_f_old": float(local_row["f_old"]) if local_row is not None else np.nan,
                "bootstrap_lpm": prepared.context.lpm_name if result_dir else "",
                "bootstrap_result_dir": str(result_dir) if result_dir else "",
                "bootstrap_rmse": _compute_bootstrap_rmse(prepared, well_id, stats),
                "calibration_available": bool(result_dir and result_dir.exists()),
            }
        )
    return pd.DataFrame(rows)


def build_reference_comparison_figures(
    prepared: PreparedHoltenCase,
    comparison: pd.DataFrame,
    output_dir: Path,
) -> dict[str, Path]:
    output_dir.mkdir(parents=True, exist_ok=True)
    generated: dict[str, Path] = {}

    fig, ax = plt.subplots(figsize=(9, 4.8))
    x = np.arange(len(comparison))
    width = 0.34
    ax.bar(
        x - width / 2,
        comparison["reference_4bin_chi2"].astype(float),
        width=width,
        color="#8aa5c7",
        label="Published 4-bin chi2",
    )
    ax.bar(
        x + width / 2,
        comparison["local_4bin_chi2"].astype(float),
        width=width,
        color="#c95b4f",
        label="Local Holten 4-bin chi2",
    )
    ax.set_xticks(x, comparison["well_id"].tolist())
    ax.set_ylabel("chi2")
    ax.set_title("Holten 4-bin fit quality: published benchmark vs local implementation")
    ax.grid(axis="y", alpha=0.25)
    ax.legend(loc="best")
    fig.tight_layout()
    out_path = output_dir / "local_vs_reference_4bin_chi2.png"
    fig.savefig(out_path, dpi=150)
    plt.close(fig)
    generated["local_vs_reference_4bin_chi2"] = out_path

    reference = _reference_subset(load_reference_results(prepared.context), prepared.context.selected_wells)
    fig, axes = plt.subplots(1, len(reference), figsize=(4.6 * len(reference), 4.4), sharey=True)
    if len(reference) == 1:
        axes = [axes]
    x_positions = np.arange(len(REFERENCE_MODEL_COLUMNS))
    labels = [label for _, label in REFERENCE_MODEL_COLUMNS]
    for ax, (_, row) in zip(axes, reference.iterrows()):
        values = [float(row[column]) for column, _ in REFERENCE_MODEL_COLUMNS]
        ax.bar(x_positions, values, color="#5a7aa6")
        ax.set_xticks(x_positions, labels, rotation=45, ha="right")
        ax.set_title(f"Well {row['Well']}")
        ax.set_yscale("log")
        ax.grid(axis="y", alpha=0.25, which="both")
        ax.text(
            0.98,
            0.98,
            f"Best: {row['reference_best_model'].replace('_chi2', '')}",
            transform=ax.transAxes,
            ha="right",
            va="top",
            fontsize=9,
            bbox={"boxstyle": "round,pad=0.25", "fc": "white", "ec": "#b0b0b0", "alpha": 0.9},
        )
    axes[0].set_ylabel("Published chi2 (log scale)")
    fig.suptitle("Published model scores for the selected Holten wells", y=1.02)
    fig.tight_layout()
    out_path = output_dir / "published_model_scores.png"
    fig.savefig(out_path, dpi=150, bbox_inches="tight")
    plt.close(fig)
    generated["published_model_scores"] = out_path
    return generated


def write_benchmark_summary(comparison: pd.DataFrame, output_dir: Path) -> tuple[Path, Path]:
    output_dir.mkdir(parents=True, exist_ok=True)
    csv_path = output_dir / "comparison_by_well.csv"
    txt_path = output_dir / "benchmark_summary.txt"
    comparison.to_csv(csv_path, index=False)

    lines = [
        "Holten benchmark summary",
        "",
        f"Number of wells: {len(comparison)}",
        f"Wells: {', '.join(comparison['well_id'].tolist())}",
        "",
    ]
    for _, row in comparison.iterrows():
        lines.append(
            f"{row['well_id']}: reference 4-bin chi2={row['reference_4bin_chi2']}, "
            f"reference 4-bin pchi2={row['reference_4bin_pchi2']}, "
            f"local 4-bin chi2={row['local_4bin_chi2']}, "
            f"local 4-bin fractions=({row['local_4bin_f_0_20']:.3f}, {row['local_4bin_f_20_40']:.3f}, "
            f"{row['local_4bin_f_40_60']:.3f}, {row['local_4bin_f_old']:.3f}), "
            f"reference best={row['reference_best_model']}, "
            f"bootstrap rmse={row['bootstrap_rmse']}"
        )
    txt_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return csv_path, txt_path
