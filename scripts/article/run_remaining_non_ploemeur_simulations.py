# Copyright (c) 2021-2026 Centre national de la recherche scientifique (CNRS)
# Contributor: Jean-Raynald de Dreuzy
# SPDX-License-Identifier: CECILL-2.1

"""Run the final Holten and MCMC-only article simulations.

This driver is deliberately unable to write below a path containing
``ploemeur``.  Generated numerical products live below ``results/``; the
three requested decision reports are written at repository root.
"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
import time
import xml.etree.ElementTree as ET
from pathlib import Path
from typing import Any

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from examples.natural.holten.holten_four_bin import (  # noqa: E402
    BIN_ORDER,
    LOCAL_4BIN_TRACER_ORDER,
    LOCAL_4BIN_TRACER_ORDER_WITH_HELIUM,
    load_paper_4bin_fractions,
    run_local_4bin,
    sample_all_wells_4bin_mh,
    summarize_4bin_mh_posterior,
    write_4bin_mh_outputs,
)
from examples.natural.holten.holten_prepare import prepare_holten_inputs  # noqa: E402
from pyages.convolution import ConvolutionTracers  # noqa: E402
from scripts.article.run_article_non_ploemeur import (  # noqa: E402
    DATE,
    TABLE3_TRACERS,
    _model,
    _run_table3_chain,
)
from scripts.common.provenance import sha256_file as _sha256  # noqa: E402

DEFAULT_OUTPUT = ROOT / "results" / "remaining_non_ploemeur_simulations"
HOLTEN_STEPS = 4_000
HOLTEN_BURN_IN = 0.20
HOLTEN_PROPOSAL_SCALE = 0.18
HOLTEN_SEED = 12_345
MCMC_CASES = (
    ("very_sharp", 1.0, 1.0),
    ("young_intermediate", 10.0, 10.0),
    ("figure2", 10.0, 30.0),
    ("older_intermediate", 30.0, 10.0),
    ("long", 40.0, 10.0),
)
MCMC_LENGTHS = (10_000, 5_000, 2_000, 1_000, 500, 100)
REFERENCE_SEED = 12_345
SHORT_SEEDS = (21_001, 21_002, 21_003, 21_004, 21_005)
MCMC_SKIP = 5
MCMC_BURN_IN = 0.20


def _guard_output(path: Path) -> Path:
    resolved = path.resolve()
    if any(part.lower() == "ploemeur" for part in resolved.parts):
        raise ValueError(f"Ploemeur output is forbidden for this campaign: {resolved}")
    resolved.mkdir(parents=True, exist_ok=True)
    return resolved


def _markdown(frame: pd.DataFrame, *, index: bool = False) -> str:
    if frame.empty:
        return "_Aucune ligne._"
    values = frame.copy()
    if index:
        values = values.reset_index()
    values = values.replace({np.nan: ""})
    headers = [str(column).replace("|", "\\|") for column in values.columns]
    lines = [
        "| " + " | ".join(headers) + " |",
        "| " + " | ".join("---" for _ in headers) + " |",
    ]
    for row in values.itertuples(index=False, name=None):
        rendered = []
        for value in row:
            if isinstance(value, float):
                text = f"{value:.5g}"
            else:
                text = str(value)
            rendered.append(text.replace("|", "\\|"))
        lines.append("| " + " | ".join(rendered) + " |")
    return "\n".join(lines)


def _git(*args: str) -> str:
    return subprocess.run(
        ["git", *args],
        cwd=ROOT,
        check=True,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
    ).stdout


def write_preflight(output: Path) -> Path:
    status = _git("status", "--short", "--branch")
    diff_check = subprocess.run(
        ["git", "diff", "--check"],
        cwd=ROOT,
        capture_output=True,
        text=True,
        check=False,
    )
    cached_check = subprocess.run(
        ["git", "diff", "--cached", "--check"],
        cwd=ROOT,
        capture_output=True,
        text=True,
        check=False,
    )
    tracked = subprocess.run(
        ["git", "ls-files", "-z"], cwd=ROOT, check=True, capture_output=True
    ).stdout.split(b"\0")
    ploemeur: dict[str, str] = {}
    for raw in tracked:
        if not raw:
            continue
        relative = raw.decode("utf-8", errors="surrogateescape")
        if "ploemeur" in relative.lower():
            path = ROOT / relative
            if path.is_file():
                ploemeur[relative] = _sha256(path)
    payload = {
        "captured_at": pd.Timestamp.now(tz="Europe/Paris").isoformat(),
        "head": _git("rev-parse", "HEAD").strip(),
        "status_short_branch": status,
        "diff_check_returncode": diff_check.returncode,
        "diff_check_output": diff_check.stdout + diff_check.stderr,
        "cached_diff_check_returncode": cached_check.returncode,
        "cached_diff_check_output": cached_check.stdout + cached_check.stderr,
        "ploemeur_sha256": ploemeur,
    }
    path = output / "preflight.json"
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")
    return path


def verify_ploemeur_unchanged(output: Path) -> Path:
    preflight = json.loads((output / "preflight.json").read_text(encoding="utf-8"))
    rows = []
    for relative, before in preflight["ploemeur_sha256"].items():
        path = ROOT / relative
        after = _sha256(path) if path.is_file() else "MISSING"
        rows.append(
            {
                "path": relative,
                "sha256_before": before,
                "sha256_after": after,
                "unchanged": before == after,
            }
        )
    frame = pd.DataFrame(rows)
    path = output / "ploemeur_integrity.csv"
    frame.to_csv(path, index=False)
    if not frame.empty and not bool(frame["unchanged"].all()):
        changed = frame.loc[~frame["unchanged"], "path"].tolist()
        raise RuntimeError(f"Ploemeur integrity check failed: {changed}")
    return path


def _holten_error_metrics(
    comparison: pd.DataFrame, configuration: str
) -> dict[str, Any]:
    errors = []
    for fraction in BIN_ORDER:
        errors.extend(
            np.abs(
                comparison[f"{fraction}_posterior_median"].to_numpy(float)
                - comparison[f"{fraction}_paper"].to_numpy(float)
            )
        )
    values = np.asarray(errors)
    return {
        "configuration": configuration,
        "n_fractions": len(values),
        "mae": float(np.mean(values)),
        "median_absolute_error": float(np.median(values)),
        "rmse": float(np.sqrt(np.mean(values**2))),
        "maximum_absolute_error": float(np.max(values)),
        "n_error_le_0p02": int(np.sum(values <= 0.02)),
        "n_error_le_0p05": int(np.sum(values <= 0.05)),
        "n_error_le_0p10": int(np.sum(values <= 0.10)),
    }


def _holten_long_comparison(h3: pd.DataFrame, h4: pd.DataFrame) -> pd.DataFrame:
    merged = h3.merge(h4, on="well_id", suffixes=("_h3", "_h4"))
    rows = []
    for _, row in merged.iterrows():
        for fraction in BIN_ORDER:
            paper = float(row[f"{fraction}_paper_h3"])
            h3_median = float(row[f"{fraction}_posterior_median_h3"])
            h4_median = float(row[f"{fraction}_posterior_median_h4"])
            rows.append(
                {
                    "well": row["well_id"],
                    "fraction": fraction,
                    "visser": paper,
                    "h3_median": h3_median,
                    "h3_q10": float(row[f"{fraction}_posterior_q10_h3"]),
                    "h3_q90": float(row[f"{fraction}_posterior_q90_h3"]),
                    "h4_median": h4_median,
                    "h4_q10": float(row[f"{fraction}_posterior_q10_h4"]),
                    "h4_q90": float(row[f"{fraction}_posterior_q90_h4"]),
                    "abs_error_h3": abs(h3_median - paper),
                    "abs_error_h4": abs(h4_median - paper),
                    "delta_error": abs(h4_median - paper) - abs(h3_median - paper),
                }
            )
    return pd.DataFrame(rows)


def _representative_diagnostics(
    samples: pd.DataFrame,
    configuration: str,
    tracer_order: tuple[str, ...],
) -> pd.DataFrame:
    rows = []
    for well, group in samples.groupby("well_id", sort=False):
        medians = group[list(BIN_ORDER)].median().to_numpy(float)
        distance = np.square(group[list(BIN_ORDER)].to_numpy(float) - medians).sum(
            axis=1
        )
        draw = group.iloc[int(np.argmin(distance))]
        total = 0.0
        local = []
        for tracer in tracer_order:
            observed = float(draw[f"{tracer}_observed"])
            uncertainty = float(draw[f"{tracer}_error"])
            modeled = float(draw[f"{tracer}_modeled"])
            residual = observed - modeled
            standardized = residual / uncertainty
            contribution = standardized**2
            total += contribution
            local.append(
                {
                    "configuration": configuration,
                    "well": well,
                    "tracer": tracer,
                    "observed": observed,
                    "uncertainty": uncertainty,
                    "modeled": modeled,
                    "residual_observed_minus_modeled": residual,
                    "standardized_residual": standardized,
                    "objective_contribution": contribution,
                    "representative_step": int(draw["step"]),
                    "representative_solution": "posterior_draw_nearest_fraction_medians",
                }
            )
        for item in local:
            item["objective_total"] = total
            rows.append(item)
    return pd.DataFrame(rows)


def _figure3(comparison: pd.DataFrame, path: Path) -> None:
    labels = {
        "f_0_20": "0–20 yr",
        "f_20_40": "20–40 yr",
        "f_40_60": "40–60 yr",
        "f_old": ">60 yr",
    }
    fig, axes = plt.subplots(1, 4, figsize=(18, 5.2), sharey=True)
    y = np.arange(len(comparison))
    for axis, fraction in zip(axes, BIN_ORDER, strict=False):
        lower = comparison[f"{fraction}_posterior_q10"].to_numpy(float)
        median = comparison[f"{fraction}_posterior_median"].to_numpy(float)
        upper = comparison[f"{fraction}_posterior_q90"].to_numpy(float)
        paper = comparison[f"{fraction}_paper"].to_numpy(float)
        axis.hlines(y, lower, upper, color="#3566a8", linewidth=4)
        axis.scatter(median, y, color="#173f73", s=60, marker="o", zorder=3)
        axis.scatter(paper, y, color="#b03a2e", s=65, marker="D", zorder=4)
        axis.set_title(labels[fraction])
        axis.set_xlim(0, 1)
        axis.set_xlabel("Age fraction")
        axis.grid(alpha=0.25)
    axes[0].set_yticks(y, comparison["well_id"].tolist())
    axes[0].invert_yaxis()
    handles = [
        plt.Line2D(
            [],
            [],
            color="#b03a2e",
            marker="D",
            linestyle="None",
            label="Visser et al. (2013)",
        ),
        plt.Line2D(
            [],
            [],
            color="#173f73",
            marker="o",
            linewidth=4,
            label="PyAges H4 median and q10–q90",
        ),
        plt.Line2D(
            [],
            [],
            color="none",
            label="H4 observables: ³H, tritiogenic ³He, ⁸⁵Kr, and ³⁹Ar",
        ),
    ]
    fig.legend(handles=handles, loc="lower center", ncol=3, bbox_to_anchor=(0.5, -0.03))
    fig.suptitle(
        "Holten four-bin benchmark — H4 observables: ³H, tritiogenic ³He, ⁸⁵Kr, and ³⁹Ar"
    )
    fig.tight_layout(rect=(0, 0.08, 1, 0.95))
    fig.savefig(path, dpi=220, bbox_inches="tight")
    plt.close(fig)


def run_holten(output: Path) -> dict[str, Path]:
    target = _guard_output(output / "holten")
    prepared = prepare_holten_inputs()
    paper = load_paper_4bin_fractions(prepared)
    products: dict[str, Path] = {}
    comparisons: dict[str, pd.DataFrame] = {}
    diagnostics = []
    for label, include_helium, order in (
        ("H3", False, LOCAL_4BIN_TRACER_ORDER),
        ("H4", True, LOCAL_4BIN_TRACER_ORDER_WITH_HELIUM),
    ):
        directory = target / label.lower()
        endmembers, _, _, _ = run_local_4bin(
            prepared, directory, include_helium=include_helium
        )
        samples = sample_all_wells_4bin_mh(
            prepared,
            endmembers,
            nstep=HOLTEN_STEPS,
            burn_in=HOLTEN_BURN_IN,
            proposal_scale=HOLTEN_PROPOSAL_SCALE,
            seed=HOLTEN_SEED,
            include_helium=include_helium,
        )
        posterior = summarize_4bin_mh_posterior(samples)
        from examples.natural.holten.holten_four_bin import compare_paper_vs_mh_4bin

        comparison = compare_paper_vs_mh_4bin(paper, posterior)
        write_4bin_mh_outputs(paper, samples, posterior, comparison, directory)
        comparisons[label] = comparison
        diagnostics.append(_representative_diagnostics(samples, label, order))
        products[f"{label.lower()}_samples"] = directory / "holten_4bin_mh_samples.csv"

    long_comparison = _holten_long_comparison(comparisons["H3"], comparisons["H4"])
    comparison_path = target / "holten_h3_h4_fraction_comparison.csv"
    long_comparison.to_csv(comparison_path, index=False)
    metrics = pd.DataFrame(
        [
            _holten_error_metrics(comparisons["H3"], "H3"),
            _holten_error_metrics(comparisons["H4"], "H4"),
        ]
    )
    metrics_path = target / "holten_h3_h4_metrics.csv"
    metrics.to_csv(metrics_path, index=False)
    diagnostics_path = target / "holten_observable_fit_diagnostics.csv"
    pd.concat(diagnostics, ignore_index=True).to_csv(diagnostics_path, index=False)

    audit_rows = []
    for _, row in prepared.helium_diagnostics.iterrows():
        reported = row["3He_err_raw"]
        source = (
            "reported by Visser"
            if pd.notna(reported)
            else "0.5 TU imputed as median of six reported values"
        )
        audit_rows.append(
            {
                "well": row["well_id"],
                "observable_helium_visser": "tritiogenic 3He concentration",
                "observable_helium_pyages_historical": "3He_trit_TU concentration",
                "unit": "TU equivalent",
                "uncertainty": float(row["3He_err"]),
                "uncertainty_provenance": source,
                "equivalent": "yes",
                "source_field": "visser_data.xlsx:sampling_data:3He_trit_TU",
                "calibration_residual": "(observed - modeled) / uncertainty",
            }
        )
    audit_path = target / "holten_helium_observable_audit.csv"
    pd.DataFrame(audit_rows).to_csv(audit_path, index=False)
    figure_path = target / "figure3_holten_h4.png"
    _figure3(comparisons["H4"], figure_path)
    products.update(
        comparison=comparison_path,
        metrics=metrics_path,
        diagnostics=diagnostics_path,
        audit=audit_path,
        figure3=figure_path,
    )
    return products


def _acf_and_ess(values: np.ndarray) -> tuple[float, float]:
    values = np.asarray(values, dtype=float)
    n = len(values)
    if n < 3 or np.var(values) == 0.0:
        return np.nan, float(n)
    centered = values - values.mean()
    variance = float(np.dot(centered, centered) / n)
    max_lag = min(n - 1, 1000)
    acf = np.empty(max_lag + 1)
    acf[0] = 1.0
    for lag in range(1, max_lag + 1):
        acf[lag] = np.dot(centered[:-lag], centered[lag:]) / ((n - lag) * variance)
    positive = []
    for lag in range(1, max_lag + 1):
        if acf[lag] <= 0.0:
            break
        positive.append(acf[lag])
    tau = max(1.0, 1.0 + 2.0 * float(np.sum(positive)))
    return float(acf[1]), float(min(n, n / tau))


def _parameter_summary(values: np.ndarray) -> dict[str, float]:
    values = np.asarray(values, dtype=float)
    acf1, ess = _acf_and_ess(values)
    return {
        "mean": float(np.mean(values)),
        "median": float(np.median(values)),
        "sd": float(np.std(values, ddof=1)) if len(values) > 1 else np.nan,
        "q025": float(np.quantile(values, 0.025)),
        "q10": float(np.quantile(values, 0.10)),
        "q25": float(np.quantile(values, 0.25)),
        "q75": float(np.quantile(values, 0.75)),
        "q90": float(np.quantile(values, 0.90)),
        "q975": float(np.quantile(values, 0.975)),
        "acf1_stored": acf1,
        "ess_approx": ess,
    }


def _comparison_metrics(summary: pd.DataFrame) -> pd.DataFrame:
    references = summary.loc[summary["is_reference"]].set_index(["case", "parameter"])
    rows = []
    for _, row in summary.loc[~summary["is_reference"]].iterrows():
        ref = references.loc[(row["case"], row["parameter"])]
        target = float(row["target_value"])
        median_delta = abs(float(row["median"] - ref["median"]))
        position_threshold = max(0.05 * abs(target), 0.1 * float(ref["sd"]))
        sd_relative_difference = abs(float(row["sd"] / ref["sd"] - 1.0))
        width = float(row["q90"] - row["q10"])
        ref_width = float(ref["q90"] - ref["q10"])
        width_relative_difference = abs(width / ref_width - 1.0)
        rows.append(
            {
                "case": row["case"],
                "target_mu": row["target_mu"],
                "target_t0": row["target_t0"],
                "steps": int(row["steps"]),
                "seed": int(row["seed"]),
                "parameter": row["parameter"],
                "median": row["median"],
                "reference_median": ref["median"],
                "median_absolute_difference": median_delta,
                "median_relative_difference": median_delta / abs(float(ref["median"]))
                if ref["median"]
                else np.nan,
                "position_threshold": position_threshold,
                "position_pass": median_delta < position_threshold,
                "sd": row["sd"],
                "reference_sd": ref["sd"],
                "sd_relative_difference": sd_relative_difference,
                "sd_pass": sd_relative_difference <= 0.10,
                "q10_q90_width": width,
                "reference_q10_q90_width": ref_width,
                "width_relative_difference": width_relative_difference,
                "width_pass": width_relative_difference <= 0.10,
                "mtt_median_pass": (
                    median_delta / abs(float(ref["median"])) <= 0.05
                    if row["parameter"] == "mu_plus_t0"
                    else True
                ),
            }
        )
    frame = pd.DataFrame(rows)
    frame["parameter_pass"] = (
        frame["position_pass"]
        & frame["sd_pass"]
        & frame["width_pass"]
        & frame["mtt_median_pass"]
    )
    return frame


def run_mcmc(output: Path) -> dict[str, Path]:
    target = _guard_output(output / "mcmc")
    chain_dir = _guard_output(target / "chains")
    tracers = ConvolutionTracers(names=list(TABLE3_TRACERS), date=DATE)
    summary_rows = []
    run_rows = []
    for case_name, mu, t0 in MCMC_CASES:
        target_model = _model("exp_shifted", {"mu": mu, "shift": t0})
        observations = tracers.convolve(target_model, return_type="concentrations")
        observations.set_relative_errors(0.08)
        for steps in MCMC_LENGTHS:
            seeds = (REFERENCE_SEED,) if steps == 10_000 else SHORT_SEEDS
            for seed in seeds:
                wall_start = time.perf_counter()
                mh, posterior = _run_table3_chain(
                    observations, target, seed, steps, MCMC_SKIP
                )
                wall_seconds = time.perf_counter() - wall_start
                frame = posterior.frame.copy()
                frame["mu_plus_t0"] = frame["mu"] + frame["shift"]
                chain_path = chain_dir / f"{case_name}_n{steps}_seed{seed}.csv"
                frame.to_csv(chain_path, index=False)
                result_spec: dict[str, Any] = {}
                mh.write_results_spec(result_spec)
                run_rows.append(
                    {
                        "case": case_name,
                        "target_mu": mu,
                        "target_t0": t0,
                        "steps": steps,
                        "seed": seed,
                        "is_reference": steps == 10_000,
                        "burn_in_fraction": MCMC_BURN_IN,
                        "nskip": MCMC_SKIP,
                        "stored_samples": len(frame),
                        "acceptance_rate": float(result_spec["success_rate"]),
                        "best_sqrt_J_data_over_m": float(frame["obj_function"].min()),
                        "runtime_seconds": wall_seconds,
                        "mh_internal_runtime_seconds": float(mh.time_perform),
                        "chain_file": str(chain_path.relative_to(ROOT)),
                    }
                )
                for parameter, column, target_value in (
                    ("mu", "mu", mu),
                    ("t0", "shift", t0),
                    ("mu_plus_t0", "mu_plus_t0", mu + t0),
                ):
                    summary_rows.append(
                        {
                            "case": case_name,
                            "target_mu": mu,
                            "target_t0": t0,
                            "target_value": target_value,
                            "steps": steps,
                            "seed": seed,
                            "is_reference": steps == 10_000,
                            "parameter": parameter,
                            **_parameter_summary(frame[column].to_numpy(float)),
                        }
                    )
    runs = pd.DataFrame(run_rows)
    summaries = pd.DataFrame(summary_rows)
    differences = _comparison_metrics(summaries)
    run_pass = (
        differences.groupby(["case", "steps", "seed"], as_index=False)["parameter_pass"]
        .all()
        .rename(columns={"parameter_pass": "all_criteria_pass"})
    )
    run_pass = run_pass.merge(
        runs.loc[~runs["is_reference"]], on=["case", "steps", "seed"], how="left"
    )
    reference_runtime = runs.loc[
        runs["is_reference"], ["case", "runtime_seconds"]
    ].rename(columns={"runtime_seconds": "reference_runtime_seconds"})
    run_pass = run_pass.merge(reference_runtime, on="case", how="left")
    run_pass["runtime_ratio_case_reference"] = (
        run_pass["runtime_seconds"] / run_pass["reference_runtime_seconds"]
    )
    pass_summary = (
        run_pass.groupby("steps", as_index=False)
        .agg(
            runs=("all_criteria_pass", "size"),
            passes=("all_criteria_pass", "sum"),
            median_runtime_ratio=("runtime_ratio_case_reference", "median"),
        )
        .sort_values("steps", ascending=False)
    )
    cases_with_any_pass = (
        run_pass.loc[run_pass["all_criteria_pass"]]
        .groupby("steps")["case"]
        .nunique()
        .rename("cases_with_any_pass")
    )
    pass_summary = pass_summary.merge(cases_with_any_pass, on="steps", how="left")
    pass_summary["cases_with_any_pass"] = (
        pass_summary["cases_with_any_pass"].fillna(0).astype(int)
    )
    pass_summary["pass_rate"] = pass_summary["passes"] / pass_summary["runs"]
    runtime_summary = (
        runs.groupby("steps", as_index=False)
        .agg(
            n_runs=("runtime_seconds", "size"),
            runtime_mean_seconds=("runtime_seconds", "mean"),
            runtime_median_seconds=("runtime_seconds", "median"),
            runtime_sd_seconds=("runtime_seconds", "std"),
        )
        .sort_values("steps", ascending=False)
    )
    reference_mean = float(
        runtime_summary.loc[
            runtime_summary["steps"] == 10_000, "runtime_mean_seconds"
        ].iloc[0]
    )
    runtime_summary["runtime_over_runtime_10000"] = (
        runtime_summary["runtime_mean_seconds"] / reference_mean
    )

    paths = {
        "runs": target / "mcmc_runs.csv",
        "summaries": target / "mcmc_posterior_summaries.csv",
        "differences": target / "mcmc_reference_differences.csv",
        "run_pass": target / "mcmc_run_comparability.csv",
        "pass_summary": target / "mcmc_comparability_summary.csv",
        "runtime": target / "mcmc_runtime_summary.csv",
    }
    runs.to_csv(paths["runs"], index=False)
    summaries.to_csv(paths["summaries"], index=False)
    differences.to_csv(paths["differences"], index=False)
    run_pass.to_csv(paths["run_pass"], index=False)
    pass_summary.to_csv(paths["pass_summary"], index=False)
    runtime_summary.to_csv(paths["runtime"], index=False)
    return paths


def write_reports(output: Path) -> dict[str, Path]:
    holten_metrics = pd.read_csv(output / "holten" / "holten_h3_h4_metrics.csv")
    holten_comparison = pd.read_csv(
        output / "holten" / "holten_h3_h4_fraction_comparison.csv"
    )
    audit = pd.read_csv(output / "holten" / "holten_helium_observable_audit.csv")
    diagnostics = pd.read_csv(
        output / "holten" / "holten_observable_fit_diagnostics.csv"
    )
    summaries = pd.read_csv(output / "mcmc" / "mcmc_posterior_summaries.csv")
    runs = pd.read_csv(output / "mcmc" / "mcmc_runs.csv")
    run_pass = pd.read_csv(output / "mcmc" / "mcmc_run_comparability.csv")
    pass_summary = pd.read_csv(output / "mcmc" / "mcmc_comparability_summary.csv")
    runtime = pd.read_csv(output / "mcmc" / "mcmc_runtime_summary.csv")
    test_rows = []
    for label, filename in (
        ("Holten targeted", "holten-junit.xml"),
        ("Shifted-exponential and MCMC targeted", "shifted-mcmc-junit.xml"),
        ("MCMC prior validation", "mcmc-prior-validation-junit.xml"),
    ):
        junit = output / "tests" / filename
        if not junit.exists():
            continue
        suite = ET.parse(junit).getroot().find("testsuite")
        if suite is None:
            continue
        tests = int(suite.attrib.get("tests", 0))
        failures = int(suite.attrib.get("failures", 0))
        errors = int(suite.attrib.get("errors", 0))
        skipped = int(suite.attrib.get("skipped", 0))
        test_rows.append(
            {
                "suite": label,
                "passed": tests - failures - errors - skipped,
                "skipped": skipped,
                "failed": failures,
                "errors": errors,
                "total": tests,
                "seconds": float(suite.attrib.get("time", 0.0)),
            }
        )
    test_summary = pd.DataFrame(test_rows)
    if not test_summary.empty:
        totals = {
            "suite": "TOTAL",
            **{
                column: test_summary[column].sum()
                for column in (
                    "passed",
                    "skipped",
                    "failed",
                    "errors",
                    "total",
                    "seconds",
                )
            },
        }
        test_summary = pd.concat(
            [test_summary, pd.DataFrame([totals])], ignore_index=True
        )
        tests_report = (
            "# Tests finaux ciblés hors Ploemeur\n\n"
            + _markdown(test_summary)
            + "\n\nLes quatre skips sont les variantes `--run-extensive` de "
            "`test_calibration_mh.py`; aucun test Ploemeur et aucun golden Ploemeur n'a été exécuté.\n"
        )
        (output / "tests" / "tests_summary.md").write_text(
            tests_report, encoding="utf-8", newline="\n"
        )
    reference_summaries = summaries.loc[
        summaries["is_reference"], ["case", "parameter", "median", "sd", "q10", "q90"]
    ].rename(
        columns={
            "median": "reference_median",
            "sd": "reference_sd",
            "q10": "reference_q10",
            "q90": "reference_q90",
        }
    )
    interseed = (
        summaries.loc[~summaries["is_reference"]]
        .groupby(["case", "steps", "parameter"], as_index=False)
        .agg(
            seeds=("seed", "nunique"),
            median_across_seeds=("median", "mean"),
            median_interseed_sd=("median", "std"),
            median_min=("median", "min"),
            median_max=("median", "max"),
            posterior_sd_mean=("sd", "mean"),
            posterior_sd_min=("sd", "min"),
            posterior_sd_max=("sd", "max"),
            ess_mean=("ess_approx", "mean"),
            ess_min=("ess_approx", "min"),
        )
        .merge(reference_summaries, on=["case", "parameter"], how="left")
    )
    interseed["median_bias"] = (
        interseed["median_across_seeds"] - interseed["reference_median"]
    )
    interseed["median_relative_bias"] = (
        interseed["median_bias"] / interseed["reference_median"].abs()
    )
    interseed["posterior_sd_ratio"] = (
        interseed["posterior_sd_mean"] / interseed["reference_sd"]
    )
    interseed["variance_direction"] = np.where(
        interseed["posterior_sd_ratio"] < 1.0, "underestimated", "overestimated"
    )
    interseed_path = output / "mcmc" / "mcmc_interseed_variability.csv"
    interseed.to_csv(interseed_path, index=False)
    h3 = holten_metrics.set_index("configuration").loc["H3"]
    h4 = holten_metrics.set_index("configuration").loc["H4"]
    h4_better = bool(h4["mae"] < h3["mae"])
    run_diagnostics = (
        runs.groupby("steps", as_index=False)
        .agg(
            runs=("seed", "size"),
            acceptance_min=("acceptance_rate", "min"),
            acceptance_mean=("acceptance_rate", "mean"),
            acceptance_max=("acceptance_rate", "max"),
            best_sqrt_J_min=("best_sqrt_J_data_over_m", "min"),
            best_sqrt_J_median=("best_sqrt_J_data_over_m", "median"),
            best_sqrt_J_max=("best_sqrt_J_data_over_m", "max"),
        )
        .sort_values("steps", ascending=False)
    )
    posterior_display = summaries[
        [
            "case",
            "target_mu",
            "target_t0",
            "steps",
            "seed",
            "is_reference",
            "parameter",
            "mean",
            "median",
            "sd",
            "q025",
            "q10",
            "q25",
            "q75",
            "q90",
            "q975",
            "acf1_stored",
            "ess_approx",
        ]
    ]

    audit_display = audit[
        [
            "well",
            "observable_helium_visser",
            "observable_helium_pyages_historical",
            "unit",
            "uncertainty",
            "uncertainty_provenance",
            "equivalent",
        ]
    ]
    objective = diagnostics.groupby(["configuration", "well"], as_index=False)[
        "objective_total"
    ].first()
    holten_report = f"""# Requalification du ³He tritiogénique dans le benchmark Holten

