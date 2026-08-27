# Copyright (c) 2021-2026 Centre national de la recherche scientifique (CNRS)
# Contributor: Jean-Raynald de Dreuzy
# SPDX-License-Identifier: CECILL-2.1

"""Build the article audit tables from existing simulation artifacts only.

This script is intentionally post-processing-only: it never imports or calls a
sampler.  It reads the frozen final outputs and writes compact, citable CSVs.
"""

from __future__ import annotations

import json
import re
from pathlib import Path

import numpy as np
import pandas as pd

from pyages.data_io.lpm_distribution import read_distribution

ROOT = Path(__file__).resolve().parents[1]
OUTPUT = ROOT / "results" / "final_scientific_audit_20260821"
PLOEMEUR = ROOT / "results" / "HYP-26-0172" / "v2"
SCENARIO_RE = re.compile(
    r"ploemeur_(?P<conditioning>apriori_double_)?(?P<error>\d+(?:\.\d+)?)"
    r"(?P<mode>span_full|span_with_prior|successive_with_prior|successive)$"
)
CASE_RE = re.compile(r"(?P<well>.+)_(?P<start>\d{4})_(?P<end>\d{4})")


def _relative(path: Path) -> str:
    return path.relative_to(ROOT).as_posix()


def shifted_table() -> pd.DataFrame:
    source = (
        ROOT
        / "results"
        / "final_article_simulations"
        / "shifted_exponential"
        / "table3_final.csv"
    )
    frame = pd.read_csv(source)
    columns = ["case", "target_mu", "target_t0", "target_mtt"]
    for parameter in ("mu", "t0", "mtt"):
        columns.extend(
            f"posterior_{parameter}_{stat}"
            for stat in ("mean", "median", "sd", "q10", "q90", "q025", "q975")
        )
    result = frame.loc[:, columns + ["best_sqrt_J_data_over_m"]].copy()
    result["max_split_rhat"] = frame[
        ["mu_split_rhat", "t0_split_rhat", "mtt_split_rhat"]
    ].max(axis=1)
    result["min_ess"] = frame[["mu_ess", "t0_ess", "mtt_ess"]].min(axis=1)
    result["canonical_source"] = _relative(source)
    return result


def holten_tables() -> tuple[pd.DataFrame, pd.DataFrame]:
    directory = ROOT / "results" / "final_article_simulations" / "holten_h4_final"
    comparison = pd.read_csv(directory / "visser_vs_pyages_h4.csv")
    convergence = pd.read_csv(directory / "convergence_diagnostics.csv")
    summary = pd.read_csv(directory / "posterior_summaries.csv")

    records: list[dict] = []
    for well, group in comparison.groupby("well", sort=False):
        row: dict[str, object] = {
            "well": well,
            "steps_per_chain": int(
                summary.loc[summary["well"].eq(well), "steps_per_chain"].iloc[0]
            ),
            "chains": int(summary.loc[summary["well"].eq(well), "chains"].iloc[0]),
            "max_split_rhat": convergence.loc[
                convergence["well"].eq(well), "split_rhat"
            ].max(),
            "min_ess": convergence.loc[
                convergence["well"].eq(well), "ess_sum_chains"
            ].min(),
            "converged": bool(
                convergence.loc[convergence["well"].eq(well), "converged"].all()
            ),
        }
        for item in group.itertuples(index=False):
            name = str(item.fraction)
            row[f"{name}_visser"] = item.visser
            row[f"{name}_median"] = item.pyages_median
            row[f"{name}_q10"] = item.pyages_q10
            row[f"{name}_q90"] = item.pyages_q90
        records.append(row)
    wells = pd.DataFrame(records)
    residuals = pd.read_csv(directory / "posterior_modeled_concentrations.csv")
    residuals["canonical_source"] = _relative(
        directory / "posterior_modeled_concentrations.csv"
    )
    return wells, residuals


