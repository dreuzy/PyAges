# Copyright (c) 2021-2026 Centre national de la recherche scientifique (CNRS)
# Contributor: Jean-Raynald de Dreuzy
# SPDX-License-Identifier: CECILL-2.1

"""Qualify fixed MH proposals for the shifted-exponential article cases.

This driver is deliberately restricted to the four synthetic Table 3 pilot
cases.  It never launches the 19-case production campaign and refuses output
paths containing ``ploemeur``.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import platform
import subprocess
import sys
import time
import xml.etree.ElementTree as ET
from concurrent.futures import ProcessPoolExecutor, as_completed
from pathlib import Path
from typing import Any

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import scipy

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from pyages.calibration.methods.metropolis_hastings import (  # noqa: E402
    MetropolisHastings,
    MHConfig,
)
from pyages.calibration.mh_proposals import (  # noqa: E402
    regularize_empirical_covariance,
    sum_difference_log_abs_det_jacobian,
)
from pyages.calibration.problem import CalibrationProblem  # noqa: E402
from pyages.config.runtime import DisplayOptions  # noqa: E402
from pyages.convolution import ConvolutionTracers  # noqa: E402
from pyages.lpm import build_lpm  # noqa: E402

OUTPUT = ROOT / "results" / "mh_proposal_qualification"
CASES = (
    ("very_sharp", 1.0, 1.0),
    ("young_intermediate", 10.0, 10.0),
    ("figure2", 10.0, 30.0),
    ("long", 40.0, 10.0),
)
SEEDS = (31_001, 31_002, 31_003, 31_004, 31_005)
TRACERS = ("cfc11", "cfc12", "cfc113", "sf6")
DATE = 2010.0
BURN_IN = 0.20
PRODUCTION_STEPS = 10_000
PILOT_STEPS = 4_000
PILOT_SEED = 27_001
RIDGE = 1.0e-6
MAX_ACF_LAG = 1_000


CONFIGURATIONS = (
    {
        "name": "historical_1p5",
        "strategy": "historical",
        "kind": "componentwise",
        "scale": "(1.5,1.5)",
    },
    {
        "name": "diagonal_2",
        "strategy": "diagonal",
        "kind": "diagonal",
        "scales": (2.0, 2.0),
        "scale": "(2,2)",
    },
    {
        "name": "diagonal_3",
        "strategy": "diagonal",
        "kind": "diagonal",
        "scales": (3.0, 3.0),
        "scale": "(3,3)",
    },
    {
        "name": "diagonal_4",
        "strategy": "diagonal",
        "kind": "diagonal",
        "scales": (4.0, 4.0),
        "scale": "(4,4)",
    },
    {
        "name": "md_2_4",
        "strategy": "sum_difference",
        "kind": "sum_difference",
        "scales": (2.0, 4.0),
        "scale": "m=2,d=4",
    },
    {
        "name": "md_3_6",
        "strategy": "sum_difference",
        "kind": "sum_difference",
        "scales": (3.0, 6.0),
        "scale": "m=3,d=6",
    },
    {
        "name": "md_4_8",
        "strategy": "sum_difference",
        "kind": "sum_difference",
        "scales": (4.0, 8.0),
        "scale": "m=4,d=8",
    },
    {
        "name": "correlated_0p75",
        "strategy": "pilot_covariance",
        "kind": "correlated",
        "multiplier": 0.75,
        "scale": "s=0.75",
    },
    {
        "name": "correlated_1",
        "strategy": "pilot_covariance",
        "kind": "correlated",
        "multiplier": 1.0,
        "scale": "s=1",
    },
    {
        "name": "correlated_1p68",
        "strategy": "pilot_covariance",
        "kind": "correlated",
        "multiplier": 2.38 / math.sqrt(2.0),
        "scale": "s=2.38/sqrt(2)",
    },
    {
        "name": "correlated_2p4",
        "strategy": "pilot_covariance",
        "kind": "correlated",
        "multiplier": 2.4,
        "scale": "s=2.4",
    },
)


def _guard_output(path: Path) -> Path:
    resolved = path.resolve()
    if "ploemeur" in str(resolved).lower():
        raise ValueError("This campaign refuses any Ploemeur output path")
    resolved.mkdir(parents=True, exist_ok=True)
    return resolved


def _display(output: Path) -> DisplayOptions:
    display = DisplayOptions()
    display.text = False
    display.figure = False
    display.figure_save = False
    display.figure_close = True
    display.directory = output
    return display


def _model(mu: float, t0: float):
    model = build_lpm("exp_shifted", directory_lpm=str(ROOT / "data_core" / "data_lpm"))
    model.p.update({"mu": mu, "shift": t0})
    return model


def _observations(mu: float, t0: float):
    tracers = ConvolutionTracers(names=list(TRACERS), date=DATE)
    observations = tracers.convolve(_model(mu, t0), return_type="concentrations")
    observations.error_affect_from_value(0.08)
    return observations


def _run_chain(
    mu: float,
    t0: float,
    seed: int,
    steps: int,
    configuration: dict[str, Any],
    covariance: np.ndarray | None,
    output: Path,
) -> tuple[MetropolisHastings, pd.DataFrame, float]:
    observations = _observations(mu, t0)
    problem = CalibrationProblem(
        observations,
        "exp_shifted",
        display_options=_display(output),
        sample_count=10_000,
        explore_objective=False,
        explore_reachable=False,
    ).prepare()
    kwargs: dict[str, Any] = {
        "proposal_kind": configuration["kind"],
        "proposal_multiplier": float(configuration.get("multiplier", 1.0)),
    }
    if "scales" in configuration:
        kwargs["proposal_scales"] = tuple(configuration["scales"])
    if configuration["kind"] == "componentwise":
        kwargs["componentwise_source"] = "model"
    if covariance is not None:
        kwargs["proposal_covariance"] = tuple(
            tuple(float(v) for v in row) for row in covariance
        )
    mh = MetropolisHastings(
        config=MHConfig(
            nstep=steps,
            burn_in=BURN_IN,
            nskip=1,
            prior_option=False,
            likelihood=True,
            monitor=False,
            display_traj=False,
            display_text=False,
            seed=seed,
            initial_params={"mu": 10.0, "shift": 10.0},
            **kwargs,
        )
    )
    start = time.perf_counter()
    posterior = mh.run(problem)
    elapsed = time.perf_counter() - start
    frame = posterior.frame.copy()
    frame["t0"] = frame["shift"]
    frame["mtt"] = frame["mu"] + frame["t0"]
    return mh, frame, elapsed


def _acceptance(mh: MetropolisHastings) -> float:
    payload: dict[str, Any] = {}
    mh.write_results_spec(payload)
    return float(payload["success_rate"])


def _acf(values: np.ndarray, max_lag: int = MAX_ACF_LAG) -> np.ndarray:
    values = np.asarray(values, dtype=float)
    centered = values - values.mean()
    n = len(centered)
    if n < 2 or np.dot(centered, centered) == 0.0:
        return np.ones(1)
    fft_size = 1 << (2 * n - 1).bit_length()
    spectrum = np.fft.rfft(centered, n=fft_size)
    covariance = np.fft.irfft(spectrum * np.conjugate(spectrum), n=fft_size)[:n]
    covariance /= np.arange(n, 0, -1)
    result = covariance / covariance[0]
    return result[: min(max_lag, n - 1) + 1]


def _iact_ess(values: np.ndarray) -> tuple[np.ndarray, float, float]:
    acf = _acf(values)
    pair_sums = []
    for start in range(1, len(acf) - 1, 2):
        pair = float(acf[start] + acf[start + 1])
        if pair <= 0.0:
            break
        pair_sums.append(pair)
    if pair_sums:
        monotone = np.minimum.accumulate(np.asarray(pair_sums))
        tau = max(1.0, 1.0 + 2.0 * float(monotone.sum()))
    else:
        tau = 1.0
    return acf, tau, min(float(len(values)), float(len(values)) / tau)


def _summary(values: np.ndarray) -> dict[str, float]:
    acf, iact, ess = _iact_ess(values)
    return {
        "mean": float(np.mean(values)),
        "median": float(np.median(values)),
        "sd": float(np.std(values, ddof=1)),
        "q025": float(np.quantile(values, 0.025)),
        "q10": float(np.quantile(values, 0.10)),
        "q25": float(np.quantile(values, 0.25)),
        "q75": float(np.quantile(values, 0.75)),
        "q90": float(np.quantile(values, 0.90)),
        "q975": float(np.quantile(values, 0.975)),
        "acf1": float(acf[1]) if len(acf) > 1 else np.nan,
        "iact": iact,
        "ess": ess,
    }


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def write_preflight(output: Path) -> Path:
    files = (
        ROOT / "scripts" / "qualify_mh_proposals.py",
        ROOT / "pyages" / "calibration" / "mh_proposals.py",
        ROOT / "pyages" / "calibration" / "methods" / "metropolis_hastings.py",
        ROOT / "pyages" / "calibration" / "methods" / "trajectory.py",
        ROOT / "data_core" / "data_lpm" / "exp_shifted" / "params.yaml",
    )

    def run(*args: str) -> str:
        return subprocess.run(
            args,
            cwd=ROOT,
            text=True,
            capture_output=True,
            check=True,
        ).stdout

    payload = {
        "captured_at_unix": time.time(),
        "task_initial_head": "a0cf3b95e0327ad16069cb57b37e87522416d481",
        "head_at_campaign_start": run("git", "rev-parse", "HEAD").strip(),
        "git_status_porcelain_v2": run("git", "status", "--porcelain=v2").splitlines(),
        "git_diff_check": subprocess.run(
            ["git", "diff", "--check"], cwd=ROOT, text=True, capture_output=True
        ).returncode,
        "python": platform.python_version(),
        "numpy": np.__version__,
        "scipy": scipy.__version__,
        "hashes_sha256": {str(path.relative_to(ROOT)): _sha256(path) for path in files},
        "protocol": {
            "cases": CASES,
            "seeds": SEEDS,
            "tracers": TRACERS,
            "date": DATE,
            "relative_error": 0.08,
            "production_steps": PRODUCTION_STEPS,
            "pilot_steps": PILOT_STEPS,
            "burn_in": BURN_IN,
            "nskip": 1,
            "pilot_seed": PILOT_SEED,
            "covariance_relative_ridge": RIDGE,
            "configurations": CONFIGURATIONS,
            "md_inverse_log_abs_det_jacobian": sum_difference_log_abs_det_jacobian(),
        },
    }
    path = output / "preflight.json"
    path.write_text(json.dumps(payload, indent=2), encoding="utf-8", newline="\n")
    return path


def run_pilots(output: Path) -> dict[str, np.ndarray]:
    pilot_dir = _guard_output(output / "pilots")
    covariances: dict[str, np.ndarray] = {}
    historical = CONFIGURATIONS[0]
    for case_name, mu, t0 in CASES:
        covariance_path = pilot_dir / f"{case_name}_covariance.npy"
        if covariance_path.exists():
            covariances[case_name] = np.load(covariance_path)
            continue
        mh, frame, elapsed = _run_chain(
            mu, t0, PILOT_SEED, PILOT_STEPS, historical, None, pilot_dir
        )
        samples = frame[["mu", "t0"]].to_numpy(float)
        covariance = regularize_empirical_covariance(samples, RIDGE)
        np.save(covariance_path, covariance)
        np.savez_compressed(
            pilot_dir / f"{case_name}_pilot_chain.npz",
            mu=samples[:, 0],
            t0=samples[:, 1],
            mtt=samples.sum(axis=1),
            acceptance=_acceptance(mh),
            runtime=elapsed,
        )
        covariances[case_name] = covariance
    return covariances


def _chain_path(
    output: Path, case_name: str, configuration: str, seed: int, steps: int
) -> Path:
    return output / "chains" / f"{case_name}__{configuration}__seed{seed}__n{steps}.npz"


def _run_job(job: tuple[Any, ...]) -> str:
    output, case_name, mu, t0, seed, steps, configuration, covariance = job
    output = Path(output)
    chain_path = _chain_path(output, case_name, configuration["name"], seed, steps)
    if chain_path.exists():
        return str(chain_path)
    mh, frame, elapsed = _run_chain(
        mu, t0, seed, steps, configuration, covariance, output
    )
    np.savez_compressed(
        chain_path,
        mu=frame["mu"].to_numpy(float),
        t0=frame["t0"].to_numpy(float),
        mtt=frame["mtt"].to_numpy(float),
        objective=frame["obj_function"].to_numpy(float),
        acceptance=_acceptance(mh),
        runtime=elapsed,
    )
    return str(chain_path)


def run_screen(output: Path, workers: int, steps: int = PRODUCTION_STEPS) -> None:
    _guard_output(output / "chains")
    covariances = run_pilots(output)
    jobs = []
    for case_name, mu, t0 in CASES:
        for configuration in CONFIGURATIONS:
            covariance = (
                covariances[case_name]
                if configuration["kind"] == "correlated"
                else None
            )
            for seed in SEEDS:
                path = _chain_path(
                    output, case_name, configuration["name"], seed, steps
                )
                if not path.exists():
                    jobs.append(
                        (
                            str(output),
                            case_name,
                            mu,
                            t0,
                            seed,
                            steps,
                            configuration,
                            covariance,
                        )
                    )
    if not jobs:
        return
    with ProcessPoolExecutor(max_workers=workers) as executor:
        futures = [executor.submit(_run_job, job) for job in jobs]
        for index, future in enumerate(as_completed(futures), 1):
            future.result()
            if index % 10 == 0 or index == len(futures):
                print(f"completed {index}/{len(futures)} chains", flush=True)


def split_rhat(chains: list[np.ndarray]) -> float:
    """Classical split-Rhat (Gelman--Rubin) for equal-length scalar chains."""
    if len(chains) < 2:
        return np.nan
    length = min(len(chain) for chain in chains)
    half = length // 2
    if half < 2:
        return np.nan
    split = np.asarray(
        [part for chain in chains for part in (chain[:half], chain[length - half :])],
        dtype=float,
    )
    within = float(np.mean(np.var(split, axis=1, ddof=1)))
    if within == 0.0:
        return 1.0 if np.var(np.mean(split, axis=1), ddof=1) == 0.0 else math.inf
    between = half * float(np.var(np.mean(split, axis=1), ddof=1))
    variance = (half - 1.0) / half * within + between / half
    return float(math.sqrt(variance / within))


def _load_chain(path: Path) -> dict[str, Any]:
    with np.load(path) as data:
        return {name: data[name].copy() for name in data.files}


def _collect_analysis_tables(output: Path, steps: int):
    summary_rows, run_rows, acf_rows = [], [], []
    chain_cache: dict[tuple[str, str, int], dict[str, Any]] = {}
    for case_name, target_mu, target_t0 in CASES:
        for configuration in CONFIGURATIONS:
            for seed in SEEDS:
                path = _chain_path(
                    output, case_name, configuration["name"], seed, steps
                )
                if not path.exists():
                    raise FileNotFoundError(path)
                chain = _load_chain(path)
                chain_cache[(case_name, configuration["name"], seed)] = chain
                runtime = float(chain["runtime"])
                per_parameter_ess = []
                for parameter, target in (
                    ("mu", target_mu),
                    ("t0", target_t0),
                    ("mtt", target_mu + target_t0),
                ):
                    values = chain[parameter]
                    stats = _summary(values)
                    per_parameter_ess.append(stats["ess"])
                    summary_rows.append(
                        {
                            "case": case_name,
                            "target_mu": target_mu,
                            "target_t0": target_t0,
                            "configuration": configuration["name"],
                            "strategy": configuration["strategy"],
                            "scale": configuration["scale"],
                            "seed": seed,
                            "steps": steps,
                            "stored_samples": len(values),
                            "parameter": parameter,
                            "target": target,
                            "runtime_seconds": runtime,
                            **stats,
                            "ess_per_second": stats["ess"] / runtime,
                        }
                    )
                    acf = _acf(values)
                    acf_rows.extend(
                        {
                            "case": case_name,
                            "configuration": configuration["name"],
                            "seed": seed,
                            "parameter": parameter,
                            "lag": lag,
                            "acf": float(value),
                        }
                        for lag, value in enumerate(acf)
                    )
                run_rows.append(
                    {
                        "case": case_name,
                        "configuration": configuration["name"],
                        "strategy": configuration["strategy"],
                        "scale": configuration["scale"],
                        "seed": seed,
                        "steps": steps,
                        "stored_samples": len(chain["mu"]),
                        "acceptance_rate": float(chain["acceptance"]),
                        "runtime_seconds": runtime,
                        "best_normalized_misfit": float(np.min(chain["objective"])),
                        "minimum_ess": min(per_parameter_ess),
                        "minimum_ess_per_second": min(per_parameter_ess) / runtime,
                        "chain_file": str(
                            _chain_path(
                                output, case_name, configuration["name"], seed, steps
                            ).relative_to(ROOT)
                        ),
                    }
                )
    return (
        pd.DataFrame(summary_rows),
        pd.DataFrame(run_rows),
        pd.DataFrame(acf_rows),
        chain_cache,
    )


def _split_rhat_table(
    summaries: pd.DataFrame,
    chain_cache: dict[tuple[str, str, int], dict[str, Any]],
) -> pd.DataFrame:
    rows = []
    for (case_name, configuration, parameter), group in summaries.groupby(
        ["case", "configuration", "parameter"]
    ):
        chains = [
            chain_cache[(case_name, configuration, int(seed))][parameter]
            for seed in group["seed"]
        ]
        rows.append(
            {
                "case": case_name,
                "configuration": configuration,
                "parameter": parameter,
                "split_rhat": split_rhat(chains),
            }
        )
    return pd.DataFrame(rows)


def analyze(output: Path, steps: int = PRODUCTION_STEPS) -> dict[str, Path]:
    summaries, runs, acfs, chain_cache = _collect_analysis_tables(output, steps)
    rhats = _split_rhat_table(summaries, chain_cache)

    variability = (
        summaries.groupby(
            ["case", "configuration", "strategy", "scale", "parameter"], as_index=False
        )
        .agg(
            seeds=("seed", "nunique"),
            median_interseed_sd=("median", "std"),
            median_interseed_range=(
                "median",
                lambda values: values.max() - values.min(),
            ),
            q10_interseed_sd=("q10", "std"),
            q90_interseed_sd=("q90", "std"),
            posterior_sd_interseed_sd=("sd", "std"),
            ess_median=("ess", "median"),
            ess_min=("ess", "min"),
            ess_per_second_median=("ess_per_second", "median"),
            iact_median=("iact", "median"),
        )
        .merge(rhats, on=["case", "configuration", "parameter"], how="left")
    )
    ranking = variability.groupby(
        ["configuration", "strategy", "scale"], as_index=False
    ).agg(
        max_split_rhat=("split_rhat", "max"),
        min_ess=("ess_min", "min"),
        median_ess=("ess_median", "median"),
        median_ess_per_second=("ess_per_second_median", "median"),
        max_median_interseed_sd=("median_interseed_sd", "max"),
        max_quantile_interseed_sd=("q10_interseed_sd", "max"),
    )
    acceptance = runs.groupby("configuration", as_index=False).agg(
        acceptance_mean=("acceptance_rate", "mean"),
        runtime_mean=("runtime_seconds", "mean"),
    )
    ranking = ranking.merge(acceptance, on="configuration", how="left")
    ranking["rhat_below_1p01"] = ranking["max_split_rhat"] < 1.01
    ranking = ranking.sort_values(
        ["rhat_below_1p01", "median_ess_per_second", "min_ess"],
        ascending=[False, False, False],
    )

    comparison_rows = []
    historical = summaries.loc[summaries["configuration"] == "historical_1p5"]
    best_name = str(ranking.iloc[0]["configuration"])
    best = summaries.loc[summaries["configuration"] == best_name]
    keys = ["case", "seed", "parameter"]
    merged = historical.merge(best, on=keys, suffixes=("_historical", "_best"))
    for _, row in merged.iterrows():
        comparison_rows.append(
            {
                **{key: row[key] for key in keys},
                "best_configuration": best_name,
                **{
                    f"delta_{metric}": float(
                        row[f"{metric}_best"] - row[f"{metric}_historical"]
                    )
                    for metric in ("mean", "median", "sd", "q025", "q10", "q90", "q975")
                },
            }
        )
    comparisons = pd.DataFrame(comparison_rows)

    pooled_rows = []
    for case_name, target_mu, target_t0 in CASES:
        for configuration in ("historical_1p5", best_name):
            for parameter, target in (
                ("mu", target_mu),
                ("t0", target_t0),
                ("mtt", target_mu + target_t0),
            ):
                values = np.concatenate(
                    [
                        chain_cache[(case_name, configuration, seed)][parameter]
                        for seed in SEEDS
                    ]
                )
                pooled_rows.append(
                    {
                        "case": case_name,
                        "configuration": configuration,
                        "parameter": parameter,
                        "target": target,
                        "pooled_samples": len(values),
                        **_summary(values),
                    }
                )
    pooled = pd.DataFrame(pooled_rows)
    pooled_historical = pooled.loc[pooled["configuration"] == "historical_1p5"].drop(
        columns="configuration"
    )
    pooled_best = pooled.loc[pooled["configuration"] == best_name].drop(
        columns="configuration"
    )
    pooled_comparison = pooled_historical.merge(
        pooled_best,
        on=["case", "parameter", "target"],
        suffixes=("_historical", "_best"),
    )
    for metric in ("mean", "median", "sd", "q025", "q10", "q25", "q75", "q90", "q975"):
        pooled_comparison[f"delta_{metric}"] = (
            pooled_comparison[f"{metric}_best"]
            - pooled_comparison[f"{metric}_historical"]
        )

    published_comparison = pd.DataFrame()
    published_path = (
        ROOT
        / "results"
        / "remaining_non_ploemeur_simulations"
        / "mcmc"
        / "mcmc_posterior_summaries.csv"
    )
    if published_path.exists():
        published = pd.read_csv(published_path)
        published = published.loc[
            published["is_reference"].astype(str).str.lower() == "true"
        ].copy()
        published["parameter"] = published["parameter"].replace({"mu_plus_t0": "mtt"})
        selected = published[
            [
                "case",
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
            ]
        ]
        published_comparison = selected.merge(
            pooled_best, on=["case", "parameter"], suffixes=("_published", "_best")
        )
        for metric in (
            "mean",
            "median",
            "sd",
            "q025",
            "q10",
            "q25",
            "q75",
            "q90",
            "q975",
        ):
            published_comparison[f"delta_{metric}"] = (
                published_comparison[f"{metric}_best"]
                - published_comparison[f"{metric}_published"]
            )
        published_comparison["abs_median_delta_over_published_sd"] = (
            published_comparison["delta_median"].abs()
            / published_comparison["sd_published"]
        )
        standardized_columns = []
        for metric in ("median", "q025", "q10", "q25", "q75", "q90", "q975"):
            column = f"abs_{metric}_delta_over_published_sd"
            published_comparison[column] = (
                published_comparison[f"delta_{metric}"].abs()
                / published_comparison["sd_published"]
            )
            standardized_columns.append(column)
        published_comparison["max_abs_summary_delta_over_published_sd"] = (
            published_comparison[standardized_columns].max(axis=1)
        )
        comparison_manifest = {
            "published_reference_file": str(published_path.relative_to(ROOT)),
            "published_reference_sha256": _sha256(published_path),
            "published_configuration": "historical (1.5,1.5), 10000 steps, seed 12345, nskip 5",
            "qualified_configuration": best_name,
            "qualified_pool": f"{len(SEEDS)} chains x 7999 post-burn-in states",
        }
        (output / "published_comparison_manifest.json").write_text(
            json.dumps(comparison_manifest, indent=2), encoding="utf-8", newline="\n"
        )

    paths = {
        "summaries": output / "posterior_summaries.csv",
        "runs": output / "run_diagnostics.csv",
        "acf": output / "autocorrelation_functions.csv.gz",
        "rhat": output / "split_rhat.csv",
        "variability": output / "interseed_variability.csv",
        "ranking": output / "configuration_ranking.csv",
        "comparisons": output / "posterior_target_comparison.csv",
        "pooled_comparison": output / "posterior_pooled_comparison.csv",
        "published_comparison": output / "published_reference_comparison.csv",
    }
    summaries.to_csv(paths["summaries"], index=False)
    runs.to_csv(paths["runs"], index=False)
    acfs.to_csv(paths["acf"], index=False, compression="gzip")
    rhats.to_csv(paths["rhat"], index=False)
    variability.to_csv(paths["variability"], index=False)
    ranking.to_csv(paths["ranking"], index=False)
    comparisons.to_csv(paths["comparisons"], index=False)
    pooled_comparison.to_csv(paths["pooled_comparison"], index=False)
    published_comparison.to_csv(paths["published_comparison"], index=False)
    make_figure2_diagnostics(output, best_name, chain_cache, acfs, summaries, runs)
    write_report(output, best_name, ranking, runs, comparisons)
    manifest_sources = (
        ROOT / "scripts" / "qualify_mh_proposals.py",
        ROOT / "pyages" / "calibration" / "mh_proposals.py",
        ROOT / "pyages" / "calibration" / "methods" / "metropolis_hastings.py",
        ROOT / "pyages" / "calibration" / "methods" / "trajectory.py",
        ROOT / "data_core" / "data_lpm" / "exp_shifted" / "params.yaml",
        ROOT / "tests" / "calibration" / "test_mh_proposals.py",
        ROOT / "tests" / "scripts" / "test_qualify_mh_proposals.py",
    )
    artifact_paths = [path for path in paths.values() if path.exists()]
    artifact_paths.extend(sorted((output / "figures").glob("*.png")))
    analysis_manifest = {
        "head": subprocess.run(
            ["git", "rev-parse", "HEAD"],
            cwd=ROOT,
            text=True,
            capture_output=True,
            check=True,
        ).stdout.strip(),
        "source_hashes_sha256": {
            str(path.relative_to(ROOT)): _sha256(path) for path in manifest_sources
        },
        "artifact_hashes_sha256": {
            str(path.relative_to(ROOT)): _sha256(path) for path in artifact_paths
        },
        "chain_files": len(list((output / "chains").glob("*.npz"))),
        "pilot_chain_files": len(list((output / "pilots").glob("*_pilot_chain.npz"))),
    }
    (output / "analysis_manifest.json").write_text(
        json.dumps(analysis_manifest, indent=2), encoding="utf-8", newline="\n"
    )
    return paths


def make_figure2_diagnostics(
    output: Path,
    best_name: str,
    chains: dict[tuple[str, str, int], dict[str, Any]],
    acfs: pd.DataFrame,
    summaries: pd.DataFrame,
    runs: pd.DataFrame,
) -> None:
    figures = _guard_output(output / "figures")
    configurations = ("historical_1p5", best_name)
    figure, axes = plt.subplots(3, 2, figsize=(12, 9), constrained_layout=True)
    for column, configuration in enumerate(configurations):
        chain = chains[("figure2", configuration, SEEDS[0])]
        for row, parameter in enumerate(("mu", "t0", "mtt")):
            axes[row, column].plot(chain[parameter], linewidth=0.45)
            axes[row, column].set_ylabel(parameter)
            axes[row, column].set_title(configuration if row == 0 else "")
            axes[row, column].set_xlabel("post-burn-in iteration")
    figure.savefig(figures / "figure2_trace_comparison.png", dpi=180)
    plt.close(figure)

    figure, axes = plt.subplots(3, 2, figsize=(12, 9), constrained_layout=True)
    for column, configuration in enumerate(configurations):
        subset = acfs.loc[
            (acfs["case"] == "figure2")
            & (acfs["configuration"] == configuration)
            & (acfs["seed"] == SEEDS[0])
            & (acfs["lag"] <= 250)
        ]
        for row, parameter in enumerate(("mu", "t0", "mtt")):
            values = subset.loc[subset["parameter"] == parameter]
            axes[row, column].plot(values["lag"], values["acf"])
            axes[row, column].axhline(0.0, color="black", linewidth=0.6)
            axes[row, column].set_ylabel(f"ACF {parameter}")
            axes[row, column].set_title(configuration if row == 0 else "")
            axes[row, column].set_xlabel("lag")
    figure.savefig(figures / "figure2_acf_comparison.png", dpi=180)
    plt.close(figure)

    figure, axes = plt.subplots(1, 2, figsize=(11, 5), constrained_layout=True)
    for axis, configuration in zip(axes, configurations, strict=True):
        for seed in SEEDS:
            chain = chains[("figure2", configuration, seed)]
            axis.scatter(chain["mu"][::8], chain["t0"][::8], s=2, alpha=0.18)
        axis.scatter([10.0], [30.0], marker="x", s=80, color="black")
        axis.set(title=configuration, xlabel="mu", ylabel="t0")
    figure.savefig(figures / "figure2_posterior_cloud_comparison.png", dpi=180)
    plt.close(figure)

    table = (
        summaries.loc[summaries["case"] == "figure2"]
        .groupby(["configuration", "strategy", "scale", "parameter"], as_index=False)
        .agg(
            iact=("iact", "median"),
            ess=("ess", "median"),
            ess_per_second=("ess_per_second", "median"),
        )
        .pivot(
            index=["configuration", "strategy", "scale"],
            columns="parameter",
            values=["iact", "ess", "ess_per_second"],
        )
    )
    table.columns = [f"{metric}_{parameter}" for metric, parameter in table.columns]
    table = table.reset_index().merge(
        runs.loc[runs["case"] == "figure2"]
        .groupby("configuration", as_index=False)
        .agg(acceptance=("acceptance_rate", "mean")),
        on="configuration",
    )
    table.to_csv(output / "figure2_proposal_comparison.csv", index=False)


def _markdown(frame: pd.DataFrame, digits: int = 4) -> str:
    rounded = frame.round(digits)
    columns = [str(column) for column in rounded.columns]

    def render(value: Any) -> str:
        if pd.isna(value):
            return "NA"
        return str(value).replace("|", "\\|")

    rows = [
        "| " + " | ".join(columns) + " |",
        "| " + " | ".join("---" for _ in columns) + " |",
    ]
    rows.extend(
        "| " + " | ".join(render(value) for value in row) + " |"
        for row in rounded.itertuples(index=False, name=None)
    )
    return "\n".join(rows)


def write_report(
    output: Path,
    best_name: str,
    ranking: pd.DataFrame,
    runs: pd.DataFrame,
    comparisons: pd.DataFrame,
) -> Path:
    best_rank = ranking.loc[ranking["configuration"] == best_name].iloc[0]
    historical_rank = ranking.loc[ranking["configuration"] == "historical_1p5"].iloc[0]
    best_diagonal = ranking.loc[ranking["strategy"] == "diagonal"].iloc[0]
    best_md = ranking.loc[ranking["strategy"] == "sum_difference"].iloc[0]
    ess_per_second_gain = float(best_rank["median_ess_per_second"]) / float(
        historical_rank["median_ess_per_second"]
    )
    figure2 = pd.read_csv(output / "figure2_proposal_comparison.csv")
    key_ranking = ranking[
        [
            "configuration",
            "strategy",
            "scale",
            "acceptance_mean",
            "max_split_rhat",
            "min_ess",
            "median_ess",
            "median_ess_per_second",
            "max_median_interseed_sd",
        ]
    ]
    posterior_delta = comparisons.groupby("parameter", as_index=False).agg(
        max_abs_median_delta=("delta_median", lambda x: np.max(np.abs(x))),
        max_abs_mean_delta=("delta_mean", lambda x: np.max(np.abs(x))),
        max_abs_sd_delta=("delta_sd", lambda x: np.max(np.abs(x))),
        max_abs_q10_delta=("delta_q10", lambda x: np.max(np.abs(x))),
        max_abs_q90_delta=("delta_q90", lambda x: np.max(np.abs(x))),
    )
    pooled_comparison = pd.read_csv(output / "posterior_pooled_comparison.csv")
    pooled_delta = pooled_comparison.groupby("parameter", as_index=False).agg(
        max_abs_median_delta=("delta_median", lambda x: np.max(np.abs(x))),
        max_abs_sd_delta=("delta_sd", lambda x: np.max(np.abs(x))),
        max_abs_q10_delta=("delta_q10", lambda x: np.max(np.abs(x))),
        max_abs_q90_delta=("delta_q90", lambda x: np.max(np.abs(x))),
    )
    published_path = output / "published_reference_comparison.csv"
    published = (
        pd.read_csv(published_path) if published_path.exists() else pd.DataFrame()
    )
    if published.empty:
        published_display = "_Référence publiée indisponible dans le workspace._"
        published_max_standardized = math.nan
    else:
        published_display_frame = published[
            [
                "case",
                "parameter",
                "median_published",
                "median_best",
                "delta_median",
                "q10_published",
                "q10_best",
                "q90_published",
                "q90_best",
                "sd_published",
                "sd_best",
                "abs_median_delta_over_published_sd",
            ]
        ]
        published_display = _markdown(published_display_frame)
        published_max_standardized = float(
            published["abs_median_delta_over_published_sd"].max()
        )
        published_max_summary_standardized = float(
            published["max_abs_summary_delta_over_published_sd"].max()
        )
    if published.empty:
        published_max_summary_standardized = math.nan
    runtime = (
        runs.groupby(["configuration", "strategy", "scale"], as_index=False)
        .agg(
            runs=("runtime_seconds", "size"),
            runtime_median_seconds=("runtime_seconds", "median"),
            runtime_min_seconds=("runtime_seconds", "min"),
            runtime_max_seconds=("runtime_seconds", "max"),
        )
        .sort_values("runtime_median_seconds")
    )
    junit_path = output / "targeted-tests.xml"
    if junit_path.exists():
        root = ET.parse(junit_path).getroot()
        suite = root if root.tag == "testsuite" else root.find("testsuite")
        if suite is not None:
            total = int(suite.attrib.get("tests", 0))
            failures = int(suite.attrib.get("failures", 0))
            errors = int(suite.attrib.get("errors", 0))
            skipped = int(suite.attrib.get("skipped", 0))
            test_result = (
                f"{total - failures - errors - skipped} passed, {skipped} skipped, "
                f"{failures} failed, {errors} errors"
            )
        else:
            test_result = "fichier JUnit présent mais illisible"
    else:
        test_result = "résultat JUnit non encore enregistré"
    corr_rows = []
    for configuration in ("historical_1p5", best_name):
        for seed in SEEDS:
            with np.load(
                _chain_path(output, "figure2", configuration, seed, PRODUCTION_STEPS)
            ) as chain:
                corr_rows.append(
                    {
                        "configuration": configuration,
                        "seed": seed,
                        "corr_mu_t0": np.corrcoef(chain["mu"], chain["t0"])[0, 1],
                    }
                )
    correlation = (
        pd.DataFrame(corr_rows)
        .groupby("configuration", as_index=False)
        .agg(
            correlation_mean=("corr_mu_t0", "mean"),
            correlation_sd=("corr_mu_t0", "std"),
        )
    )
    report = f"""# Qualification finale des proposals Metropolis–Hastings