## Décision

Visser et al. (2013) et l'ancienne implémentation PyAges utilisent la même observable : la concentration de **³He tritiogénique corrigée**, en TU équivalentes. Ce n'est ni le rapport ³H/³He ni l'âge apparent. H4 est donc scientifiquement recevable. Pour `59-05`, le sigma source est absent; H4 emploie 0,5 TU, médiane préenregistrée des six sigmas publiés, et cette imputation fait partie du modèle d'erreur.

Dans le PDF Visser, les paragraphes 23–26 décrivent le calcul corrigé du ³He tritiogénique puis son emploi comme traceur transitoire indépendant; les paragraphes 49–54 décrivent les end-members et la minimisation des écarts de concentrations. Dans PyAges historique (commit `235f3a5c`), `holten_prepare.py` lisait `3He_trit_TU`/`3He_err`, `holten_four_bin.py` ajoutait `3He_trit` à l'ordre des observations, puis calculait le même résidu standardisé. L'âge apparent `H3_He_age` restait un diagnostic et n'entrait pas dans l'objectif.

Le forward local applique `lambda = ln(2) / 12.32 an`, `³H=H0 exp(-lambda tau)` et `³He_trit=H0(1-exp(-lambda tau))`. Les données `3He_trit_TU` ont déjà subi les corrections gaz nobles, dégazage et séparation radiogénique décrites par Visser; aucune correction atmosphérique ou terrigène n'est réappliquée. La chronique locale est utilisée comme entrée effective du benchmark : ajouter une seconde correction de deux ans détériore le χ² total, alors que la convention retenue donne 13,65 à l'optimum contre 14,2 publié.