def campaign_inventory() -> pd.DataFrame:
    matrix = pd.read_csv(
        ROOT
        / "sites"
        / "ploemeur"
        / "studies"
        / "HYP-26-0172"
        / "experiment_matrix.csv"
    ).set_index("experiment_id")
    rows: list[dict] = []
    for manifest_path in sorted((PLOEMEUR / "runs").glob("*/manifest.json")):
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        experiment_id = manifest_path.parent.name
        experiment = matrix.loc[experiment_id]
        started = pd.Timestamp(manifest["started_at_utc"])
        finished = pd.Timestamp(manifest["finished_at_utc"])
        rows.append(
            {
                "experiment_id": experiment_id,
                "family": experiment["family"],
                "publication_outputs": experiment["article_outputs"],
                "publication_critical": bool(experiment["enabled"]),
                "git_commit": manifest["git"]["commit"],
                "git_dirty": manifest["git"]["dirty"],
                "snapshot": "C:/codes/pyages-campaign-snapshots/HYP-26-0172-v2-20260820-000740",
                "config": manifest["artifacts"]["resolved_config"].replace("\\", "/"),
                "source_checksums": manifest["artifacts"]["source_checksums"].replace(
                    "\\", "/"
                ),
                "input_checksums": manifest["artifacts"]["input_checksums"].replace(
                    "\\", "/"
                ),
                "seed": experiment["seeds"],
                "chains": 1,
                "mh_nsteps": manifest["mh_nsteps"],
                "burn_in_fraction": 0.2,
                "nskip": 10,
                "status": manifest["status"],
                "runtime_hours": (finished - started).total_seconds() / 3600.0,
                "manifest": _relative(manifest_path),
            }
        )
    return pd.DataFrame(rows)


def _latest_outputs(run_dir: Path) -> list[tuple[Path, re.Match[str]]]:
    outputs: list[tuple[Path, re.Match[str]]] = []
    for scenario in (run_dir / "workflow").iterdir():
        if not scenario.is_dir() or not (match := SCENARIO_RE.fullmatch(scenario.name)):
            continue
        timestamps = [path for path in scenario.iterdir() if path.is_dir()]
        if timestamps:
            outputs.append(
                (max(timestamps, key=lambda path: path.stat().st_mtime), match)
            )
    return outputs


def _case_acceptance(
    diagnostics: pd.DataFrame, experiment: str, case_key: str
) -> float:
    normalized = diagnostics["case"].str.replace("\\", "/", regex=False)
    match = diagnostics.loc[
        diagnostics["experiment_id"].eq(experiment) & normalized.eq(case_key)
    ]
    if len(match) != 1:
        raise RuntimeError(f"Cannot match diagnostics for {experiment}: {case_key}")
    return float(match.iloc[0]["success_rate"])


def publication_cases() -> pd.DataFrame:
    diagnostics = pd.read_csv(PLOEMEUR / "derived" / "mcmc_diagnostics.csv")
    matrix = pd.read_csv(
        ROOT
        / "sites"
        / "ploemeur"
        / "studies"
        / "HYP-26-0172"
        / "experiment_matrix.csv"
    ).set_index("experiment_id")
    selected_experiments = {
        "main_F09_exp_ig_3cfc_err20_seed12345",
        "main_F11_exp_ig_3cfc_err20_seed12345",
        "regime_F38_exp_3cfc_err20_seed12345",
        "regime_MF1_exp_3cfc_err20_seed12345",
        "regime_PE_exp_3cfc_err20_seed12345",
    }
    rows: list[dict] = []
    for experiment in sorted(selected_experiments):
        run_dir = PLOEMEUR / "runs" / experiment
        manifest = json.loads((run_dir / "manifest.json").read_text(encoding="utf-8"))
        for output, scenario_match in _latest_outputs(run_dir):
            mode = scenario_match.group("mode")
            if mode not in {"span_full", "successive", "successive_with_prior"}:
                continue
            cases = sorted(
                output.glob("*_????_????/*/Metropolis_Hastings/lpm_dist_calibrated.txt")
            )
            if mode == "span_full" and cases:
                spans = [
                    int(path.parents[2].name.rsplit("_", 2)[2])
                    - int(path.parents[2].name.rsplit("_", 2)[1])
                    for path in cases
                ]
                longest = max(spans)
                cases = [
                    path
                    for path, span in zip(cases, spans, strict=False)
                    if span == longest
                ]
            for posterior_path in cases:
                model = posterior_path.parents[1].name
                case_name = posterior_path.parents[2].name
                match = CASE_RE.fullmatch(case_name)
                if match is None:
                    continue
                frame = read_distribution(posterior_path)
                case_key = f"{output.parent.name}/{output.name}/{case_name}/{model}"
                row: dict[str, object] = {
                    "experiment_id": experiment,
                    "well": match.group("well"),
                    "mode": mode,
                    "conditioned": mode == "successive_with_prior",
                    "window_start": int(match.group("start")),
                    "window_end": int(match.group("end")),
                    "lpm": model,
                    "publication_critical": True,
                    "publication_outputs": matrix.loc[experiment, "article_outputs"],
                    "seed": int(matrix.loc[experiment, "seeds"]),
                    "chains": 1,
                    "nsteps": int(manifest["mh_nsteps"]),
                    "burn_in_fraction": 0.2,
                    "nskip": 10,
                    "stored_samples": len(frame),
                    "acceptance_rate": _case_acceptance(
                        diagnostics, experiment, case_key
                    ),
                    "below_5pct_acceptance": _case_acceptance(
                        diagnostics, experiment, case_key
                    )
                    < 0.05,
                    "best_sqrt_J_data_over_m": float(frame["obj_function"].min()),
                    "parameter_pairing_in_posterior": "preserved_by_row",
                    "parameter_pairing_in_prediction": (
                        "BROKEN_random_each"
                        if mode == "span_full"
                        else "preserved_random_line"
                    ),
                    "posterior_file": _relative(posterior_path),
                }
                for parameter in ("mu", "sigma", "shift", "mean"):
                    if parameter not in frame:
                        continue
                    values = pd.to_numeric(frame[parameter], errors="coerce")
                    for stat, value in {
                        "mean": values.mean(),
                        "median": values.median(),
                        "sd": values.std(ddof=1),
                        "q10": values.quantile(0.10),
                        "q90": values.quantile(0.90),
                    }.items():
                        prefix = "mtt" if parameter == "mean" else parameter
                        row[f"{prefix}_{stat}"] = float(value)
                rows.append(row)
    result = pd.DataFrame(rows)
    return result.sort_values(["well", "mode", "window_start", "lpm"]).reset_index(
        drop=True
    )