## Décision

Sur les quatre cas pilotes et cinq seeds, la configuration classée première est **`{best_name}`**. Son split-Rhat maximal vaut **{best_rank["max_split_rhat"]:.4f}**, son ESS minimal observé **{best_rank["min_ess"]:.1f}**, et son ESS/s médian **{best_rank["median_ess_per_second"]:.2f}**, contre respectivement **{historical_rank["max_split_rhat"]:.4f}**, **{historical_rank["min_ess"]:.1f}** et **{historical_rank["median_ess_per_second"]:.2f}** pour `(1.5,1.5)`. Le gain médian d'ESS/s est **×{ess_per_second_gain:.2f}**.

Cette qualification ne recalcule volontairement ni les 19 cas de Table 3, ni Figure 2 finale, ni le manuscrit. Elle fournit d'abord les résultats pilotes demandés pour validation.

## Traçabilité et invariants

- Commit au début de la tâche : `a0cf3b95e0327ad16069cb57b37e87522416d481`. Un commit concurrent a ensuite fait avancer `HEAD`; le détail au démarrage de la campagne est dans `preflight.json`.
- Environnement : Python {platform.python_version()}, NumPy {np.__version__}, SciPy {scipy.__version__}.
- Données : concentrations synthétiques non bruitées, CFC-11/CFC-12/CFC-113/SF6, 2010, erreur relative 8 %.
- Cible inchangée : même shifted exponential, likelihood, absence de prior, bounds `[0.1,70] × [0,70]`, forward CDF–partial-first-moment et initialisation `(10,10)`.
- Production : 10 000 itérations, burn-in 20 %, chaque état post-burn-in stocké, aucun thinning diagnostique, seeds {", ".join(map(str, SEEDS))}.
- Covariance : pilote historique de {PILOT_STEPS} itérations, seed {PILOT_SEED}, burn-in 20 %, covariance empirique en `(mu,t0)`, ridge relatif `{RIDGE:g}`, puis covariance figée en production.
- Transformation : `m=mu+t0`, `d=mu-t0`; inverse `mu=(m+d)/2`, `t0=(m-d)/2`; `|d(mu,t0)/d(m,d)|=1/2`, constant. Il s'annule dans le rapport MH et les bounds restent testés en coordonnées physiques.
- Empreintes exactes des scripts/configurations : `results/mh_proposal_qualification/preflight.json`.