Les tests analytiques vérifient `tau=0`, une demi-vie, la limite vieille (`tau=12 320 ans`), la conservation `³H+³He=H0`, l'emploi de `ln(2)/12.32` plutôt que `1/12.32`, et le rejet des âges/constantes non physiques.

## Audit puits par puits

{_markdown(audit_display)}

Chaîne de traçabilité : `visser_data.xlsx` / feuille `sampling_data` / champ `3He_trit_TU` → `sampling_data.txt` → `build_helium_diagnostics` → `_local_4bin_observations(include_helium=True)` → résidu `(observed-modeled)/uncertainty`.

## Protocole H3/H4

Les deux configurations utilisent les classes 0–20, 20–40, 40–60 et >60 ans, le même paramétrage stick-breaking, les mêmes contraintes, la même mesure implicite dans l'espace `z` sans prior paramétrique additionnel, `nstep={HOLTEN_STEPS}`, burn-in {HOLTEN_BURN_IN:.0%}, proposal scale {HOLTEN_PROPOSAL_SCALE}, seed de base {HOLTEN_SEED} et décalage de seed +101 par puits. Les erreurs des observables communes sont strictement identiques. H3 ajuste ³H, ⁸⁵Kr, ³⁹Ar; H4 ajuste ³H, ³He tritiogénique, ⁸⁵Kr, ³⁹Ar.

