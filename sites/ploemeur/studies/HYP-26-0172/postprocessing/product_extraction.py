# Copyright (c) 2021-2026 Centre national de la recherche scientifique (CNRS)
# Contributor: Jean-Raynald de Dreuzy
# SPDX-License-Identifier: CECILL-2.1

"""Extract durable HYP-26-0172 tables from native workflow directories.

Only this layer searches timestamped PyAges result folders. It converts their
statistics and run summaries into stable CSV products below ``derived/`` so
publication figure builders do not depend on the native execution layout.
No figure is created here.
"""

from __future__ import annotations

import re
from pathlib import Path

import numpy as np
import pandas as pd

from pyages._scalar_conversion import scalar_float

REPO_ROOT = Path(__file__).resolve().parents[5]
STUDY_RESULTS = REPO_ROOT / "results" / "HYP-26-0172"
SCENARIO_RE = re.compile(
    r"ploemeur_(?P<conditioning>apriori_double_)?(?P<error>\d+(?:\.\d+)?)"
    r"(?P<mode>span_full|span_with_prior|successive_with_prior|successive)$"
)


def profile_root(profile: str) -> Path:
    """Return the production or isolated-profile result directory."""
    return STUDY_RESULTS if profile == "production" else STUDY_RESULTS / profile


def run_directories(root: Path) -> list[Path]:
    """Return matrix-managed run directories containing native workflow output."""
    runs = root / "runs"
    if not runs.is_dir():
        raise FileNotFoundError(f"No run directory found: {runs}")
    return sorted(path for path in runs.iterdir() if (path / "workflow").is_dir())


def latest_scenario_outputs(workflow: Path) -> list[tuple[Path, re.Match[str]]]:
    """Select the newest timestamped output for every recognized scenario."""
    outputs: list[tuple[Path, re.Match[str]]] = []
    for scenario in workflow.iterdir() if workflow.is_dir() else []:
        if not scenario.is_dir() or not (match := SCENARIO_RE.fullmatch(scenario.name)):
            continue
        timestamps = [path for path in scenario.iterdir() if path.is_dir()]
        if timestamps:
            outputs.append(
                (max(timestamps, key=lambda path: path.stat().st_mtime), match)
            )
    return outputs


def collect_statistics(root: Path) -> pd.DataFrame:
    """Collect per-case posterior statistics with explicit study coordinates.

    The native case directory supplies the well and time window; the scenario
    name supplies conditioning mode and relative error. These coordinates are
    written alongside the numerical summaries so later figures need no path
    parsing.
    """
    records: list[dict] = []
    for run_dir in run_directories(root):
        for output, match in latest_scenario_outputs(run_dir / "workflow"):
            for stats_file in sorted(
                output.glob("*_????_????/*/Metropolis_Hastings/distributions_stats.txt")
            ):
                model_dir = stats_file.parents[1]
                case_dir = model_dir.parent
                case_match = re.fullmatch(
                    r"(?P<well>.+)_(?P<start>\d{4})_(?P<end>\d{4})",
                    case_dir.name,
                )
                if not case_match:
                    continue
                samples = pd.read_csv(stats_file, sep="\t")
                if samples.empty or "p50" not in samples:
                    continue
                record = {
                    "date": float(case_match.group("end")),
                    "window_start": int(case_match.group("start")),
                    "window_end": int(case_match.group("end")),
                    "well": case_match.group("well"),
                }
                for column in ("p10", "p25", "p50", "p75", "p90", "mean"):
                    if column in samples:
                        record[f"{column}_mean"] = scalar_float(samples[column].mean())
                        record[f"{column}_std"] = scalar_float(
                            samples[column].std(ddof=0)
                        )
                record.update(
                    experiment_id=run_dir.name,
                    scenario=output.parent.name,
                    output_directory=str(output.relative_to(REPO_ROOT)),
                    mode=match.group("mode"),
                    conditioned=bool(match.group("conditioning")),
                    relative_error=float(match.group("error")),
                    lpm=model_dir.name,
                )
                records.append(record)
    if not records:
        raise FileNotFoundError(
            f"No *_stats_quantiles.txt files found below {root / 'runs'}"
        )
    return pd.DataFrame.from_records(records)


def infer_well(experiment_id: str) -> str:
    """Infer a known Ploemeur well name from a matrix experiment identifier."""
    for well in ("F09", "F11", "F38", "MF1", "PE"):
        if well in experiment_id:
            return well
    return "multiple"


def _read_key_values(path: Path) -> dict[str, str]:
    """Read the canonical tab-separated PyAges scalar metadata format."""
    return dict(
        line.split("\t", maxsplit=1)
        for line in path.read_text(encoding="utf-8").splitlines()
        if "\t" in line
    )


def _boolean_series(series: pd.Series) -> pd.Series:
    """Normalize persisted boolean diagnostics without relying on CSV inference."""
    return series.map(
        lambda value: (
            value
            if isinstance(value, (bool, np.bool_))
            else str(value).strip().lower() == "true"
        )
    )


def _column(frame: pd.DataFrame, name: str) -> pd.Series:
    """Return one unambiguous named column from a diagnostic table."""
    column = frame[name]
    if not isinstance(column, pd.Series):
        raise ValueError(f"Expected exactly one {name!r} diagnostic column")
    return column


def _diagnostic_extreme(
    diagnostics: pd.DataFrame, column: str, operation: str
) -> float:
    """Return a finite diagnostic extreme, or NaN when it is unavailable."""
    if column not in diagnostics:
        return float("nan")
    numeric = pd.to_numeric(_column(diagnostics, column), errors="coerce")
    if not isinstance(numeric, pd.Series):  # pragma: no cover - pandas contract.
        raise TypeError("diagnostic numeric conversion must return a Series")
    numeric = numeric.dropna()
    if numeric.empty:
        return float("nan")
    return float(getattr(numeric, operation)())


