# Copyright (c) 2021-2026 Centre national de la recherche scientifique (CNRS)
# Contributor: Jean-Raynald de Dreuzy
# SPDX-License-Identifier: CECILL-2.1

"""Post-process the completed Holten prior-sensitivity campaigns.

This module never starts a sampler and never writes to the baseline campaign.
It reads the final posterior summaries, residuals, prior-only comparison, and
Dirichlet convergence diagnostics, then creates the Appendix C artifacts.
"""

from __future__ import annotations

import argparse
import json
import math
import sys
from collections.abc import Iterable
from pathlib import Path
from typing import Any

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from matplotlib.ticker import PercentFormatter

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts.common.publication_plotting import (  # noqa: E402
    PUBLICATION_RC,
    mm_to_in,
    save_pdf_png,
)

DEFAULT_BASELINE = (
    ROOT / "results" / "final_article_simulations" / "holten_h4_final"
)
DEFAULT_DIRICHLET = ROOT / "results" / "robustness" / "holten_prior_dirichlet1"
DEFAULT_OUTPUT = (
    ROOT / "results" / "robustness" / "holten_prior_sensitivity_postprocessed"
)

WELL_ORDER = ("59-05", "67-19", "72-22", "73-29", "85-33", "85-34", "85-35")
AGE_PARAMETERS = ("f_0_20", "f_20_40", "f_40_60", "f_old")
AGE_CLASS_LABELS = {
    "f_0_20": "0\N{EN DASH}20 yr",
    "f_20_40": "20\N{EN DASH}40 yr",
    "f_40_60": "40\N{EN DASH}60 yr",
    "f_old": ">60 yr",
}
# Existing Holten four-bin palette in examples/natural/holten/holten_four_bin.py.
AGE_CLASS_COLORS = {
    "f_0_20": "#4c78a8",
    "f_20_40": "#72b7b2",
    "f_40_60": "#f2cf5b",
    "f_old": "#d95f5f",
}
MEDIAN_SUM_ATOL = 5.0e-3
MAX_SPLIT_RHAT = 1.01
MIN_ESS = 300.0


def _require_columns(frame: pd.DataFrame, columns: Iterable[str], source: Path) -> None:
    missing = sorted(set(columns).difference(frame.columns))
    if missing:
        raise ValueError(f"{source} is missing required columns: {missing}")


def _read_csv(path: Path, columns: Iterable[str]) -> pd.DataFrame:
    if not path.is_file():
        raise FileNotFoundError(f"Required completed-campaign file not found: {path}")
    frame = pd.read_csv(path)
    _require_columns(frame, columns, path)
    return frame


def _ordered_fraction_summary(frame: pd.DataFrame, source: Path) -> pd.DataFrame:
    selected = frame.loc[
        frame["parameter"].isin(AGE_PARAMETERS),
        ["well", "parameter", "median", "q10", "q90"],
    ].copy()
    if selected.duplicated(["well", "parameter"]).any():
        duplicates = selected.loc[
            selected.duplicated(["well", "parameter"], keep=False),
            ["well", "parameter"],
        ].values.tolist()
        raise ValueError(f"{source} has duplicate age-fraction rows: {duplicates}")

    expected = pd.MultiIndex.from_product(
        [WELL_ORDER, AGE_PARAMETERS], names=["well", "parameter"]
    )
    indexed = selected.set_index(["well", "parameter"])
    missing = expected.difference(indexed.index).tolist()
    extra = indexed.index.difference(expected).tolist()
    if missing or extra:
        raise ValueError(
            f"{source} does not have the expected wells and age classes "
            f"(missing={missing}, extra={extra})"
        )
    ordered = indexed.reindex(expected)
    values = ordered[["median", "q10", "q90"]].to_numpy(dtype=float)
    if not np.isfinite(values).all():
        raise ValueError(f"{source} contains non-finite posterior summaries")
    if not ((0.0 <= values).all() and (values <= 1.0).all()):
        raise ValueError(f"{source} contains an age-fraction summary outside [0, 1]")
    if not (
        (ordered["q10"] <= ordered["median"]).all()
        and (ordered["median"] <= ordered["q90"]).all()
    ):
        raise ValueError(f"{source} does not satisfy q10 <= median <= q90")
    return ordered