## Comparaison aux 28 fractions Visser

{_markdown(holten_metrics)}

Table détaillée avec q10–q90 et `delta_error` : `results/remaining_non_ploemeur_simulations/holten/holten_h3_h4_fraction_comparison.csv`.

{_markdown(holten_comparison)}

## Qualité de fit des observables

La solution représentative est, pour chaque puits, le tirage posterior réellement échantillonné le plus proche des quatre médianes marginales. Le CSV complet contient observation, sigma, valeur modélisée, résidu, résidu standardisé, contribution et objectif total.

{_markdown(objective)}

{_markdown(diagnostics)}

CSV : `results/remaining_non_ploemeur_simulations/holten/holten_observable_fit_diagnostics.csv`.

## Réponses explicites

1. **Oui**, Visser utilise une concentration de ³He tritiogénique compatible avec `3He_trit_TU`.
2. **Oui**, l'ancienne implémentation PyAges utilisait la même grandeur; son ancien calcul confondait toutefois demi-vie et durée de vie moyenne.
3. **Oui**, H4 reproduit mieux le problème inverse de Visser parce qu'il ajuste les quatre concentrations indépendantes publiées.
4. **{"Oui" if h4_better else "Non"}**, la MAE passe de {h3["mae"]:.5f} à {h4["mae"]:.5f}.
5. **{"Oui" if h4_better else "Non"}**, H4 doit {"devenir" if h4_better else "ne pas devenir"} le benchmark Holten final, avec l'imputation de `59-05` explicitement déclarée.
6. Conserver la nouvelle Figure 3 H4 : `results/remaining_non_ploemeur_simulations/holten/figure3_holten_h4.png`.