def save_derived_tables(stats: pd.DataFrame, derived: Path) -> dict[str, Path]:
    """Write the complete statistics table and declared figure subsets."""
    derived.mkdir(parents=True, exist_ok=True)
    stats = stats.copy()
    if "well" not in stats:
        stats["well"] = stats["experiment_id"].map(infer_well)
    all_path = derived / "posterior_statistics.csv"
    stats.to_csv(all_path, index=False)

    tables = {"all": all_path}
    definitions = {
        "figure4_median_transit_times.csv": stats[
            stats["experiment_id"].str.startswith("main_")
            & stats["mode"].isin(["successive", "successive_with_prior"])
            & stats["lpm"].eq("exp_shifted")
        ],
        "figure5_model_comparison.csv": stats[
            stats["experiment_id"].str.startswith("main_")
            & stats["mode"].eq("successive_with_prior")
        ],
        "figure6_median_transit_times.csv": stats[
            (
                stats["experiment_id"].str.startswith("regime_")
                | stats["experiment_id"].str.startswith("main_")
            )
            & stats["mode"].eq("successive_with_prior")
            & stats["lpm"].eq("exp_shifted")
            & stats["relative_error"].eq(0.2)
        ],
        "figureA1_error_sensitivity.csv": stats[
            (
                stats["experiment_id"].str.startswith("error_")
                | stats["experiment_id"].str.startswith("main_")
            )
            & stats["mode"].eq("successive_with_prior")
        ],
        "F11_initialization_robustness.csv": stats[
            stats["experiment_id"].str.startswith("init_F11_")
        ],
        "F11_tracer_sensitivity.csv": stats[
            stats["experiment_id"].str.startswith("tracer_F11_")
            | stats["experiment_id"].str.startswith("main_F11_")
        ],
    }
    for filename, frame in definitions.items():
        path = derived / filename
        frame.to_csv(path, index=False)
        tables[filename] = path
    return tables


def collect_diagnostics(root: Path, derived: Path) -> Path:
    """Write acceptance and convergence summaries for every discovered case."""
    records = []
    for run_dir in run_directories(root):
        for result_file in (run_dir / "workflow").glob(
            "**/Metropolis_Hastings/results_calibration.txt"
        ):
            values = _read_key_values(result_file)
            required_fields = {
                "chain_count",
                "mean_acceptance_rate",
                "qualification_status",
            }
            missing_fields = sorted(required_fields.difference(values))
            if missing_fields:
                missing = ", ".join(missing_fields)
                raise ValueError(
                    f"{result_file} does not follow the current MH result schema; "
                    f"missing: {missing}"
                )
            diagnostics_file = result_file.with_name("mcmc_diagnostics.tsv")
            diagnostics = (
                pd.read_csv(diagnostics_file, sep="\t")
                if diagnostics_file.is_file()
                else pd.DataFrame()
            )
            qualified_diagnostics = diagnostics
            if "included_in_qualification" in diagnostics:
                qualified_diagnostics = diagnostics.loc[
                    _boolean_series(_column(diagnostics, "included_in_qualification"))
                ]

            stats_file = result_file.with_name("distributions_stats.txt")
            finite = False
            if stats_file.is_file():
                samples = pd.read_csv(stats_file, sep="\t")
                finite = bool(
                    np.isfinite(
                        samples.select_dtypes(include="number").to_numpy()
                    ).all()
                )
            diagnostics_qualified = False
            if "qualified" in qualified_diagnostics and not qualified_diagnostics.empty:
                diagnostics_qualified = bool(
                    _boolean_series(_column(qualified_diagnostics, "qualified")).all()
                )
            records.append(
                {
                    "experiment_id": run_dir.name,
                    "case": str(
                        result_file.parent.parent.relative_to(run_dir / "workflow")
                    ),
                    "qualification_status": values["qualification_status"],
                    "chain_count": pd.to_numeric(
                        values["chain_count"],
                        errors="coerce",
                    ),
                    "mean_acceptance_rate": pd.to_numeric(
                        values["mean_acceptance_rate"], errors="coerce"
                    ),
                    "max_rhat": _diagnostic_extreme(
                        qualified_diagnostics, "rhat", "max"
                    ),
                    "min_bulk_ess": _diagnostic_extreme(
                        qualified_diagnostics, "bulk_ess", "min"
                    ),
                    "min_tail_ess": _diagnostic_extreme(
                        qualified_diagnostics, "tail_ess", "min"
                    ),
                    "max_mcse_mean": _diagnostic_extreme(
                        qualified_diagnostics, "mcse_mean", "max"
                    ),
                    "diagnostics_qualified": diagnostics_qualified,
                    "finite_posterior": finite,
                }
            )
    path = derived / "mcmc_diagnostics.csv"
    derived.mkdir(parents=True, exist_ok=True)
    pd.DataFrame.from_records(
        records,
        columns=[
            "experiment_id",
            "case",
            "qualification_status",
            "chain_count",
            "mean_acceptance_rate",
            "max_rhat",
            "min_bulk_ess",
            "min_tail_ess",
            "max_mcse_mean",
            "diagnostics_qualified",
            "finite_posterior",
        ],
    ).to_csv(path, index=False)
    return path


__all__ = [
    "REPO_ROOT",
    "collect_diagnostics",
    "collect_statistics",
    "latest_scenario_outputs",
    "profile_root",
    "run_directories",
    "save_derived_tables",
]