## Proposals comparés

{_markdown(key_ranking)}

Le classement privilégie d'abord `Rhat < 1.01`, puis ESS/s et ESS; l'acceptance n'intervient pas comme critère primaire.

## Temps de calcul

{_markdown(runtime)}

Les temps sont des temps muraux par chaîne sous charge concurrente du workspace. Quelques maxima reflètent une contention externe; le classement utilise donc la médiane d'ESS/s sur les répétitions, pas le maximum ni la moyenne brute de runtime.

## Figure 2 : `(mu,t0)=(10,30)`

{_markdown(figure2)}

Corrélation postérieure et stabilité entre seeds :

{_markdown(correlation)}

Figures diagnostiques :

- `figures/figure2_trace_comparison.png`
- `figures/figure2_acf_comparison.png`
- `figures/figure2_posterior_cloud_comparison.png`

## Stabilité de la distribution cible

Écarts maximaux seed-par-seed entre le meilleur proposal et le proposal historique :

{_markdown(posterior_delta)}

Après agrégation des cinq chaînes de chaque proposal (comparaison moins sensible à un seed isolé) :

{_markdown(pooled_delta)}

Comparaison directe aux résumés actuellement publiés (`seed=12345`, 10 000 pas, stockage 1/5) :

{published_display}

Le plus grand déplacement de médiane vaut **{published_max_standardized:.3f} SD posterior publiée**; le plus grand déplacement parmi médiane et quantiles vaut **{published_max_summary_standardized:.3f} SD**. Les différences seed-par-seed les plus grandes proviennent donc principalement de l'erreur Monte Carlo du proposal historique; le nouveau proposal ne modifie pas la cible mais peut modifier certaines valeurs tabulées insuffisamment convergées.