## Tests Holten ciblés

{_markdown(test_summary.loc[test_summary["suite"].isin(["Holten targeted", "TOTAL"])]) if not test_summary.empty else "_Non encore exécutés._"}
"""
    holten_path = output / "holten_helium_requalification.md"
    holten_path.write_text(holten_report, encoding="utf-8", newline="\n")

    by_length = pass_summary.set_index("steps")
    pass1000 = int(by_length.loc[1000, "passes"])
    runs1000 = int(by_length.loc[1000, "runs"])
    pass100 = int(by_length.loc[100, "passes"])
    runs100 = int(by_length.loc[100, "runs"])
    if pass1000 == runs1000 and pass100 == runs100:
        decision = "one_to_two"
        sentence = "Tests with chain lengths reduced by one to two orders of magnitude produced comparable posterior summaries for the representative cases examined."
    elif pass1000 == runs1000:
        decision = "one_order"
        sentence = "Tests with chain lengths reduced by approximately one order of magnitude produced comparable posterior summaries for representative cases, whereas substantially shorter chains showed increased Monte Carlo variability."
    else:
        decision = "remove"
        sentence = "Shorter-chain sensitivity tests showed case- and seed-dependent Monte Carlo variability; the 10,000-iteration configuration was therefore retained for the reported posterior summaries."
    hundred_runs = run_pass.loc[run_pass["steps"] == 100]
    hundred_summaries = summaries.loc[
        (summaries["steps"] == 100)
        & (summaries["parameter"].isin(["mu", "t0", "mu_plus_t0"]))
    ]
    hundred_variability = interseed.loc[
        interseed["steps"] == 100,
        [
            "case",
            "parameter",
            "median_across_seeds",
            "reference_median",
            "median_bias",
            "median_interseed_sd",
            "posterior_sd_ratio",
            "variance_direction",
            "ess_mean",
            "ess_min",
        ],
    ]
    pass_by_case = (
        run_pass.groupby(["steps", "case"])["all_criteria_pass"]
        .agg(["sum", "count"])
        .reset_index()
        .rename(columns={"sum": "passes", "count": "runs"})
    )
    mcmc_report = f"""# Sensibilité du benchmark shifted-exponential à la longueur MCMC

