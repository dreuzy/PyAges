"""Stabilized Ploemeur physical shifted-IG article campaign.

This runner intentionally limits the experiment to F09 and F11.  It uses the
physical shifted-IG implementation, the current CDF/partial-first-moment
convolution engine and the corrected current tracer chronicles.  The
deprecated Simpson forward and the former CFC-12 header bug are never
reintroduced.
"""

# The repository root and non-interactive Matplotlib backend are configured
# before importing local modules and pyplot.
# ruff: noqa: E402, I001

from __future__ import annotations

import argparse
import hashlib
import json
import math
import os
import platform
import shutil
import subprocess
import sys
import time
from concurrent.futures import ProcessPoolExecutor
from dataclasses import dataclass
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import matplotlib
import numpy as np
import pandas as pd
import scipy
from scipy.stats import invgauss

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402

from pyage.calibration.methods.prior import (
    make_prior_expo,
)
from pyage.calibration.ig_parameterization import (
    physical_moments_to_scipy,
    physical_to_scipy_coordinates,
    scipy_to_physical_coordinates,
    scipy_to_physical_moments,
)
from pyage.calibration.mh_proposals import regularize_empirical_covariance
from pyage.calibration.problem import CalibrationProblem
from pyage.concentrations.concentrations import Concentrations
from scripts.common.mcmc_diagnostics import (
    ess as _ess,
    rank_normalize as _rank_normalize,
    split_rhat as _split_rhat,
)
from scripts.common.reporting import markdown_table
from scripts.common.provenance import repository_provenance
from sites.ploemeur.benchmarks.scipy_ig_prior import (
    BENCHMARK_NAME,
    logpdf as article_prior_logpdf,
)

OUTPUT = ROOT / "results" / "ploemeur_targeted_ig_reproduction"
SHIFTED_SUMMARY: Path | None = None
BENCHMARK_LPM = ROOT / "sites" / "ploemeur" / "benchmarks" / BENCHMARK_NAME / "data_lpm"
ORI_DIRECTORY = ROOT / "sites" / "ploemeur" / "data" / "ori"
PARAMETERS = ("M", "S", "t0", "a", "s", "t50")
SEEDS = (12345, 24680, 54321, 97531, 86420)
PILOT_STEPS = int(os.environ.get("PYAGE_PLOEMEUR_IG_PILOT_STEPS", "1200"))
PRODUCTION_STEPS = int(os.environ.get("PYAGE_PLOEMEUR_IG_PRODUCTION_STEPS", "12000"))
PRODUCTION_WARMUP = int(os.environ.get("PYAGE_PLOEMEUR_IG_WARMUP_STEPS", "2000"))
MIN_ESS = 300.0
MAX_RHAT = 1.01

OBSERVATIONS = {
    "F09": ORI_DIRECTORY / "ori_ploemeur_F09_2005_2024.txt",
    "F11": ORI_DIRECTORY / "ori_ploemeur_F11_2004_2024.txt",
}


@dataclass
class ChainResult:
    samples: np.ndarray
    objectives: np.ndarray
    log_posteriors: np.ndarray
    accepted: np.ndarray
    elapsed_seconds: float


def _load_observations(
    well: str, interval: tuple[float, float] | None
) -> Concentrations:
    observations = Concentrations.from_file(OBSERVATIONS[well])
    if interval is not None:
        start, end = interval
        frame = observations.cv.loc[
            observations.cv["date"].between(start, end, inclusive="both")
        ]
        observations = Concentrations.from_dataframe(frame)
    observations.cv["unit"] = "pptv"
    observations.error_affect_from_value(0.2)
    if set(observations.names()) != {"cfc11", "cfc12", "cfc113"}:
        raise RuntimeError(f"Unexpected tracer set for {well}")
    return observations


def _prepare_problem(well: str, interval: tuple[float, float] | None):
    observations = _load_observations(well, interval)
    problem = CalibrationProblem(
        observations,
        "ig_shifted",
        lpm_directory=BENCHMARK_LPM,
        explore_objective=False,
        explore_reachable=False,
    ).prepare()
    return problem, observations


def _bootstrap_samples(well: str, interval: tuple[float, float] | None) -> pd.DataFrame:
    """Build deterministic, data-informed starts without archived posteriors."""
    problem, observations = _prepare_problem(well, interval)
    observed = observations.cv["concentration"].to_numpy(dtype=float)
    errors = observations.cv["error"].to_numpy(dtype=float)
    rows = []
    for shape in (0.25, 0.5, 1.0, 2.0, 5.0, 10.0, 25.0, 60.0):
        for scale in (0.5, 1.0, 2.0, 4.0, 8.0, 15.0, 25.0):
            for shift in (0.5, 2.0, 5.0, 10.0, 20.0, 35.0, 48.0):
                physical = scipy_to_physical_coordinates((shape, scale, shift))
                objective = problem.objective_function(physical, observed, errors)
                rows.append(
                    {
                        "M": physical[0],
                        "S": physical[1],
                        "t0": physical[2],
                        "objective_J": objective,
                    }
                )
    candidates = _augment(pd.DataFrame(rows)).sort_values("objective_J")
    # A moderately broad elite set seeds independent chains and the first
    # proposal while keeping initialization tied only to versioned inputs.
    return candidates.head(120).reset_index(drop=True)