def compare_age_fractions(
    baseline: pd.DataFrame,
    dirichlet: pd.DataFrame,
    *,
    baseline_source: Path,
    dirichlet_source: Path,
) -> pd.DataFrame:
    """Build and validate the direct 7-well by 4-class comparison."""

    baseline_grid = _ordered_fraction_summary(baseline, baseline_source)
    dirichlet_grid = _ordered_fraction_summary(dirichlet, dirichlet_source)
    if not baseline_grid.index.equals(dirichlet_grid.index):
        raise AssertionError("Baseline and Dirichlet wells or age classes differ")

    result = pd.DataFrame(index=baseline_grid.index)
    for statistic in ("median", "q10", "q90"):
        result[f"baseline_{statistic}"] = baseline_grid[statistic]
        result[f"dirichlet_{statistic}"] = dirichlet_grid[statistic]
    result["signed_change"] = (
        result["dirichlet_median"] - result["baseline_median"]
    )
    result["absolute_change"] = result["signed_change"].abs()
    result["signed_change_percentage_points"] = 100.0 * result["signed_change"]
    result["absolute_change_percentage_points"] = 100.0 * result["absolute_change"]
    result = result.reset_index()
    result.insert(2, "age_class", result["parameter"].map(AGE_CLASS_LABELS))
    result = result.drop(columns="parameter")
    result = result[
        [
            "well",
            "age_class",
            "baseline_median",
            "baseline_q10",
            "baseline_q90",
            "dirichlet_median",
            "dirichlet_q10",
            "dirichlet_q90",
            "signed_change",
            "absolute_change",
            "signed_change_percentage_points",
            "absolute_change_percentage_points",
        ]
    ]

    for prior in ("baseline", "dirichlet"):
        sums = result.groupby("well", sort=False)[f"{prior}_median"].sum()
        np.testing.assert_allclose(
            sums.to_numpy(),
            np.ones(len(WELL_ORDER)),
            atol=MEDIAN_SUM_ATOL,
            rtol=0.0,
            err_msg=f"The four {prior} marginal medians do not sum approximately to 1",
        )
    return result


def _residual_metrics(residuals: pd.DataFrame, prior: str, well: str | None) -> dict[str, float]:
    selected = residuals.loc[residuals["prior"].eq(prior)]
    if well is not None:
        selected = selected.loc[selected["well"].eq(well)]
    values = selected["standardized_residual"].to_numpy(dtype=float)
    expected = 28 if well is None else 4
    if len(values) != expected or not np.isfinite(values).all():
        scope = "global" if well is None else well
        raise ValueError(
            f"Expected {expected} finite {prior} residuals for {scope}, found {len(values)}"
        )
    absolute = np.abs(values)
    return {
        "rms": float(np.sqrt(np.mean(np.square(values)))),
        "mean_absolute": float(np.mean(absolute)),
        "maximum_absolute": float(np.max(absolute)),
    }