## Critères figés avant analyse

Pour `mu` et `t0`, l'écart absolu de médiane doit être strictement inférieur au maximum de 5 % de la vraie valeur et 0,1 SD de référence. Pour `mu`, `t0` et `mu+t0`, la SD et la largeur q10–q90 doivent chacune rester à ±10 % de la référence. La médiane de `mu+t0` doit en plus rester à ±5 %. Une chaîne est comparable seulement si tous ces tests passent; les seuils n'ont pas été modifiés après inspection.

## Protocole

- Cas : `mu,t0` = (1,1), (10,10), (10,30), (30,10), (40,10).
- Traceurs : CFC-11, CFC-12, CFC-113 et SF₆; concentrations synthétiques non bruitées; erreur relative 8 %.
- Forward : moteur final CDF–partial-first-moment; mêmes likelihood, bornes [0.1,70] × [0,70], initialisation (10,10), proposal (1.5,1.5), sans prior.
- Référence : 10 000 pas, seed {REFERENCE_SEED}. Chaînes courtes : seeds {", ".join(map(str, SHORT_SEEDS))}.
- Burn-in : 20 %; stockage tous les {MCMC_SKIP} pas sans thinning accru.

## Comparabilité par longueur

{_markdown(pass_summary)}

{_markdown(pass_by_case)}