def observation_map(cases: pd.DataFrame) -> pd.DataFrame:
    records: list[dict] = []
    main = cases.loc[cases["experiment_id"].str.startswith("main_")]
    unique = main[
        ["well", "mode", "conditioned", "window_start", "window_end"]
    ].drop_duplicates()
    for item in unique.itertuples(index=False):
        source = (
            ROOT
            / "sites"
            / "ploemeur"
            / "data"
            / "ori"
            / (
                "ori_ploemeur_F09_2005_2024.txt"
                if item.well == "F09"
                else "ori_ploemeur_F11_2004_2024.txt"
            )
        )
        observations = pd.read_csv(source, sep="\t")
        chosen = observations.loc[
            observations["date"].between(
                item.window_start, item.window_end + 1, inclusive="both"
            )
        ]
        for observation in chosen.itertuples(index=False):
            records.append(
                {
                    "well": item.well,
                    "mode": item.mode,
                    "conditioned": item.conditioned,
                    "window_start": item.window_start,
                    "window_end": item.window_end,
                    "element": observation.element,
                    "date_decimal_campaign": observation.date,
                    "concentration": observation.concentration,
                    "input_error_field": observation.error,
                    "effective_sigma_20pct": 0.2 * observation.concentration,
                    "input_unit_field": observation.unit,
                    "physical_unit": "pptv",
                    "source_file": _relative(source),
                }
            )
    return pd.DataFrame(records).sort_values(
        ["well", "mode", "window_start", "date_decimal_campaign", "element"]
    )


def f11_prediction_check(cases: pd.DataFrame) -> pd.DataFrame:
    chosen = cases.loc[
        cases["well"].eq("F11")
        & cases["window_start"].eq(2018)
        & cases["window_end"].eq(2019)
    ]
    observations = pd.read_csv(
        ROOT / "sites" / "ploemeur" / "data" / "ori" / "ori_ploemeur_F11_2004_2024.txt",
        sep="\t",
    )
    observations = observations.loc[
        observations["date"].between(2018, 2020, inclusive="both")
    ]
    records: list[dict] = []
    for case in chosen.itertuples(index=False):
        frame = read_distribution(ROOT / case.posterior_file)
        prediction_columns = [
            column
            for column in frame.columns
            if re.fullmatch(r"cfc(?:11|12|113)_\d+(?:\.\d+)?_\d+", column)
        ]
        for column in prediction_columns:
            tracer, date, observation_index = column.rsplit("_", 2)
            obs = observations.iloc[int(observation_index)]
            if str(obs["element"]) != tracer or not np.isclose(
                float(obs["date"]), float(date)
            ):
                raise RuntimeError(
                    f"Observation header mismatch in {case.posterior_file}: {column}"
                )
            values = pd.to_numeric(frame[column], errors="coerce")
            median = float(values.median())
            records.append(
                {
                    "mode": case.mode,
                    "conditioned": case.conditioned,
                    "lpm": case.lpm,
                    "observation_date": float(date),
                    "tracer": tracer,
                    "observed_pptv": float(obs["concentration"]),
                    "sigma_20pct_pptv": 0.2 * float(obs["concentration"]),
                    "predicted_median_pptv": median,
                    "predicted_q10_pptv": float(values.quantile(0.10)),
                    "predicted_q90_pptv": float(values.quantile(0.90)),
                    "standardized_residual": (median - float(obs["concentration"]))
                    / (0.2 * float(obs["concentration"])),
                    "posterior_file": case.posterior_file,
                }
            )
    return pd.DataFrame(records).sort_values(
        ["mode", "lpm", "observation_date", "tracer"]
    )