def summarize_by_well(
    comparison: pd.DataFrame, residuals: pd.DataFrame
) -> pd.DataFrame:
    """Calculate directly interpretable age-fraction and residual metrics."""

    _require_columns(
        residuals,
        ("prior", "well", "tracer", "standardized_residual"),
        Path("standardized_residuals.csv"),
    )
    expected_priors = {"uniform_z", "dirichlet_1"}
    if set(residuals["prior"]) != expected_priors:
        raise ValueError(
            "standardized_residuals.csv must contain exactly uniform_z and dirichlet_1"
        )
    expected_pairs = {(well, tracer) for well in WELL_ORDER for tracer in residuals["tracer"].unique()}
    for prior in expected_priors:
        pairs = set(
            residuals.loc[residuals["prior"].eq(prior), ["well", "tracer"]]
            .itertuples(index=False, name=None)
        )
        if pairs != expected_pairs:
            raise ValueError(f"Residual well/tracer grid differs for {prior}")

    rows: list[dict[str, Any]] = []
    for well in WELL_ORDER:
        group = comparison.loc[comparison["well"].eq(well)].reset_index(drop=True)
        absolute = group["absolute_change"].to_numpy(dtype=float)
        maximum_index = int(np.argmax(absolute))
        maximum = float(absolute[maximum_index])
        redistributed = 0.5 * float(np.sum(absolute))
        assert 0.0 <= redistributed <= 1.0
        assert math.isclose(redistributed, 0.5 * float(np.sum(np.abs(absolute))))
        assert math.isclose(maximum, float(np.max(np.abs(absolute))))

        baseline_fit = _residual_metrics(residuals, "uniform_z", well)
        dirichlet_fit = _residual_metrics(residuals, "dirichlet_1", well)
        rows.append(
            {
                "well": well,
                "largest_age_class_change_percentage_points": 100.0 * maximum,
                "age_class_with_largest_change": group.loc[maximum_index, "age_class"],
                "total_redistributed_percentage_points": 100.0 * redistributed,
                "baseline_rms_standardized_residual": baseline_fit["rms"],
                "dirichlet_rms_standardized_residual": dirichlet_fit["rms"],
                "baseline_mean_absolute_standardized_residual": baseline_fit[
                    "mean_absolute"
                ],
                "dirichlet_mean_absolute_standardized_residual": dirichlet_fit[
                    "mean_absolute"
                ],
                "baseline_maximum_absolute_standardized_residual": baseline_fit[
                    "maximum_absolute"
                ],
                "dirichlet_maximum_absolute_standardized_residual": dirichlet_fit[
                    "maximum_absolute"
                ],
            }
        )
    return pd.DataFrame(rows)


def validate_convergence(convergence: pd.DataFrame, source: Path) -> dict[str, float]:
    """Stop unless every recorded Dirichlet group satisfies the current criteria."""

    _require_columns(
        convergence,
        ("prior", "well", "split_rhat", "ess_sum_chains", "converged"),
        source,
    )
    if len(convergence) != 49 or set(convergence["well"]) != set(WELL_ORDER):
        raise ValueError("Expected the complete 49-row Dirichlet convergence table")
    if set(convergence["prior"]) != {"dirichlet_1"}:
        raise ValueError("Convergence diagnostics contain a prior other than dirichlet_1")
    rhat = pd.to_numeric(convergence["split_rhat"], errors="raise")
    ess = pd.to_numeric(convergence["ess_sum_chains"], errors="raise")
    converged = convergence["converged"].astype(str).str.lower().map(
        {"true": True, "false": False}
    )
    if converged.isna().any():
        raise ValueError("Convergence diagnostics contain invalid converged flags")
    maximum_rhat = float(rhat.max())
    minimum_ess = float(ess.min())
    failures: list[str] = []
    if not bool(converged.all()):
        failures.append(f"{int((~converged).sum())} recorded group(s) failed")
    if not maximum_rhat < MAX_SPLIT_RHAT:
        failures.append(f"max split-Rhat {maximum_rhat:.6g} is not < {MAX_SPLIT_RHAT}")
    if not minimum_ess >= MIN_ESS:
        failures.append(f"min ESS {minimum_ess:.6g} is not >= {MIN_ESS:g}")
    if failures:
        raise RuntimeError("Dirichlet convergence criteria failed: " + "; ".join(failures))
    return {"maximum_split_rhat": maximum_rhat, "minimum_ess": minimum_ess}


def validate_prior_only(prior_only: pd.DataFrame, source: Path) -> None:
    """Check that the existing prior-only table can directly support Table C1."""

    _require_columns(
        prior_only,
        ("prior", "fraction", "mean", "median", "q10", "q90"),
        source,
    )
    expected_priors = {"uniform_z", "dirichlet_1_truncated_to_z_bounds"}
    if set(prior_only["prior"]) != expected_priors:
        raise ValueError(f"{source} does not contain the two expected prior-only groups")
    for prior in expected_priors:
        subset = prior_only.loc[prior_only["prior"].eq(prior)]
        if set(subset["fraction"]) != set(AGE_PARAMETERS) or len(subset) != 4:
            raise ValueError(f"{source} has an incomplete age-class grid for {prior}")
    numeric = prior_only[["mean", "median", "q10", "q90"]].to_numpy(dtype=float)
    if not np.isfinite(numeric).all():
        raise ValueError(f"{source} contains non-finite prior-only summaries")