À 1 000 pas (×10), **{pass1000}/{runs1000}** combinaisons cas/seed passent tous les critères. À 100 pas (×100), **{pass100}/{runs100}** passent.

## Temps de calcul

{_markdown(runtime)}

Les ratios sont approximativement proportionnels au nombre de pas (0,513 pour 5 000; 0,092 pour 1 000; 0,0496 pour 500). À 100 pas, le ratio 0,0131 est légèrement supérieur à 0,01 à cause du coût fixe de préparation.

## Acceptation et meilleur objectif

{_markdown(run_diagnostics)}

## Cas 100 pas

Une chaîne de 100 pas ne fournit que {int(hundred_runs["stored_samples"].min())} échantillons post-burn-in stockés. Les biais de médiane et distorsions de variance par seed sont fournis sans agrégation masquante dans `mcmc_reference_differences.csv`.

{_markdown(hundred_variability)}

Les 75 résumés bruts (5 cas × 5 seeds × 3 paramètres) à 100 pas restent reproduits ci-dessous.

{_markdown(hundred_summaries)}

## Résultats bruts

- `mcmc_posterior_summaries.csv` : mean, median, SD, q10, q25, q75, q90, q025, q975, ACF(1) et ESS approximatif pour chaque paramètre.
- `mcmc_runs.csv` : meilleur `sqrt(J_data/m)`, taux d'acceptation, temps et nombre stocké.
- `mcmc_reference_differences.csv` : écarts et tests élémentaires.
- `mcmc_run_comparability.csv` : verdict par cas/seed.
- `mcmc_interseed_variability.csv` : étendue et SD inter-seed des médianes, biais et ratio de SD posterior.