Ces écarts doivent être interprétés conjointement avec l'ESS, Rhat et la variabilité inter-seed. Un écart qui dépasse l'incertitude Monte Carlo historique ne constitue pas à lui seul une preuve de changement de cible; les tests unitaires confirment que likelihood, prior, bounds et log-posterior ne dépendent pas du proposal.

## Réponses explicites

1. **Le proposal historique est-il sous-optimal ?** {"Oui" if best_rank["median_ess_per_second"] > 1.2 * historical_rank["median_ess_per_second"] else "Pas clairement"} selon l'ESS/s médian de cette qualification.
2. **Des pas diagonaux plus grands suffisent-ils ?** **Non.** Le meilleur diagonal, `{best_diagonal["configuration"]}`, monte à {best_diagonal["median_ess_per_second"]:.2f} ESS/s médian mais garde un ESS minimal de {best_diagonal["min_ess"]:.1f}, très inférieur au proposal corrélé.
3. **La paramétrisation `(m,d)` aide-t-elle ?** **Oui, mais moins.** `{best_md["configuration"]}` atteint {best_md["median_ess_per_second"]:.2f} ESS/s médian et Rhat max {best_md["max_split_rhat"]:.4f}; le Jacobien constant garantit la même cible.
4. **Le proposal corrélé améliore-t-il davantage l'ESS ?** {"Oui" if best_rank["strategy"] == "pilot_covariance" else "Non sur ce protocole"}.
5. **Stratégie générique recommandée :** `short pilot -> covariance empirique + ridge 1e-6 -> covariance fixe`, si `{best_name}` demeure premier après examen; sinon retenir la meilleure configuration du classement.
6. **Longueur finale :** conserver au moins 10 000 itérations par chaîne et cinq chaînes tant que les objectifs Rhat/ESS ne justifient pas une réduction. Une extension 20 000 est requise si un ESS important reste inférieur à 300.
7. **Les quantiles publiés changent-ils ?** Les médianes restent proches (maximum **{published_max_standardized:.3f} SD**), donc pas de déplacement central statistiquement important sur les pilotes. Certains quantiles bougent toutefois jusqu'à **{published_max_summary_standardized:.3f} SD**, au-delà du simple arrondi; ils doivent être recalculés avec les chaînes convergées.
8. **Faut-il recalculer les 19 cas et Figure 2 ?** **Oui**, après validation de cette qualification, avec cinq chaînes de 10 000 pas et combinaison post-burn-in seulement après `Rhat < 1.01`. Cette campagne pilote ne les a pas écrasés.