def _augment(frame: pd.DataFrame) -> pd.DataFrame:
    result = frame.copy()
    result["a"] = result["S"] ** 2 / result["M"] ** 2
    result["s"] = result["M"] ** 3 / result["S"] ** 2
    result["t50"] = result["t0"] + invgauss.ppf(
        0.5, result["a"].to_numpy(), scale=result["s"].to_numpy()
    )
    return result


def _empirical_prior_spec(samples: pd.DataFrame) -> dict[str, list[float]]:
    """Build the published product of marginal histograms in (a,s,t0)."""
    spec: dict[str, list[float]] = {}
    bounds = {"a": (0.1, 100.0), "s": (0.1, 30.0), "t0": (0.1, 50.0)}
    for name, (lower, upper) in bounds.items():
        histogram, bins = np.histogram(samples[name], bins=100, density=True)
        decay = 500.0 / (upper - lower)
        x_values, probabilities = make_prior_expo(
            bins[:-1],
            histogram,
            xmin=lower,
            xmax=upper,
            n_points=101,
            decay_left=decay,
            decay_right=decay,
        )
        spec[f"{name}_x"] = x_values.tolist()
        spec[f"{name}_p"] = probabilities.tolist()
    return spec


def _conditional_log_prior(params: np.ndarray, spec: dict[str, list[float]]) -> float:
    mean, std, shift = params
    shape, scale = physical_moments_to_scipy(mean, std)
    if not (0.1 <= shape <= 100.0 and 0.1 <= scale <= 30.0 and 0.1 <= shift <= 50.0):
        return -math.inf
    probability = 1.0
    for name, value in (("a", shape), ("s", scale), ("t0", shift)):
        x_values = np.asarray(spec[f"{name}_x"])
        probabilities = np.asarray(spec[f"{name}_p"])
        probability *= probabilities[int(np.argmin(np.abs(x_values - value)))]
    # Historical empirical prior is a product density in (a,s,t0).  Its
    # physical-coordinate density therefore also carries |d(a,s)/d(M,S)|=2/S.
    return math.log(max(float(probability), 1.0e-300)) + math.log(2.0) - math.log(std)


def _run_chain_worker(payload: dict[str, Any]) -> ChainResult:
    problem, observations = _prepare_problem(payload["well"], payload["interval"])
    observed = observations.cv["concentration"].to_numpy(dtype=float)
    errors = observations.cv["error"].to_numpy(dtype=float)
    conditional = payload.get("conditional_prior")

    def evaluate(params: np.ndarray) -> tuple[float, float]:
        if conditional is None:
            log_prior = article_prior_logpdf(params)
        else:
            log_prior = _conditional_log_prior(params, conditional)
        if not math.isfinite(log_prior):
            return -math.inf, math.inf
        objective = problem.objective_function(params, observed, errors)
        return log_prior - 0.5 * objective, objective

    rng = np.random.default_rng(payload["seed"])
    state = np.asarray(payload["initial"], dtype=float)
    log_posterior, objective = evaluate(state)
    if not math.isfinite(log_posterior):
        raise RuntimeError(f"Initial state is outside target support: {state}")
    covariance = np.asarray(payload["covariance"], dtype=float)
    steps = int(payload["steps"])
    samples = np.empty((steps, 3), dtype=float)
    objectives = np.empty(steps, dtype=float)
    log_posteriors = np.empty(steps, dtype=float)
    accepted = np.zeros(steps, dtype=bool)
    started = time.perf_counter()
    for index in range(steps):
        proposed_coordinates = physical_to_scipy_coordinates(
            state
        ) + rng.multivariate_normal(np.zeros(3), covariance)
        proposed = scipy_to_physical_coordinates(proposed_coordinates)
        proposed_log_posterior, proposed_objective = evaluate(proposed)
        log_hastings = (
            0.0
            if not np.all(np.isfinite(proposed)) or proposed[1] <= 0.0
            else math.log(proposed[1] / state[1])
        )
        if (
            math.log(rng.random())
            < proposed_log_posterior - log_posterior + log_hastings
        ):
            state = proposed
            log_posterior = proposed_log_posterior
            objective = proposed_objective
            accepted[index] = True
        samples[index] = state
        objectives[index] = objective
        log_posteriors[index] = log_posterior
    return ChainResult(
        samples=samples,
        objectives=objectives,
        log_posteriors=log_posteriors,
        accepted=accepted,
        elapsed_seconds=time.perf_counter() - started,
    )