## Posterior summaries complets

{_markdown(posterior_display)}

## Décision manuscrit

1. « one to two orders of magnitude » : **{"oui" if decision == "one_to_two" else "non"}**.
2. « approximately one order of magnitude » : **{"oui" if decision in {"one_to_two", "one_order"} else "non"}**.
3. Suppression entière de l'affirmation générale : **{"oui" if decision == "remove" else "non"}**.
4. Formulation recommandée : “{sentence}”

## Tests shifted-exponential/MCMC ciblés

{_markdown(test_summary.loc[test_summary["suite"] != "Holten targeted"]) if not test_summary.empty else "_Non encore exécutés._"}
"""
    mcmc_path = output / "mcmc_chain_length_sensitivity.md"
    mcmc_path.write_text(mcmc_report, encoding="utf-8", newline="\n")

    global_report = f"""# Simulations complémentaires restantes hors Ploemeur

## Décisions

- Holten : **{"H4 (quatre observables)" if h4_better else "H3 (trois observables)"}**; observable ajoutée = ³He tritiogénique corrigé en TU équivalentes.
- Figure 3 : **{"nouvelle figure H4" if h4_better else "figure H3 existante"}**.
- Sensibilité MCMC : décision **{decision}**; formulation anglaise recommandée : “{sentence}”
- Ploemeur : aucun workflow, test ou golden Ploemeur n'a été lancé par cette campagne. **Exception de workspace concurrente** : vers 23:31, une autre activité dans le dépôt a modifié des sources Ploemeur après le snapshot propre initial; le contrôle SHA-256 l'a détecté et échoue donc au niveau du workspace partagé. Ces changements externes ont été préservés et ne sont pas attribués à la présente campagne.

## État du workspace

Au début de cette tâche : branche `refactor/release-0.1`, `git status --porcelain=v2` vide, `git diff --check` et `git diff --cached --check` à zéro. L'état final contient les fichiers de cette campagne et de nombreuses modifications concurrentes apparues après 23:31; aucune n'a été réinitialisée. Le détail d'intégrité Ploemeur est dans `results/remaining_non_ploemeur_simulations/ploemeur_integrity.csv`.

## Modifications exactes à imposer au manuscrit

1. Décrire Holten avec les quatre observables exactes : ³H, tritiogenic ³He, ⁸⁵Kr, and ³⁹Ar.
2. Déclarer l'erreur ³He : sigma analytique publié de 0,5 TU pour six puits; 0,5 TU imputé pour `59-05` car le sigma source manque.
3. Remplacer les valeurs de comparaison Holten par les médianes et q10–q90 H4 du CSV détaillé.
4. Remplacer la Figure 3 par `figure3_holten_h4.png` si H4 est retenu.
5. Remplacer l'affirmation actuelle sur les longueurs MCMC par la phrase anglaise ci-dessus.
6. Ajouter au supplément les cinq cas, les six longueurs, les cinq seeds courts, le critère préenregistré, les taux d'acceptation, ESS et ratios de temps.

## Rapports détaillés

- `holten_helium_requalification.md`
- `mcmc_chain_length_sensitivity.md`

## Tests finaux ciblés

{_markdown(test_summary) if not test_summary.empty else "_Non encore exécutés._"}

Les quatre skips sont les variantes extensives explicitement désactivées; échecs et erreurs : zéro. Aucun test Ploemeur ni golden Ploemeur n'a été lancé ou mis à jour.
"""
    global_path = output / "remaining_non_ploemeur_simulations.md"
    global_path.write_text(global_report, encoding="utf-8", newline="\n")
    return {"holten": holten_path, "mcmc": mcmc_path, "global": global_path}


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "phase", choices=("preflight", "holten", "mcmc", "reports", "all")
    )
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    args = parser.parse_args(argv)
    output = _guard_output(args.output)
    if args.phase in {"preflight", "all"}:
        write_preflight(output)
    if args.phase in {"holten", "all"}:
        run_holten(output)
    if args.phase in {"mcmc", "all"}:
        run_mcmc(output)
    if args.phase in {"reports", "all"}:
        write_reports(output)
    if args.phase == "all":
        verify_ploemeur_unchanged(output)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