## Produits complets

- `posterior_summaries.csv`: mean, median, SD, q025, q10, q25, q75, q90, q975, ACF(1), IACT, ESS et ESS/s.
- `run_diagnostics.csv`: acceptance, runtime, meilleur misfit normalisé et chemins des chaînes.
- `autocorrelation_functions.csv.gz`: ACF complète jusqu'au lag {MAX_ACF_LAG}.
- `split_rhat.csv` et `interseed_variability.csv`: convergence et stabilité multi-chain.
- `configuration_ranking.csv` et `posterior_target_comparison.csv`: sélection et contrôle de cible.
- `posterior_pooled_comparison.csv` et `published_reference_comparison.csv`: accord de cible agrégé et impact sur les valeurs publiées.
- `chains/*.npz`: chaque état post-burn-in réellement diagnostiqué.

## Tests logiciels

Résultat : **{test_result}**. Les tests ciblés couvrent symétrie/covariance, transformation aller-retour, Jacobien, reproductibilité, régularisation, rejet aux bounds et invariance de la cible. Aucun test ni golden Ploemeur n'est inclus dans la commande de validation.
"""
    path = ROOT / "docs" / "reports" / "mh_proposal_qualification.md"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(report, encoding="utf-8", newline="\n")
    return path


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "phase", choices=("preflight", "pilot", "screen", "analyze", "all")
    )
    parser.add_argument("--output", type=Path, default=OUTPUT)
    parser.add_argument("--workers", type=int, default=3)
    parser.add_argument("--steps", type=int, default=PRODUCTION_STEPS)
    args = parser.parse_args(argv)
    output = _guard_output(args.output)
    if args.phase in {"preflight", "all"}:
        write_preflight(output)
    if args.phase in {"pilot", "all"}:
        run_pilots(output)
    if args.phase in {"screen", "all"}:
        run_screen(output, args.workers, args.steps)
    if args.phase in {"analyze", "all"}:
        analyze(output, args.steps)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