def validate_existing_change_of_variables_check(
    validation: pd.DataFrame, source: Path
) -> None:
    """Reuse the campaign's numerical implementation check without recomputing it."""

    _require_columns(
        validation,
        ("analytical_abs_det", "finite_difference_abs_det", "relative_error"),
        source,
    )
    if len(validation) != 256:
        raise ValueError(f"Expected 256 existing validation points in {source}")
    values = validation[
        ["analytical_abs_det", "finite_difference_abs_det", "relative_error"]
    ].to_numpy(dtype=float)
    if not np.isfinite(values).all() or (values < 0.0).any():
        raise ValueError(f"{source} contains invalid numerical validation values")
    if float(validation["relative_error"].max()) >= 1.0e-6:
        raise RuntimeError("Existing change-of-variables implementation check failed")


def _table_c2(frame: pd.DataFrame) -> pd.DataFrame:
    table = frame[
        [
            "well",
            "largest_age_class_change_percentage_points",
            "age_class_with_largest_change",
            "total_redistributed_percentage_points",
            "baseline_rms_standardized_residual",
            "dirichlet_rms_standardized_residual",
        ]
    ].copy()
    table.columns = [
        "Well",
        "Largest change in one age class (percentage points)",
        "Age class with largest change",
        "Total fraction redistributed between age classes (percentage points)",
        "RMS residual, baseline",
        "RMS residual, Dirichlet",
    ]
    for column in table.columns[[1, 3]]:
        table[column] = table[column].map(lambda value: f"{value:.1f}")
    for column in table.columns[[4, 5]]:
        table[column] = table[column].map(lambda value: f"{value:.2f}")
    return table


def _markdown_table(frame: pd.DataFrame) -> str:
    headings = "| " + " | ".join(frame.columns) + " |"
    rule = "| " + " | ".join("---" for _ in frame.columns) + " |"
    rows = [
        "| " + " | ".join(str(value) for value in row) + " |"
        for row in frame.itertuples(index=False, name=None)
    ]
    return "\n".join([headings, rule, *rows]) + "\n"


def _summary(
    comparison: pd.DataFrame,
    by_well: pd.DataFrame,
    residuals: pd.DataFrame,
    convergence: dict[str, float],
) -> dict[str, Any]:
    largest_row = comparison.loc[
        comparison["absolute_change_percentage_points"].idxmax()
    ]
    redistributed_row = by_well.loc[
        by_well["total_redistributed_percentage_points"].idxmax()
    ]
    baseline_fit = _residual_metrics(residuals, "uniform_z", None)
    dirichlet_fit = _residual_metrics(residuals, "dirichlet_1", None)
    return {
        "largest_age_class_change": {
            "fraction": float(largest_row["absolute_change"]),
            "percentage_points": float(
                largest_row["absolute_change_percentage_points"]
            ),
            "signed_percentage_points": float(
                largest_row["signed_change_percentage_points"]
            ),
            "well": str(largest_row["well"]),
            "age_class": str(largest_row["age_class"]),
        },
        "median_largest_age_class_change_by_well_percentage_points": float(
            by_well["largest_age_class_change_percentage_points"].median()
        ),
        "largest_total_fraction_redistributed": {
            "fraction": float(
                redistributed_row["total_redistributed_percentage_points"] / 100.0
            ),
            "percentage_points": float(
                redistributed_row["total_redistributed_percentage_points"]
            ),
            "well": str(redistributed_row["well"]),
        },
        "median_total_fraction_redistributed_percentage_points": float(
            by_well["total_redistributed_percentage_points"].median()
        ),
        "global_rms_standardized_residual": {
            "baseline_uniform_z_prior": baseline_fit["rms"],
            "dirichlet_prior": dirichlet_fit["rms"],
        },
        "change_of_variables_implementation_numerically_verified": True,
        **convergence,
    }