def _parallel_chains(
    well: str,
    interval: tuple[float, float] | None,
    initials: np.ndarray,
    covariance: np.ndarray,
    steps: int,
    conditional_prior: dict[str, list[float]] | None,
    seed_offset: int,
) -> list[ChainResult]:
    payloads = [
        {
            "well": well,
            "interval": interval,
            "initial": initials[index].tolist(),
            "covariance": covariance.tolist(),
            "steps": steps,
            "conditional_prior": conditional_prior,
            "seed": SEEDS[index] + seed_offset,
        }
        for index in range(len(SEEDS))
    ]
    with ProcessPoolExecutor(max_workers=len(SEEDS)) as executor:
        return list(executor.map(_run_chain_worker, payloads))


def _initials_from_samples(samples: pd.DataFrame) -> np.ndarray:
    ordered = samples.sort_values("t50").reset_index(drop=True)
    positions = np.linspace(0.08, 0.92, len(SEEDS)) * (len(ordered) - 1)
    return ordered.loc[np.rint(positions).astype(int), ["M", "S", "t0"]].to_numpy()


def _run_adapted_stage(
    well: str,
    stage: str,
    interval: tuple[float, float] | None,
    initialization_samples: pd.DataFrame | None,
    conditional_prior: dict[str, list[float]] | None,
) -> np.ndarray:
    stage_dir = OUTPUT / stage / well
    stage_dir.mkdir(parents=True, exist_ok=True)
    if initialization_samples is None:
        initialization_samples = _bootstrap_samples(well, interval)
        initialization_samples.to_csv(
            stage_dir / "bootstrap_candidates.csv", index=False
        )
    initials = _initials_from_samples(initialization_samples)
    initial_coordinates = np.asarray(
        [
            physical_to_scipy_coordinates(row)
            for row in initialization_samples[["M", "S", "t0"]].to_numpy()
        ]
    )
    base_covariance = regularize_empirical_covariance(
        initial_coordinates, relative_ridge=1.0e-10
    )
    optimal = 2.38 / math.sqrt(3.0)
    first_covariance = base_covariance * (0.25 * optimal) ** 2
    print(
        f"[{well} {stage}] pilot 1 ({PILOT_STEPS} steps x {len(SEEDS)} chains)",
        flush=True,
    )
    pilot_1 = _parallel_chains(
        well, interval, initials, first_covariance, PILOT_STEPS, conditional_prior, 0
    )
    pilot_1_values = np.asarray(
        [
            physical_to_scipy_coordinates(row)
            for item in pilot_1
            for row in item.samples[PILOT_STEPS // 2 :]
        ]
    )
    empirical = regularize_empirical_covariance(pilot_1_values, relative_ridge=1.0e-10)
    pilot_acceptance = float(np.mean([item.accepted.mean() for item in pilot_1]))
    second_multiplier = (
        0.65 if pilot_acceptance > 0.45 else 0.5 if pilot_acceptance > 0.30 else 0.35
    )
    second_covariance = empirical * (second_multiplier * optimal) ** 2
    print(
        f"[{well} {stage}] pilot 2; pilot-1 acceptance={pilot_acceptance:.3f}; "
        f"multiplier={second_multiplier:.2f}",
        flush=True,
    )
    pilot_2 = _parallel_chains(
        well,
        interval,
        np.asarray([item.samples[-1] for item in pilot_1]),
        second_covariance,
        PILOT_STEPS,
        conditional_prior,
        1000,
    )
    pilot_2_values = np.asarray(
        [
            physical_to_scipy_coordinates(row)
            for item in pilot_2
            for row in item.samples[PILOT_STEPS // 2 :]
        ]
    )
    fixed_empirical = regularize_empirical_covariance(
        pilot_2_values, relative_ridge=1.0e-10
    )
    second_acceptance = float(np.mean([item.accepted.mean() for item in pilot_2]))
    production_multiplier = second_multiplier
    if second_acceptance > 0.42:
        production_multiplier *= 1.25
    elif second_acceptance < 0.15:
        production_multiplier *= 0.70
    fixed_covariance = fixed_empirical * (production_multiplier * optimal) ** 2
    print(
        f"[{well} {stage}] production ({PRODUCTION_STEPS} steps x {len(SEEDS)} chains); "
        f"pilot-2 acceptance={second_acceptance:.3f}; fixed multiplier={production_multiplier:.3f}",
        flush=True,
    )
    production = _parallel_chains(
        well,
        interval,
        np.asarray([item.samples[-1] for item in pilot_2]),
        fixed_covariance,
        PRODUCTION_STEPS,
        conditional_prior,
        2000,
    )
    retained = np.asarray([item.samples[PRODUCTION_WARMUP:] for item in production])
    objectives = np.asarray(
        [item.objectives[PRODUCTION_WARMUP:] for item in production]
    )
    log_posteriors = np.asarray(
        [item.log_posteriors[PRODUCTION_WARMUP:] for item in production]
    )
    np.savez_compressed(
        stage_dir / "production_chains.npz",
        samples=retained,
        objectives=objectives,
        log_posteriors=log_posteriors,
        fixed_covariance=fixed_covariance,
    )
    run_rows = []
    for index, item in enumerate(production):
        chain = _augment(
            pd.DataFrame(item.samples[PRODUCTION_WARMUP:], columns=["M", "S", "t0"])
        )
        chain["objective_J"] = item.objectives[PRODUCTION_WARMUP:]
        chain["log_posterior"] = item.log_posteriors[PRODUCTION_WARMUP:]
        chain.to_csv(
            stage_dir / f"trace_chain_{index + 1}.csv.gz",
            index=False,
            compression="gzip",
        )
        run_rows.append(
            {
                "well": well,
                "stage": stage,
                "chain": index + 1,
                "seed": SEEDS[index] + 2000,
                "acceptance": item.accepted.mean(),
                "elapsed_seconds": item.elapsed_seconds,
                "retained_draws": len(chain),
            }
        )
    pd.DataFrame(run_rows).to_csv(stage_dir / "chain_diagnostics.csv", index=False)
    np.savetxt(
        stage_dir / "fixed_proposal_covariance.csv", fixed_covariance, delimiter=","
    )
    _write_posterior_products(stage_dir, retained)
    return retained


def _augmented_chains(chains: np.ndarray) -> np.ndarray:
    augmented = []
    for chain in chains:
        augmented.append(
            _augment(pd.DataFrame(chain, columns=["M", "S", "t0"]))[
                list(PARAMETERS)
            ].to_numpy()
        )
    return np.asarray(augmented)


def _write_posterior_products(directory: Path, chains: np.ndarray) -> None:
    augmented = _augmented_chains(chains)
    flat = pd.DataFrame(augmented.reshape(-1, len(PARAMETERS)), columns=PARAMETERS)
    summary = flat.describe(percentiles=[0.025, 0.1, 0.25, 0.5, 0.75, 0.9, 0.975]).T
    summary.to_csv(directory / "posterior_summary.csv")
    diagnostic_rows = []
    for index, name in enumerate(PARAMETERS):
        values = augmented[:, :, index]
        ranked = _rank_normalize(values)
        low = (values <= np.quantile(values, 0.05)).astype(float)
        high = (values >= np.quantile(values, 0.95)).astype(float)
        diagnostic_rows.append(
            {
                "parameter": name,
                "split_rhat": _split_rhat(values),
                "bulk_ess": _ess(ranked),
                "tail_ess": min(_ess(low), _ess(high)),
            }
        )
    pd.DataFrame(diagnostic_rows).to_csv(
        directory / "convergence_diagnostics.csv", index=False
    )

    figure, axes = plt.subplots(3, 2, figsize=(11, 8), constrained_layout=True)
    for parameter_index, (axis, name) in enumerate(
        zip(axes.flat, PARAMETERS, strict=True)
    ):
        for chain_index in range(augmented.shape[0]):
            axis.plot(augmented[chain_index, :, parameter_index], lw=0.35, alpha=0.75)
        axis.set_title(name)
        axis.set_xlabel("retained draw")
    figure.savefig(directory / "trace_plots.png", dpi=180)
    plt.close(figure)

    figure, axes = plt.subplots(3, 2, figsize=(11, 8), constrained_layout=True)
    for axis, name in zip(axes.flat, PARAMETERS, strict=True):
        axis.hist(flat[name], bins=80, density=True, alpha=0.8)
        axis.set_title(name)
    figure.savefig(directory / "posterior_distributions.png", dpi=180)
    plt.close(figure)


def _load_stage_chains(stage: str, well: str) -> np.ndarray:
    return np.load(OUTPUT / stage / well / "production_chains.npz")["samples"]


def _full_series_passes(well: str, chains: np.ndarray) -> tuple[bool, dict[str, float]]:
    new = _augment(pd.DataFrame(chains.reshape(-1, 3), columns=["M", "S", "t0"]))
    diagnostics = pd.read_csv(
        OUTPUT / "full_series" / well / "convergence_diagnostics.csv"
    )
    converged = bool(
        diagnostics["split_rhat"].max() < MAX_RHAT
        and diagnostics[["bulk_ess", "tail_ess"]].min().min() >= MIN_ESS
    )
    payload = {
        "t50_mean": float(new["t50"].mean()),
        "t50_sd": float(new["t50"].std(ddof=1)),
        "max_split_rhat": float(diagnostics["split_rhat"].max()),
        "min_bulk_ess": float(diagnostics["bulk_ess"].min()),
        "min_tail_ess": float(diagnostics["tail_ess"].min()),
        "converged": converged,
    }
    return converged, payload


def _write_full_series_gate() -> bool:
    status = {}
    all_pass = True
    for well in ("F09", "F11"):
        chains = _load_stage_chains("full_series", well)
        passed, payload = _full_series_passes(well, chains)
        status[well] = {"passed": passed, **payload}
        all_pass &= passed
        print(f"[{well} full_series] passed={passed}: {payload}", flush=True)
    (OUTPUT / "full_series_gate.json").write_text(
        json.dumps({"passed": all_pass, "wells": status}, indent=2), encoding="utf-8"
    )
    return all_pass


def run_full_series(*, resume: bool = False) -> bool:
    OUTPUT.mkdir(parents=True, exist_ok=True)
    for well in ("F09", "F11"):
        if (
            resume
            and (OUTPUT / "full_series" / well / "production_chains.npz").is_file()
        ):
            print(
                f"[{well} full_series] reusing complete production chains", flush=True
            )
            continue
        _run_adapted_stage(well, "full_series", None, None, None)
    return _write_full_series_gate()


def extend_full_series(well: str, extension_steps: int) -> bool:
    """Continue existing stationary chains with their fixed proposal."""
    stage_dir = OUTPUT / "full_series" / well
    chain_path = stage_dir / "production_chains.npz"
    with np.load(chain_path) as archive:
        existing = np.asarray(archive["samples"])
        existing_objectives = np.asarray(archive["objectives"])
        existing_log_posteriors = np.asarray(archive["log_posteriors"])
        fixed_covariance = np.asarray(archive["fixed_covariance"])
    if existing.shape[0] != len(SEEDS) or existing.shape[2] != 3:
        raise ValueError(
            f"Unexpected existing chain shape for {well}: {existing.shape}"
        )

    original_draws = existing.shape[1]
    baseline = stage_dir / f"production_chains_initial_n{original_draws}.npz"
    if not baseline.exists():
        shutil.copy2(chain_path, baseline)
    print(
        f"[{well} full_series] extending {len(SEEDS)} chains by {extension_steps} draws "
        f"from {original_draws} retained draws",
        flush=True,
    )
    continuation = _parallel_chains(
        well,
        None,
        existing[:, -1, :],
        fixed_covariance,
        extension_steps,
        None,
        100_000 + original_draws,
    )
    new_samples = np.asarray([item.samples for item in continuation])
    new_objectives = np.asarray([item.objectives for item in continuation])
    new_log_posteriors = np.asarray([item.log_posteriors for item in continuation])
    extension_path = stage_dir / (
        f"extension_from_n{original_draws}_by_n{extension_steps}.npz"
    )
    np.savez_compressed(
        extension_path,
        samples=new_samples,
        objectives=new_objectives,
        log_posteriors=new_log_posteriors,
        fixed_covariance=fixed_covariance,
    )

    combined = np.concatenate((existing, new_samples), axis=1)
    combined_objectives = np.concatenate((existing_objectives, new_objectives), axis=1)
    combined_log_posteriors = np.concatenate(
        (existing_log_posteriors, new_log_posteriors), axis=1
    )
    np.savez_compressed(
        chain_path,
        samples=combined,
        objectives=combined_objectives,
        log_posteriors=combined_log_posteriors,
        fixed_covariance=fixed_covariance,
    )
    previous_diagnostics = pd.read_csv(stage_dir / "chain_diagnostics.csv")
    extension_rows = []
    combined_rows = []
    for index, item in enumerate(continuation):
        chain = _augment(pd.DataFrame(combined[index], columns=["M", "S", "t0"]))
        chain["objective_J"] = combined_objectives[index]
        chain["log_posterior"] = combined_log_posteriors[index]
        chain.to_csv(
            stage_dir / f"trace_chain_{index + 1}.csv.gz",
            index=False,
            compression="gzip",
        )
        extension_rows.append(
            {
                "well": well,
                "stage": "full_series_extension",
                "chain": index + 1,
                "seed": SEEDS[index] + 100_000 + original_draws,
                "acceptance": item.accepted.mean(),
                "elapsed_seconds": item.elapsed_seconds,
                "extension_draws": extension_steps,
                "total_retained_draws": combined.shape[1],
            }
        )
        previous = previous_diagnostics.loc[
            previous_diagnostics["chain"] == index + 1
        ].iloc[0]
        previous_steps = int(
            previous.get(
                "total_steps",
                int(previous["retained_draws"]) + PRODUCTION_WARMUP,
            )
        )
        total_steps = previous_steps + extension_steps
        combined_rows.append(
            {
                "well": well,
                "stage": "full_series",
                "chain": index + 1,
                "seed": previous["seed"],
                "acceptance": (
                    float(previous["acceptance"]) * previous_steps
                    + float(item.accepted.mean()) * extension_steps
                )
                / total_steps,
                "elapsed_seconds": float(previous["elapsed_seconds"])
                + item.elapsed_seconds,
                "retained_draws": combined.shape[1],
                "total_steps": total_steps,
            }
        )
    pd.DataFrame(extension_rows).to_csv(
        stage_dir / f"extension_diagnostics_from_n{original_draws}.csv", index=False
    )
    pd.DataFrame(combined_rows).to_csv(stage_dir / "chain_diagnostics.csv", index=False)
    _write_posterior_products(stage_dir, combined)
    return _write_full_series_gate()


def run_conditioned(*, resume: bool = False) -> None:
    gate = json.loads((OUTPUT / "full_series_gate.json").read_text(encoding="utf-8"))
    if not gate["passed"]:
        raise RuntimeError(
            "Full-series gate failed; conditioned stages are prohibited."
        )
    for well in ("F09", "F11"):
        full = _augment(
            pd.DataFrame(
                _load_stage_chains("full_series", well).reshape(-1, 3),
                columns=["M", "S", "t0"],
            )
        )
        full_prior = _empirical_prior_spec(full)
        span_name = "span_2012_2024_conditioned_on_full"
        span_path = OUTPUT / span_name / well / "production_chains.npz"
        if resume and span_path.is_file():
            print(
                f"[{well} {span_name}] reusing complete production chains", flush=True
            )
            span_chains = _load_stage_chains(span_name, well)
        else:
            span_chains = _run_adapted_stage(
                well, span_name, (2012.0, 2025.0), full, full_prior
            )
        span = _augment(
            pd.DataFrame(span_chains.reshape(-1, 3), columns=["M", "S", "t0"])
        )
        span_prior = _empirical_prior_spec(span)
        window_name = "window_2014_2015_conditioned"
        window_path = OUTPUT / window_name / well / "production_chains.npz"
        if resume and window_path.is_file():
            print(
                f"[{well} {window_name}] reusing complete production chains", flush=True
            )
        else:
            _run_adapted_stage(well, window_name, (2014.0, 2016.0), span, span_prior)


def _result_row(well: str, workflow: str, chains: np.ndarray) -> dict[str, Any]:
    new = _augment(pd.DataFrame(chains.reshape(-1, 3), columns=["M", "S", "t0"]))
    diagnostics = pd.read_csv(OUTPUT / workflow / well / "convergence_diagnostics.csv")
    return {
        "well": well,
        "workflow": workflow,
        "model": "ig_shifted_physical",
        "t50_mean": new["t50"].mean(),
        "t50_median": new["t50"].median(),
        "t50_sd": new["t50"].std(ddof=1),
        "t50_q10": new["t50"].quantile(0.10),
        "t50_q90": new["t50"].quantile(0.90),
        "max_split_rhat": diagnostics["split_rhat"].max(),
        "min_bulk_ess": diagnostics["bulk_ess"].min(),
        "min_tail_ess": diagnostics["tail_ess"].min(),
        "retained_draws_per_chain": chains.shape[1],
        "acceptance_min": pd.read_csv(
            OUTPUT / workflow / well / "chain_diagnostics.csv"
        )["acceptance"].min(),
        "acceptance_max": pd.read_csv(
            OUTPUT / workflow / well / "chain_diagnostics.csv"
        )["acceptance"].max(),
    }


def _distribution_verification() -> pd.DataFrame:
    rows = []
    age_grid = np.linspace(0.0, 500.0, 2001)
    for well in ("F09", "F11"):
        chains = _load_stage_chains("window_2014_2015_conditioned", well)
        frame = _augment(pd.DataFrame(chains.reshape(-1, 3), columns=["M", "S", "t0"]))
        ordered = frame.sort_values("t50").reset_index(drop=True)
        for quantile in (0.1, 0.5, 0.9):
            row = ordered.iloc[int(round(quantile * (len(ordered) - 1)))]
            shape, scale = physical_moments_to_scipy(row.M, row.S)
            roundtrip_mean, roundtrip_std = scipy_to_physical_moments(shape, scale)
            old_pdf = invgauss.pdf(age_grid, shape, loc=row.t0, scale=scale)
            old_cdf = invgauss.cdf(age_grid, shape, loc=row.t0, scale=scale)
            new_pdf = invgauss.pdf(
                age_grid,
                row.S**2 / row.M**2,
                loc=row.t0,
                scale=row.M**3 / row.S**2,
            )
            new_cdf = invgauss.cdf(
                age_grid,
                row.S**2 / row.M**2,
                loc=row.t0,
                scale=row.M**3 / row.S**2,
            )
            problem, observations = _prepare_problem(well, (2014.0, 2016.0))
            observed = observations.cv["concentration"].to_numpy(dtype=float)
            errors = observations.cv["error"].to_numpy(dtype=float)
            _, concentrations = problem.objective_function(
                [row.M, row.S, row.t0], observed, errors, return_concentrations=True
            )
            _, concentrations_roundtrip = problem.objective_function(
                [roundtrip_mean, roundtrip_std, row.t0],
                observed,
                errors,
                return_concentrations=True,
            )
            rows.append(
                {
                    "well": well,
                    "posterior_t50_quantile": quantile,
                    "M": row.M,
                    "S": row.S,
                    "a": shape,
                    "s": scale,
                    "t0": row.t0,
                    "t50": row.t50,
                    "roundtrip_M_abs_error": abs(roundtrip_mean - row.M),
                    "roundtrip_S_abs_error": abs(roundtrip_std - row.S),
                    "max_pdf_abs_error": np.max(np.abs(new_pdf - old_pdf)),
                    "max_cdf_abs_error": np.max(np.abs(new_cdf - old_cdf)),
                    "t50_abs_error": abs(
                        row.t50 - (row.t0 + invgauss.ppf(0.5, shape, scale=scale))
                    ),
                    "max_cfc_abs_error_pptv": np.max(
                        np.abs(
                            np.asarray(concentrations)
                            - np.asarray(concentrations_roundtrip)
                        )
                    ),
                }
            )
    return pd.DataFrame(rows)


def finalize() -> None:
    rows = []
    for well in ("F09", "F11"):
        for workflow in (
            "full_series",
            "span_2012_2024_conditioned_on_full",
            "window_2014_2015_conditioned",
        ):
            rows.append(_result_row(well, workflow, _load_stage_chains(workflow, well)))
    results = pd.DataFrame(rows)
    results.to_csv(OUTPUT / "ploemeur_ig_stabilized_results.csv", index=False)
    verification = _distribution_verification()
    verification.to_csv(OUTPUT / "distribution_equivalence_checks.csv", index=False)
    _write_report(results, verification)
    _manifest(results)


def _markdown_table(frame: pd.DataFrame) -> str:
    return markdown_table(frame, float_format=".6g")


def _write_report(results: pd.DataFrame, verification: pd.DataFrame) -> None:
    all_converged = bool(
        (results.max_split_rhat < MAX_RHAT).all()
        and (results.min_bulk_ess >= MIN_ESS).all()
        and (results.min_tail_ess >= MIN_ESS).all()
    )
    comparison = "Non calculée (résumé shifted-exponential non fourni)."
    comparison_passes: bool | None = None
    if SHIFTED_SUMMARY is not None:
        shifted = pd.read_csv(SHIFTED_SUMMARY)
        shifted = shifted.loc[
            shifted["calibration"] == "2014_2015_independent"
        ].set_index("well")
        ig = results.loc[
            results["workflow"] == "window_2014_2015_conditioned"
        ].set_index("well")
        comparison_passes = bool(
            ig.loc["F11", "t50_mean"] > shifted.loc["F11", "t50_median"]
        )
        comparison = (
            "F11 IG plus ancienne que shifted-exponential : "
            f"{comparison_passes}; IG={ig.loc['F11', 't50_mean']:.3f} ans, "
            f"shifted={shifted.loc['F11', 't50_median']:.3f} ans."
        )
    report = f"""# Ploemeur — campagne stabilisée avec l’IG physique

## Verdict de la nouvelle campagne

Les six ensembles postérieurs sont **{"convergés" if all_converged else "non convergés"}**. Cette campagne est reconstruite uniquement à partir du code, des configurations et des observations versionnés. Les anciens postérieurs ne servent ni d’entrée, ni d’initialisation, ni de critère d’arrêt.

## Résultats quantitatifs

{_markdown_table(results)}

## Contrôle inter-modèles

{comparison}

## Vérification de distribution

Sur {len(verification)} tirages représentatifs, les erreurs maximales sont : PDF {verification.max_pdf_abs_error.max():.3e}, CDF {verification.max_cdf_abs_error.max():.3e}, t50 {verification.t50_abs_error.max():.3e} an et concentrations CFC {verification.max_cfc_abs_error_pptv.max():.3e} pptv.

## Méthode et garde-fous

Le prior d’article est conservé exactement après conversion physique : `a=S²/M²`, `s=M³/S²`, avec densité transformée proportionnelle à `2/S`. La likelihood vaut `J=sum(((model-observed)/(0.2*observed))**2)` et `logL=-0.5*J`. Le conditionnement suit full-series → 2012–2024 → 2014–2015. Les états initiaux et la première covariance sont construits par un balayage déterministe versionné, puis les propositions sont adaptées pendant deux pilotes et figées pour la production.

Le statut de reproduction de l’article doit être décidé en comparant ces nouvelles valeurs à la version figée du manuscrit, pas à un dossier historique local absent. `comparison_passes={comparison_passes}` consigne séparément le contrôle IG/shifted lorsqu’il est disponible.
"""
    (OUTPUT / "PLOEMEUR_IG_STABILIZED.md").write_text(
        report, encoding="utf-8", newline="\n"
    )


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _path_label(path: Path, base: Path) -> str:
    try:
        return path.resolve().relative_to(base.resolve()).as_posix()
    except ValueError:
        return path.resolve().as_posix()


def _manifest(results: pd.DataFrame) -> None:
    artifacts = [
        path
        for path in OUTPUT.rglob("*")
        if path.is_file() and path.name != "manifest.json"
    ]
    sources = [
        Path(__file__),
        ROOT / "sites/ploemeur/benchmarks/scipy_ig_prior.py",
        ROOT / "scripts/common/mcmc_diagnostics.py",
        *OBSERVATIONS.values(),
    ]
    payload = {
        "repository": repository_provenance(ROOT),
        "created_at": pd.Timestamp.now(tz="Europe/Paris").isoformat(),
        "git_head": subprocess.run(
            ["git", "rev-parse", "HEAD"],
            cwd=ROOT,
            capture_output=True,
            text=True,
            check=True,
        ).stdout.strip(),
        "git_status": subprocess.run(
            ["git", "status", "--short"],
            cwd=ROOT,
            capture_output=True,
            text=True,
            check=True,
        ).stdout.splitlines(),
        "versions": {
            "python": platform.python_version(),
            "numpy": np.__version__,
            "pandas": pd.__version__,
            "scipy": scipy.__version__,
        },
        "protocol": {
            "wells": ["F09", "F11"],
            "workflows": sorted(results["workflow"].unique()),
            "pilot_steps": PILOT_STEPS,
            "production_steps": PRODUCTION_STEPS,
            "warmup_steps": PRODUCTION_WARMUP,
            "chains": len(SEEDS),
            "seeds": list(SEEDS),
            "initialization": "deterministic prior-coordinate grid ranked by objective",
            "legacy_results_used_as_inputs": False,
            "shifted_summary": str(SHIFTED_SUMMARY) if SHIFTED_SUMMARY else None,
        },
        "source_sha256": {_path_label(path, ROOT): _sha256(path) for path in sources},
        "artifact_sha256": {
            _path_label(path, OUTPUT): _sha256(path) for path in artifacts
        },
    }
    (OUTPUT / "manifest.json").write_text(
        json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )


def _validate_run_lengths() -> None:
    if PILOT_STEPS < 100 or PRODUCTION_WARMUP < 0:
        raise ValueError("Pilot/warm-up lengths are invalid")
    if PRODUCTION_STEPS - PRODUCTION_WARMUP < 1000:
        raise ValueError("At least 1000 retained production draws are required")


def _run_selected_stage(
    args: argparse.Namespace, parser: argparse.ArgumentParser
) -> None:
    if args.stage == "resume":
        if not run_full_series(resume=True):
            print("Full-series gate failed; stopping before conditioning.", flush=True)
            raise SystemExit(2)
        run_conditioned(resume=True)
        finalize()
        return
    if args.stage == "extend-full":
        if args.well is None:
            parser.error("--well is required with --stage extend-full")
        if args.extension_steps < 1000:
            parser.error("--extension-steps must be at least 1000")
        if not extend_full_series(args.well, args.extension_steps):
            print("Full-series gate still fails after extension.", flush=True)
            raise SystemExit(2)
        return
    if args.stage in {"full", "all"} and not run_full_series():
        print("Full-series gate failed; stopping before conditioning.", flush=True)
        raise SystemExit(2)
    if args.stage in {"conditioned", "all"}:
        run_conditioned()
    if args.stage in {"finalize", "all"}:
        finalize()


def main(argv: list[str] | None = None) -> int:
    global OUTPUT, SHIFTED_SUMMARY
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--stage",
        choices=("full", "extend-full", "conditioned", "finalize", "all", "resume"),
        default="all",
    )
    parser.add_argument("--well", choices=("F09", "F11"))
    parser.add_argument("--extension-steps", type=int, default=64_000)
    parser.add_argument("--output", type=Path, default=OUTPUT)
    parser.add_argument(
        "--shifted-summary",
        type=Path,
        help="summary produced by the stabilized shifted-exponential Ploemeur run",
    )
    args = parser.parse_args(argv)
    OUTPUT = args.output.resolve()
    SHIFTED_SUMMARY = (
        args.shifted_summary.resolve() if args.shifted_summary is not None else None
    )
    if SHIFTED_SUMMARY is not None and not SHIFTED_SUMMARY.is_file():
        parser.error(f"--shifted-summary does not exist: {SHIFTED_SUMMARY}")
    OUTPUT.mkdir(parents=True, exist_ok=True)
    _validate_run_lengths()
    _run_selected_stage(args, parser)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