def figure_provenance() -> pd.DataFrame:
    shifted = "results/final_article_simulations/shifted_exponential"
    holten = "results/final_article_simulations/holten_h4_final"
    ploemeur = "results/HYP-26-0172/v2"
    rows = [
        {
            "namespace": "article core",
            "figure": "Figure 2 shifted-exponential",
            "artifact": f"{shifted}/figure2_shifted_exponential_final.png|pdf|tiff",
            "builder": "scripts/run_final_shifted_exponential.py",
            "inputs": f"{shifted}/figure2_final_chain_samples.csv;{shifted}/figure2_objective_grid_sqrt_J_data_over_4.csv",
            "run_config": f"{shifted}/manifest.json",
            "status": "canonical final",
        },
        {
            "namespace": "article core",
            "figure": "Figure 3 Holten H4",
            "artifact": f"{holten}/figure3_holten_h4_final.png|pdf",
            "builder": "scripts/run_final_holten_h4.py",
            "inputs": f"{holten}/posterior_summaries.csv;{holten}/visser_vs_pyages_h4.csv",
            "run_config": f"{holten}/manifest.json",
            "status": "canonical final",
        },
    ]
    for figure, table, family in (
        ("Figure 3 Ploemeur", "concentrations_all_models.txt", "main F09/F11"),
        (
            "Figure 4 Ploemeur",
            "derived/figure4_median_transit_times.csv",
            "main F09/F11",
        ),
        ("Figure 5 Ploemeur", "derived/figure5_model_comparison.csv", "main F09/F11"),
        (
            "Figure 6 Ploemeur",
            "derived/figure6_median_transit_times.csv",
            "main+regime",
        ),
        ("Figure A1 Ploemeur", "derived/figureA1_error_sensitivity.csv", "main+error"),
    ):
        artifact_stem = figure.replace(" Ploemeur", "").replace(" ", "")
        rows.append(
            {
                "namespace": "Ploemeur study",
                "figure": figure,
                "artifact": f"{ploemeur}/figures/{artifact_stem}.png|pdf|tif",
                "builder": "sites/ploemeur/studies/HYP-26-0172/postprocessing/build_products.py",
                "inputs": f"{ploemeur}/{table}",
                "run_config": f"sites/ploemeur/studies/HYP-26-0172/experiment_matrix.csv ({family})",
                "status": "generated, scientifically blocked by audit findings",
            }
        )
    rows.append(
        {
            "namespace": "Ploemeur study",
            "figure": "Figure 2 Ploemeur observations",
            "artifact": "not present below results/HYP-26-0172/v2/figures",
            "builder": "sites/ploemeur/studies/HYP-26-0172/postprocessing/build_observation_figures.py",
            "inputs": "sites/ploemeur/data/ori/ori_ploemeur_F09_2005_2024.txt;sites/ploemeur/data/ori/ori_ploemeur_F11_2004_2024.txt",
            "run_config": "sites/ploemeur/studies/HYP-26-0172/figures.yaml",
            "status": "declared but absent from v2 deliverable",
        }
    )
    return pd.DataFrame(rows)


def main() -> None:
    OUTPUT.mkdir(parents=True, exist_ok=True)
    shifted_table().to_csv(
        OUTPUT / "shifted_exponential_19_cases_compact.csv", index=False
    )
    holten_wells, holten_residuals = holten_tables()
    holten_wells.to_csv(OUTPUT / "holten_h4_wells.csv", index=False)
    holten_residuals.to_csv(OUTPUT / "holten_h4_residuals.csv", index=False)
    campaign_inventory().to_csv(OUTPUT / "ploemeur_campaign_inventory.csv", index=False)
    cases = publication_cases()
    cases.to_csv(OUTPUT / "ploemeur_publication_cases.csv", index=False)
    observation_map(cases).to_csv(
        OUTPUT / "ploemeur_calibration_observations.csv", index=False
    )
    f11_prediction_check(cases).to_csv(
        OUTPUT / "ploemeur_f11_2018_2019_predictions.csv", index=False
    )
    figure_provenance().to_csv(OUTPUT / "figure_provenance.csv", index=False)
    print(f"Wrote audit tables to {OUTPUT}")


if __name__ == "__main__":
    main()