def _summary_markdown(summary: dict[str, Any]) -> str:
    largest = summary["largest_age_class_change"]
    redistributed = summary["largest_total_fraction_redistributed"]
    rms = summary["global_rms_standardized_residual"]
    return f"""# Holten prior sensitivity summary

- Largest change in age fraction: **{largest['percentage_points']:.3f} percentage points** ({largest['well']}, {largest['age_class']}; signed change {largest['signed_percentage_points']:+.3f} percentage points).
- Median of the largest change per well: **{summary['median_largest_age_class_change_by_well_percentage_points']:.3f} percentage points**.
- Largest total fraction redistributed between age classes: **{redistributed['percentage_points']:.3f} percentage points** ({redistributed['well']}).
- Median total fraction redistributed between age classes: **{summary['median_total_fraction_redistributed_percentage_points']:.3f} percentage points**.
- Global RMS standardized residual: **{rms['baseline_uniform_z_prior']:.6f}** for the baseline uniform-z prior and **{rms['dirichlet_prior']:.6f}** for the Dirichlet prior.
- Dirichlet calculation convergence: maximum split-Rhat **{summary['maximum_split_rhat']:.6f}**; minimum ESS **{summary['minimum_ess']:.1f}**.
- The implementation of the change of variables was verified numerically using the existing reproducibility results.
"""


def make_figure(output: Path, comparison: pd.DataFrame) -> tuple[Path, Path]:
    """Draw paired 100%-stacked horizontal bars for each Holten well."""

    with plt.rc_context(PUBLICATION_RC):
        figure, axis = plt.subplots(figsize=(mm_to_in(165), mm_to_in(112)))
        pair_centers = np.arange(len(WELL_ORDER), dtype=float) * 2.35
        bar_height = 0.72
        offsets = {"Baseline": -0.42, "Dirichlet": 0.42}
        prefixes = {"Baseline": "baseline", "Dirichlet": "dirichlet"}

        for well_index, well in enumerate(WELL_ORDER):
            group = comparison.loc[comparison["well"].eq(well)].set_index("age_class")
            for prior_label in ("Baseline", "Dirichlet"):
                left = 0.0
                prefix = prefixes[prior_label]
                y = pair_centers[well_index] + offsets[prior_label]
                for parameter in AGE_PARAMETERS:
                    age_label = AGE_CLASS_LABELS[parameter]
                    width = float(group.loc[age_label, f"{prefix}_median"])
                    axis.barh(
                        y,
                        width,
                        left=left,
                        height=bar_height,
                        color=AGE_CLASS_COLORS[parameter],
                        edgecolor="white",
                        linewidth=0.45,
                        label=age_label if well_index == 0 and prior_label == "Baseline" else None,
                    )
                    left += width

        tick_positions: list[float] = []
        tick_labels: list[str] = []
        for center, well in zip(pair_centers, WELL_ORDER, strict=True):
            tick_positions.extend([center - 0.42, center + 0.42])
            tick_labels.extend([f"{well}   Baseline", "Dirichlet"])
        axis.set_yticks(tick_positions, tick_labels)
        axis.invert_yaxis()
        axis.set_xlim(0.0, 1.0)
        axis.set_xticks(np.linspace(0.0, 1.0, 6))
        axis.xaxis.set_major_formatter(PercentFormatter(xmax=1.0, decimals=0))
        axis.set_xlabel("Age fraction")
        axis.set_axisbelow(True)
        axis.grid(axis="x", color="#d9d9d9", linewidth=0.6, alpha=0.7)
        axis.grid(False, axis="y")
        axis.spines[["top", "right", "left"]].set_visible(False)
        axis.tick_params(axis="y", length=0)
        handles, labels = axis.get_legend_handles_labels()
        figure.legend(
            handles[:4],
            labels[:4],
            loc="lower center",
            bbox_to_anchor=(0.57, 0.01),
            ncol=4,
            frameon=False,
        )
        figure.subplots_adjust(left=0.22, right=0.985, top=0.98, bottom=0.19)
        paths = save_pdf_png(figure, output, "figureC1_holten_prior_sensitivity")
        plt.close(figure)
    return paths


def postprocess(baseline_dir: Path, dirichlet_dir: Path, output: Path) -> dict[str, Any]:
    """Run the read-only scientific post-processing and write new artifacts."""

    baseline_dir = baseline_dir.resolve()
    dirichlet_dir = dirichlet_dir.resolve()
    output = output.resolve()
    for source_name, source_dir in (
        ("canonical baseline campaign", baseline_dir),
        ("Dirichlet campaign", dirichlet_dir),
    ):
        if output == source_dir or source_dir in output.parents:
            raise ValueError(f"Output must not be in the {source_name}")

    baseline_path = baseline_dir / "posterior_summaries.csv"
    dirichlet_path = dirichlet_dir / "posterior_summaries_dirichlet1.csv"
    residuals_path = dirichlet_dir / "standardized_residuals.csv"
    convergence_path = dirichlet_dir / "convergence_diagnostics.csv"
    prior_only_path = dirichlet_dir / "prior_only_comparison.csv"
    validation_path = dirichlet_dir / "jacobian_validation.csv"

    baseline = _read_csv(
        baseline_path, ("well", "parameter", "median", "q10", "q90")
    )
    dirichlet = _read_csv(
        dirichlet_path, ("well", "parameter", "median", "q10", "q90")
    )
    residuals = _read_csv(
        residuals_path, ("prior", "well", "tracer", "standardized_residual")
    )
    convergence_frame = _read_csv(
        convergence_path,
        ("prior", "well", "split_rhat", "ess_sum_chains", "converged"),
    )
    prior_only = _read_csv(
        prior_only_path, ("prior", "fraction", "mean", "median", "q10", "q90")
    )
    validation = _read_csv(
        validation_path,
        ("analytical_abs_det", "finite_difference_abs_det", "relative_error"),
    )

    convergence = validate_convergence(convergence_frame, convergence_path)
    validate_prior_only(prior_only, prior_only_path)
    validate_existing_change_of_variables_check(validation, validation_path)
    comparison = compare_age_fractions(
        baseline,
        dirichlet,
        baseline_source=baseline_path,
        dirichlet_source=dirichlet_path,
    )
    by_well = summarize_by_well(comparison, residuals)
    summary = _summary(comparison, by_well, residuals, convergence)

    output.mkdir(parents=True, exist_ok=True)
    comparison.to_csv(output / "posterior_age_fraction_prior_comparison.csv", index=False)
    by_well.to_csv(output / "prior_sensitivity_by_well.csv", index=False)
    with (output / "prior_sensitivity_summary.json").open("w", encoding="utf-8") as stream:
        json.dump(summary, stream, indent=2, ensure_ascii=False)
        stream.write("\n")
    (output / "prior_sensitivity_summary.md").write_text(
        _summary_markdown(summary), encoding="utf-8"
    )
    table_c2 = _table_c2(by_well)
    table_c2.to_csv(output / "tableC2_prior_sensitivity_by_well.csv", index=False)
    (output / "tableC2_prior_sensitivity_by_well.md").write_text(
        _markdown_table(table_c2), encoding="utf-8"
    )
    make_figure(output, comparison)
    return summary


def _arguments() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Post-process existing Holten prior-sensitivity results; never run MCMC."
    )
    parser.add_argument("--baseline", type=Path, default=DEFAULT_BASELINE)
    parser.add_argument("--dirichlet", type=Path, default=DEFAULT_DIRICHLET)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    return parser.parse_args()


def main() -> int:
    arguments = _arguments()
    summary = postprocess(arguments.baseline, arguments.dirichlet, arguments.output)
    print(json.dumps(summary, indent=2, ensure_ascii=False))
    print("no MCMC rerun")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
