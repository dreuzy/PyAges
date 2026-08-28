# Copyright (c) 2021-2026 Centre national de la recherche scientifique (CNRS)
# Contributor: Jean-Raynald de Dreuzy
# SPDX-License-Identifier: CECILL-2.1

"""Separate Holten H4 sensitivity campaign for a Dirichlet(1,1,1,1) prior.

This script reads the canonical final campaign but never writes to it.  Every
new artifact is confined to results/robustness/holten_prior_dirichlet1.
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
from pathlib import Path
from typing import Any

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import scipy
from matplotlib.ticker import FormatStrFormatter
from scipy.special import expit

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from examples.natural.holten.holten_case import build_context  # noqa: E402
from examples.natural.holten.holten_four_bin import (  # noqa: E402
    BIN_ORDER,
    load_paper_4bin_fractions,
)
from examples.natural.holten.holten_prepare import prepare_holten_inputs  # noqa: E402
from examples.natural.holten.holten_reproduction import (  # noqa: E402
    TRACERS_4,
    ForwardConvention,
    _fractions,
    _matrix,
    _objective,
    build_observations,
    build_reproduction_endmembers,
    optimize_well,
)
from scripts.article.run_final_shifted_exponential import (  # noqa: E402
    _iact_ess,
    _split_rhat,
    _summary,
)
from scripts.common.mcmc_diagnostics import mcse_mean  # noqa: E402
from scripts.common.provenance import repository_provenance  # noqa: E402
from scripts.common.publication_plotting import (  # noqa: E402
    PUBLICATION_RC,
    mm_to_in,
    save_pdf_png,
)

OUTPUT = ROOT / "results" / "robustness" / "holten_prior_dirichlet1"
CANONICAL = ROOT / "results" / "final_article_simulations" / "holten_h4_final"
CONVENTION = ForwardConvention("two_year_shift_and_decay", 2.0, True, 310.0)
PILOT_STEPS = 4_000
BURN_IN = 0.20
RIDGE = 1.0e-6
DIMENSION = 3
PROPOSAL_MULTIPLIER = 2.38 / math.sqrt(DIMENSION)
NCHAINS = 5
Z_BOUNDS = (-8.0, 8.0)
REFRESH_PROBABILITY = {"73-29": 0.20, "85-34": 0.10}
FINAL_STEPS = {
    "59-05": 10_000,
    "67-19": 10_000,
    "72-22": 10_000,
    "73-29": 20_000,
    "85-33": 20_000,
    "85-34": 20_000,
    "85-35": 20_000,
}
PRIOR_SAMPLE_SIZE = 1_000_000
PRIOR_SEED = 530_000
JACOBIAN_SEED = 530_001
LOG_DIRICHLET_NORMALIZATION = math.lgamma(4.0)  # log Gamma(sum alpha)
FIGURE_C1_WIDTH_MM = 165
FIGURE_C1_HEIGHT_MM = 78
FIGURE_C1_PANEL_TITLES = (
    "(a) 0\N{EN DASH}20 yr",
    "(b) 20\N{EN DASH}40 yr",
    "(c) 40\N{EN DASH}60 yr",
    "(d) >60 yr",
)
FIGURE_C1_STATISTICS = ("median", "q10", "q90")


def _scientific_inputs():
    prepared = prepare_holten_inputs()
    endmembers = build_reproduction_endmembers(prepared, CONVENTION)
    return prepared, endmembers


def _regularize_empirical_covariance(
    samples: np.ndarray, relative_ridge: float = 1.0e-6
) -> np.ndarray:
    """Canonical scale-aware pilot covariance regularization."""
    covariance = np.atleast_2d(np.cov(np.asarray(samples), rowvar=False, ddof=1))
    typical_variance = max(float(np.trace(covariance) / covariance.shape[0]), 1.0e-12)
    return covariance + relative_ridge * typical_variance * np.eye(covariance.shape[0])


def _guard_output(path: Path) -> Path:
    resolved = path.resolve()
    if resolved == CANONICAL.resolve() or CANONICAL.resolve() in resolved.parents:
        raise ValueError("The robustness campaign refuses the canonical output tree")
    expected = (ROOT / "results" / "robustness").resolve()
    repository = ROOT.resolve()
    inside_repository = resolved == repository or repository in resolved.parents
    if inside_repository and resolved != expected and expected not in resolved.parents:
        raise ValueError(f"Output must stay below {expected}")
    resolved.mkdir(parents=True, exist_ok=True)
    return resolved


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def log_abs_stick_breaking_jacobian(z: np.ndarray) -> float | np.ndarray:
    """Log |d(f_0,f_1,f_2)/d(z_0,z_1,z_2)|, stably evaluated."""
    values = np.asarray(z, dtype=float)
    # log(sigmoid(z)) = -logaddexp(0, -z); log(1-sigmoid(z)) = -logaddexp(0, z)
    log_v = -np.logaddexp(0.0, -values)
    log_one_minus_v = -np.logaddexp(0.0, values)
    result = (
        log_v[..., 0]
        + 3.0 * log_one_minus_v[..., 0]
        + log_v[..., 1]
        + 2.0 * log_one_minus_v[..., 1]
        + log_v[..., 2]
        + log_one_minus_v[..., 2]
    )
    return float(result) if result.ndim == 0 else result


def log_dirichlet1_density_in_z(z: np.ndarray) -> float | np.ndarray:
    """Dirichlet(1,1,1,1) density transformed to bounded latent z space."""
    return LOG_DIRICHLET_NORMALIZATION + log_abs_stick_breaking_jacobian(z)


def _numerical_jacobian(z: np.ndarray, step: float = 1.0e-6) -> np.ndarray:
    jacobian = np.empty((3, 3), dtype=float)
    for column in range(3):
        delta = np.zeros(3, dtype=float)
        delta[column] = step
        jacobian[:, column] = (
            _fractions(z + delta)[:3] - _fractions(z - delta)[:3]
        ) / (2.0 * step)
    return jacobian


def validate_jacobian(output: Path, n_points: int = 256) -> pd.DataFrame:
    rng = np.random.default_rng(JACOBIAN_SEED)
    # Avoid the extreme boundary for a better conditioned finite-difference check.
    points = rng.uniform(-6.0, 6.0, size=(n_points, 3))
    rows: list[dict[str, float | int]] = []
    for index, z in enumerate(points):
        numerical = abs(float(np.linalg.det(_numerical_jacobian(z))))
        analytical = math.exp(float(log_abs_stick_breaking_jacobian(z)))
        rows.append(
            {
                "point": index,
                "z0": z[0],
                "z1": z[1],
                "z2": z[2],
                "analytical_abs_det": analytical,
                "finite_difference_abs_det": numerical,
                "absolute_error": abs(numerical - analytical),
                "relative_error": abs(numerical - analytical) / analytical,
            }
        )
    frame = pd.DataFrame(rows)
    frame.to_csv(output / "jacobian_validation.csv", index=False)
    if float(frame["relative_error"].max()) >= 1.0e-6:
        raise RuntimeError("Finite-difference Jacobian validation failed")
    return frame


def _fractions_to_z(fractions: np.ndarray) -> np.ndarray:
    fractions = np.asarray(fractions, dtype=float)
    v = np.column_stack(
        (
            fractions[:, 0],
            fractions[:, 1] / (1.0 - fractions[:, 0]),
            fractions[:, 2] / (fractions[:, 2] + fractions[:, 3]),
        )
    )
    return np.log(v) - np.log1p(-v)


def _fractions_array(z: np.ndarray) -> np.ndarray:
    v1, v2, v3 = expit(np.asarray(z, dtype=float)).T
    return np.column_stack(
        (
            v1,
            (1.0 - v1) * v2,
            (1.0 - v1) * (1.0 - v2) * v3,
            (1.0 - v1) * (1.0 - v2) * (1.0 - v3),
        )
    )


def compare_priors(output: Path) -> pd.DataFrame:
    rng = np.random.default_rng(PRIOR_SEED)
    uniform_z = rng.uniform(*Z_BOUNDS, size=(PRIOR_SAMPLE_SIZE, 3))
    current_fractions = _fractions_array(uniform_z)

    accepted: list[np.ndarray] = []
    accepted_count = 0
    proposed_count = 0
    while accepted_count < PRIOR_SAMPLE_SIZE:
        batch = rng.dirichlet(np.ones(4), size=PRIOR_SAMPLE_SIZE - accepted_count)
        latent = _fractions_to_z(batch)
        keep = np.all((latent >= Z_BOUNDS[0]) & (latent <= Z_BOUNDS[1]), axis=1)
        accepted.append(batch[keep])
        accepted_count += int(keep.sum())
        proposed_count += len(batch)
    dirichlet_fractions = np.concatenate(accepted, axis=0)[:PRIOR_SAMPLE_SIZE]

    rows: list[dict[str, Any]] = []
    for prior, samples in (
        ("uniform_z", current_fractions),
        ("dirichlet_1_truncated_to_z_bounds", dirichlet_fractions),
    ):
        for index, fraction in enumerate(BIN_ORDER):
            rows.append(
                {
                    "prior": prior,
                    "fraction": fraction,
                    "n": len(samples),
                    "mean": float(np.mean(samples[:, index])),
                    "median": float(np.median(samples[:, index])),
                    "q10": float(np.quantile(samples[:, index], 0.10)),
                    "q90": float(np.quantile(samples[:, index], 0.90)),
                    "dirichlet_rejection_acceptance": (
                        PRIOR_SAMPLE_SIZE / proposed_count
                        if prior.startswith("dirichlet")
                        else np.nan
                    ),
                }
            )
    frame = pd.DataFrame(rows)
    frame.to_csv(output / "prior_only_comparison.csv", index=False)
    return frame


def _pilot_seed(well_index: int) -> int:
    return 510_000 + well_index


def _production_seed(well_index: int, chain: int) -> int:
    return 520_000 + 100 * well_index + chain


def _sample(
    matrix: np.ndarray,
    values: np.ndarray,
    errors: np.ndarray,
    initial: np.ndarray,
    seed: int,
    steps: int,
    covariance: np.ndarray | None,
    refresh_probability: float = 0.0,
) -> dict[str, Any]:
    rng = np.random.default_rng(seed)
    current = np.clip(np.asarray(initial, dtype=float), *Z_BOUNDS)
    current_objective = _objective(matrix, values, errors, current)
    current_log_prior = float(log_dirichlet1_density_in_z(current))
    accepted = 0
    burn_count = int(steps * BURN_IN)
    stored_count = steps - burn_count
    z_samples = np.empty((stored_count, DIMENSION), dtype=float)
    fraction_samples = np.empty((stored_count, len(BIN_ORDER)), dtype=float)
    objective_samples = np.empty(stored_count, dtype=float)
    log_prior_samples = np.empty(stored_count, dtype=float)
    proposal_covariance = (
        np.eye(DIMENSION) * 0.18**2
        if covariance is None
        else np.asarray(covariance, dtype=float) * PROPOSAL_MULTIPLIER**2
    )
    stored = 0
    started = time.perf_counter()
    for step in range(steps):
        if refresh_probability > 0.0:
            selector = rng.random()
            proposal = current.copy()
            if selector < refresh_probability:
                proposal[1] = rng.uniform(*Z_BOUNDS)
            elif selector < 2.0 * refresh_probability:
                proposal[2] = rng.uniform(*Z_BOUNDS)
            else:
                proposal = current + rng.multivariate_normal(
                    np.zeros(DIMENSION), proposal_covariance
                )
        else:
            proposal = current + rng.multivariate_normal(
                np.zeros(DIMENSION), proposal_covariance
            )
        in_bounds = bool(np.all((proposal >= Z_BOUNDS[0]) & (proposal <= Z_BOUNDS[1])))
        if in_bounds:
            proposal_objective = _objective(matrix, values, errors, proposal)
            proposal_log_prior = float(log_dirichlet1_density_in_z(proposal))
            log_ratio = (
                -0.5 * (proposal_objective - current_objective)
                + proposal_log_prior
                - current_log_prior
            )
        else:
            proposal_objective = math.inf
            proposal_log_prior = -math.inf
            log_ratio = -math.inf
        if np.log(rng.random()) < min(0.0, log_ratio):
            current = proposal
            current_objective = proposal_objective
            current_log_prior = proposal_log_prior
            accepted += 1
        if step >= burn_count:
            z_samples[stored] = current
            fraction_samples[stored] = _fractions(current)
            objective_samples[stored] = current_objective
            log_prior_samples[stored] = current_log_prior
            stored += 1
    return {
        "z": z_samples,
        "fractions": fraction_samples,
        "objective": objective_samples,
        "log_prior": log_prior_samples,
        "acceptance": accepted / steps,
        "runtime": time.perf_counter() - started,
        "seed": seed,
        "steps": steps,
    }


def _pilot_path(output: Path, well: str) -> Path:
    return output / "pilots" / f"{well}_pilot.npz"


def _covariance_path(output: Path, well: str) -> Path:
    return output / "pilots" / f"{well}_covariance.npy"


def _chain_path(output: Path, well: str, chain: int) -> Path:
    suffix = "_symmetric_refresh" if well in REFRESH_PROBABILITY else ""
    return (
        output / "chains" / f"{well}_chain_{chain + 1}_n{FINAL_STEPS[well]}{suffix}.npz"
    )


def _save(path: Path, data: dict[str, Any]) -> None:
    np.savez_compressed(path, **data)


def _load(path: Path) -> dict[str, Any]:
    with np.load(path) as data:
        return {key: data[key].copy() for key in data.files}


def run_campaign(output: Path) -> None:
    (output / "pilots").mkdir(parents=True, exist_ok=True)
    (output / "chains").mkdir(parents=True, exist_ok=True)
    prepared, endmembers = _scientific_inputs()
    for well_index, well in enumerate(prepared.context.selected_wells, start=1):
        observations = build_observations(prepared, well, True)
        optimum = optimize_well(observations, endmembers)
        covariance_path = _covariance_path(output, well)
        if covariance_path.exists():
            covariance = np.load(covariance_path)
        else:
            pilot = _sample(
                optimum["matrix"],
                optimum["values"],
                optimum["errors"],
                optimum["z"],
                _pilot_seed(well_index),
                PILOT_STEPS,
                None,
            )
            _save(_pilot_path(output, well), pilot)
            covariance = _regularize_empirical_covariance(pilot["z"], RIDGE)
            np.save(covariance_path, covariance)
            print(f"Dirichlet pilot {well_index}/7: {well}", flush=True)
        for chain in range(NCHAINS):
            path = _chain_path(output, well, chain)
            if path.exists():
                continue
            result = _sample(
                optimum["matrix"],
                optimum["values"],
                optimum["errors"],
                optimum["z"],
                _production_seed(well_index, chain),
                FINAL_STEPS[well],
                covariance,
                REFRESH_PROBABILITY.get(well, 0.0),
            )
            _save(path, result)
            print(f"Dirichlet production {well}, chain {chain + 1}/5", flush=True)


def _series(data: dict[str, Any], parameter: str) -> np.ndarray:
    if parameter.startswith("z"):
        return np.asarray(data["z"][:, int(parameter[1:])], dtype=float)
    return np.asarray(data["fractions"][:, BIN_ORDER.index(parameter)], dtype=float)


def collect_diagnostics(
    output: Path,
) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    prepared, _ = _scientific_inputs()
    parameters = ("z0", "z1", "z2", *BIN_ORDER)
    convergence_rows: list[dict[str, Any]] = []
    chain_rows: list[dict[str, Any]] = []
    summary_rows: list[dict[str, Any]] = []
    for well in prepared.context.selected_wells:
        loaded = [_load(_chain_path(output, well, chain)) for chain in range(NCHAINS)]
        for chain, data in enumerate(loaded):
            chain_rows.append(
                {
                    "prior": "dirichlet_1",
                    "well": well,
                    "chain": chain + 1,
                    "seed": int(data["seed"]),
                    "steps": int(data["steps"]),
                    "stored_samples": len(data["objective"]),
                    "acceptance_rate": float(data["acceptance"]),
                    "runtime_seconds": float(data["runtime"]),
                    "best_objective": float(np.min(data["objective"])),
                    "chain_file": str(
                        _chain_path(output, well, chain).relative_to(output)
                    ),
                }
            )
        well_diagnostics: list[dict[str, Any]] = []
        for parameter in parameters:
            chains = [_series(data, parameter) for data in loaded]
            pooled = np.concatenate(chains)
            ess_values = [_iact_ess(values)[2] for values in chains]
            total_ess = float(sum(ess_values))
            row = {
                "prior": "dirichlet_1",
                "well": well,
                "parameter": parameter,
                "space": "latent_z"
                if parameter.startswith("z")
                else "physical_fraction",
                "steps_per_chain": FINAL_STEPS[well],
                "split_rhat": _split_rhat(chains),
                "ess_sum_chains": total_ess,
                "mcse_mean": mcse_mean(pooled, total_ess),
            }
            row["converged"] = bool(
                row["split_rhat"] < 1.01 and row["ess_sum_chains"] >= 300.0
            )
            well_diagnostics.append(row)
        convergence_rows.extend(well_diagnostics)
        well_converged = all(row["converged"] for row in well_diagnostics)
        for parameter in (*parameters, "objective", "log_prior"):
            if parameter in {"objective", "log_prior"}:
                values = np.concatenate(
                    [np.asarray(data[parameter]) for data in loaded]
                )
            else:
                values = np.concatenate([_series(data, parameter) for data in loaded])
            diagnostic = next(
                (row for row in well_diagnostics if row["parameter"] == parameter),
                None,
            )
            if diagnostic is None:
                chains = [np.asarray(data[parameter]) for data in loaded]
                total_ess = float(sum(_iact_ess(chain)[2] for chain in chains))
                mean_mcse = mcse_mean(values, total_ess)
            else:
                total_ess = diagnostic["ess_sum_chains"]
                mean_mcse = diagnostic["mcse_mean"]
            stats = _summary(values)
            summary_rows.append(
                {
                    "prior": "dirichlet_1",
                    "well": well,
                    "parameter": parameter,
                    "space": (
                        "latent_z"
                        if parameter.startswith("z")
                        else "physical_fraction"
                        if parameter in BIN_ORDER
                        else parameter
                    ),
                    "steps_per_chain": FINAL_STEPS[well],
                    "chains": NCHAINS,
                    "pooled_samples": len(values),
                    "well_converged": well_converged,
                    "ess_sum_chains": total_ess,
                    "mcse_mean": mean_mcse,
                    **stats,
                }
            )
    convergence = pd.DataFrame(convergence_rows)
    chains = pd.DataFrame(chain_rows)
    summaries = pd.DataFrame(summary_rows)
    convergence.to_csv(output / "convergence_diagnostics.csv", index=False)
    chains.to_csv(output / "chain_diagnostics.csv", index=False)
    summaries.to_csv(output / "posterior_summaries_dirichlet1.csv", index=False)
    return convergence, chains, summaries


def posterior_predictions(output: Path) -> pd.DataFrame:
    prepared, endmembers = _scientific_inputs()
    rows: list[dict[str, Any]] = []
    for well in prepared.context.selected_wells:
        observations = build_observations(prepared, well, True)
        elements = observations["element"]
        if elements.isna().any():
            raise RuntimeError(f"Missing tracer name in observations for {well}")
        tracer_names = elements.map(str).tolist()
        matrix = _matrix(endmembers, tracer_names)
        fractions = np.concatenate(
            [
                _load(_chain_path(output, well, chain))["fractions"]
                for chain in range(NCHAINS)
            ]
        )
        modeled = fractions @ matrix.T
        observed = observations["concentration"].to_numpy(float)
        errors = observations["error"].to_numpy(float)
        median_modeled = np.median(modeled, axis=0)
        standardized = (observed - median_modeled) / errors
        for index, tracer in enumerate(tracer_names):
            rows.append(
                {
                    "prior": "dirichlet_1",
                    "well": well,
                    "tracer": tracer,
                    "observed": observed[index],
                    "uncertainty": errors[index],
                    "modeled_median": median_modeled[index],
                    "modeled_q10": np.quantile(modeled[:, index], 0.10),
                    "modeled_q90": np.quantile(modeled[:, index], 0.90),
                    "standardized_residual": standardized[index],
                }
            )
    alternative = pd.DataFrame(rows)
    canonical = pd.read_csv(CANONICAL / "posterior_modeled_concentrations.csv")
    canonical.insert(0, "prior", "uniform_z")
    columns = list(alternative.columns)
    combined = pd.concat([canonical[columns], alternative], ignore_index=True)
    combined.to_csv(output / "standardized_residuals.csv", index=False)
    return combined


def compare_posteriors(output: Path, summaries: pd.DataFrame) -> pd.DataFrame:
    prepared, _ = _scientific_inputs()
    paper = load_paper_4bin_fractions(prepared).set_index("well_id")
    reference = pd.read_csv(CANONICAL / "posterior_summaries.csv")
    rows: list[dict[str, Any]] = []
    for well in prepared.context.selected_wells:
        old = reference.loc[
            (reference["well"] == well) & reference["parameter"].isin(BIN_ORDER)
        ].set_index("parameter")
        new = summaries.loc[
            (summaries["well"] == well) & summaries["parameter"].isin(BIN_ORDER)
        ].set_index("parameter")
        for fraction in BIN_ORDER:
            width = float(old.loc[fraction, "q90"] - old.loc[fraction, "q10"])
            shift = abs(
                float(new.loc[fraction, "median"] - old.loc[fraction, "median"])
            )
            rows.append(
                {
                    "well": well,
                    "fraction": fraction,
                    "visser_fraction": float(paper.loc[well, fraction]),
                    "reference_median": float(old.loc[fraction, "median"]),
                    "reference_q10": float(old.loc[fraction, "q10"]),
                    "reference_q90": float(old.loc[fraction, "q90"]),
                    "dirichlet_median": float(new.loc[fraction, "median"]),
                    "dirichlet_q10": float(new.loc[fraction, "q10"]),
                    "dirichlet_q90": float(new.loc[fraction, "q90"]),
                    "absolute_median_difference": shift,
                    "reference_posterior_width_q10_q90": width,
                    "difference_over_reference_width": shift / width
                    if width > 0
                    else np.nan,
                    "reference_near_zero": bool(
                        float(old.loc[fraction, "median"]) <= 0.05
                    ),
                }
            )
    comparison = pd.DataFrame(rows)
    comparison.to_csv(output / "holten_prior_robustness_fractions.csv", index=False)
    return comparison


def global_metrics(
    output: Path,
    comparison: pd.DataFrame,
    convergence: pd.DataFrame,
    chains: pd.DataFrame,
    residuals: pd.DataFrame,
) -> pd.DataFrame:
    rows = []
    diagnostic_rows: list[dict[str, Any]] = []
    for prior, median_column in (
        ("uniform_z", "reference_median"),
        ("dirichlet_1", "dirichlet_median"),
    ):
        errors = comparison[median_column] - comparison["visser_fraction"]
        local_convergence = (
            pd.read_csv(CANONICAL / "convergence_diagnostics.csv")
            if prior == "uniform_z"
            else convergence
        )
        local_chains = (
            pd.read_csv(CANONICAL / "chain_diagnostics.csv")
            if prior == "uniform_z"
            else chains
        )
        local_residuals = residuals.loc[
            residuals["prior"] == prior, "standardized_residual"
        ]
        rows.append(
            {
                "prior": prior,
                "n_fractions": len(errors),
                "mae_vs_visser": float(np.mean(np.abs(errors))),
                "median_absolute_difference_vs_visser": float(
                    np.median(np.abs(errors))
                ),
                "rmse_vs_visser": float(np.sqrt(np.mean(errors**2))),
                "maximum_absolute_difference_vs_visser": float(np.max(np.abs(errors))),
                "max_absolute_standardized_residual": float(
                    np.max(np.abs(local_residuals))
                ),
                "rmse_standardized_residual": float(
                    np.sqrt(np.mean(local_residuals**2))
                ),
                "max_split_rhat": float(local_convergence["split_rhat"].max()),
                "min_ess": float(local_convergence["ess_sum_chains"].min()),
                "min_acceptance_rate": float(local_chains["acceptance_rate"].min()),
                "median_acceptance_rate": float(
                    local_chains["acceptance_rate"].median()
                ),
                "max_acceptance_rate": float(local_chains["acceptance_rate"].max()),
            }
        )
        for well, local_group in local_convergence.groupby("well", sort=False):
            acceptances = local_chains.loc[
                local_chains["well"] == well, "acceptance_rate"
            ]
            local_standardized = residuals.loc[
                (residuals["prior"] == prior) & (residuals["well"] == well),
                "standardized_residual",
            ]
            diagnostic_rows.append(
                {
                    "prior": prior,
                    "well": well,
                    "max_split_rhat": float(local_group["split_rhat"].max()),
                    "min_ess": float(local_group["ess_sum_chains"].min()),
                    "all_parameters_converged": bool(local_group["converged"].all()),
                    "min_acceptance_rate": float(acceptances.min()),
                    "median_acceptance_rate": float(acceptances.median()),
                    "max_acceptance_rate": float(acceptances.max()),
                    "max_absolute_standardized_residual": float(
                        np.max(np.abs(local_standardized))
                    ),
                    "rmse_standardized_residual": float(
                        np.sqrt(np.mean(local_standardized**2))
                    ),
                }
            )
    metrics = pd.DataFrame(rows)
    metrics.to_csv(output / "global_metrics.csv", index=False)
    pd.DataFrame(diagnostic_rows).to_csv(
        output / "diagnostics_summary.csv", index=False
    )

    groups = comparison.groupby("reference_near_zero", as_index=False).agg(
        count=("absolute_median_difference", "count"),
        mean_abs_shift=("absolute_median_difference", "mean"),
        median_abs_shift=("absolute_median_difference", "median"),
        max_abs_shift=("absolute_median_difference", "max"),
        mean_shift_over_reference_width=("difference_over_reference_width", "mean"),
        median_shift_over_reference_width=("difference_over_reference_width", "median"),
        max_shift_over_reference_width=("difference_over_reference_width", "max"),
    )
    groups.to_csv(output / "prior_sensitivity_near_zero.csv", index=False)
    return metrics


def _figure_c1_summary_grid(
    summaries: pd.DataFrame,
    *,
    source_name: str,
    wells: tuple[str, ...],
) -> pd.DataFrame:
    """Return the complete Holten fraction grid in Figure C1 plotting order."""

    required = {"well", "parameter", *FIGURE_C1_STATISTICS}
    missing = sorted(required.difference(summaries.columns))
    if missing:
        raise ValueError(f"{source_name} is missing columns: {missing}")

    selected = summaries.loc[
        summaries["parameter"].isin(BIN_ORDER),
        ["well", "parameter", *FIGURE_C1_STATISTICS],
    ].copy()
    duplicate = selected.duplicated(["well", "parameter"], keep=False)
    if duplicate.any():
        keys = selected.loc[duplicate, ["well", "parameter"]].values.tolist()
        raise ValueError(f"{source_name} contains duplicate fraction rows: {keys}")

    expected_index = pd.MultiIndex.from_product(
        [wells, BIN_ORDER], names=["well", "parameter"]
    )
    indexed = selected.set_index(["well", "parameter"])
    missing_keys = expected_index.difference(indexed.index).tolist()
    extra_keys = indexed.index.difference(expected_index).tolist()
    if missing_keys or extra_keys:
        raise ValueError(
            f"{source_name} does not contain exactly the Figure C1 well/fraction "
            f"grid (missing={missing_keys}, extra={extra_keys})"
        )
    return indexed.reindex(expected_index)


def _validate_figure_c1_inputs(
    comparison: pd.DataFrame,
    reference_summaries: pd.DataFrame,
    dirichlet_summaries: pd.DataFrame,
) -> tuple[str, ...]:
    """Verify completeness, order, and exact agreement with posterior summaries."""

    wells = tuple(build_context().selected_wells)
    required = {"well", "fraction"}
    required.update(
        f"{prefix}_{statistic}"
        for prefix in ("reference", "dirichlet")
        for statistic in FIGURE_C1_STATISTICS
    )
    missing = sorted(required.difference(comparison.columns))
    if missing:
        raise ValueError(f"Figure C1 comparison is missing columns: {missing}")

    expected_keys = [(well, fraction) for well in wells for fraction in BIN_ORDER]
    actual_keys = list(
        comparison[["well", "fraction"]].itertuples(index=False, name=None)
    )
    if actual_keys != expected_keys:
        raise ValueError(
            "Figure C1 comparison rows must contain exactly the configured Holten "
            "wells and age classes, in Figure 3 order"
        )

    source_grids = {
        "reference": _figure_c1_summary_grid(
            reference_summaries,
            source_name="Baseline posterior summaries",
            wells=wells,
        ),
        "dirichlet": _figure_c1_summary_grid(
            dirichlet_summaries,
            source_name="Dirichlet posterior summaries",
            wells=wells,
        ),
    }
    for prefix, source_grid in source_grids.items():
        for statistic in FIGURE_C1_STATISTICS:
            plotted = comparison[f"{prefix}_{statistic}"].to_numpy(dtype=float)
            source = source_grid[statistic].to_numpy(dtype=float)
            if not np.isfinite(plotted).all():
                raise ValueError(
                    f"Figure C1 contains non-finite {prefix}_{statistic} values"
                )
            if not np.array_equal(plotted, source):
                mismatch = int(np.flatnonzero(plotted != source)[0])
                well, fraction = expected_keys[mismatch]
                raise ValueError(
                    f"Figure C1 {prefix}_{statistic} for {well}/{fraction} does "
                    "not match its final posterior summaries file"
                )

        q10 = comparison[f"{prefix}_q10"].to_numpy(dtype=float)
        median = comparison[f"{prefix}_median"].to_numpy(dtype=float)
        q90 = comparison[f"{prefix}_q90"].to_numpy(dtype=float)
        if not ((0.0 <= q10).all() and (q90 <= 1.0).all()):
            raise ValueError(f"Figure C1 {prefix} intervals must lie within [0, 1]")
        if not ((q10 <= median).all() and (median <= q90).all()):
            raise ValueError(
                f"Figure C1 {prefix} summaries must satisfy q10 <= median <= q90"
            )
    return wells


def make_figure(
    output: Path,
    comparison: pd.DataFrame,
    *,
    reference_summaries: pd.DataFrame | None = None,
    dirichlet_summaries: pd.DataFrame | None = None,
) -> None:
    if reference_summaries is None:
        reference_summaries = pd.read_csv(CANONICAL / "posterior_summaries.csv")
    if dirichlet_summaries is None:
        dirichlet_summaries = pd.read_csv(output / "posterior_summaries_dirichlet1.csv")
    wells = _validate_figure_c1_inputs(
        comparison, reference_summaries, dirichlet_summaries
    )

    with plt.rc_context(PUBLICATION_RC):
        tab10 = plt.get_cmap("tab10").colors
        styles = (
            ("reference", -0.09, tab10[0], "o", "Latent-uniform prior"),
            (
                "dirichlet",
                0.09,
                tab10[1],
                "D",
                "Dirichlet(1,1,1,1) prior",
            ),
        )
        fig, axes = plt.subplots(
            1,
            4,
            figsize=(mm_to_in(FIGURE_C1_WIDTH_MM), mm_to_in(FIGURE_C1_HEIGHT_MM)),
            sharey=True,
        )
        y = np.arange(len(wells))
        for panel_index, (axis, fraction, title) in enumerate(
            zip(axes, BIN_ORDER, FIGURE_C1_PANEL_TITLES, strict=True)
        ):
            values = (
                comparison.loc[comparison["fraction"] == fraction]
                .set_index("well")
                .loc[list(wells)]
            )
            for row, well in enumerate(wells):
                for prefix, offset, color, marker, label in styles:
                    median = values.loc[well, f"{prefix}_median"]
                    axis.errorbar(
                        median,
                        row + offset,
                        xerr=[
                            [median - values.loc[well, f"{prefix}_q10"]],
                            [values.loc[well, f"{prefix}_q90"] - median],
                        ],
                        fmt=marker,
                        color=color,
                        ecolor=color,
                        markersize=4.6,
                        markeredgewidth=0.8,
                        elinewidth=1.4,
                        capsize=2.3,
                        capthick=1.1,
                        zorder=3,
                        label=label if row == 0 else None,
                    )
            axis.set_title(title, fontweight="bold", fontsize=9.0)
            axis.set_xlim(0.0, 1.0)
            axis.set_xticks((0.0, 0.5, 1.0))
            axis.xaxis.set_major_formatter(FormatStrFormatter("%g"))
            axis.set_axisbelow(True)
            axis.grid(
                True,
                axis="x",
                color="#d9d9d9",
                linewidth=0.6,
                alpha=0.65,
            )
            axis.grid(False, axis="y")
            if panel_index != 0:
                axis.tick_params(axis="y", labelleft=False)
        axes[0].set_yticks(y, wells)
        axes[0].invert_yaxis()
        handles, labels = axes[0].get_legend_handles_labels()
        handles_by_label = dict(zip(labels, handles, strict=False))
        legend_labels = tuple(style[-1] for style in styles)
        fig.supxlabel("Age fraction", x=0.55, y=0.19)
        fig.legend(
            [handles_by_label[label] for label in legend_labels],
            legend_labels,
            loc="lower center",
            bbox_to_anchor=(0.5, 0.015),
            ncol=2,
            frameon=False,
        )
        fig.subplots_adjust(left=0.10, right=0.99, top=0.84, bottom=0.29, wspace=0.18)
        save_pdf_png(fig, output, "figureC1_holten_prior_sensitivity")
        plt.close(fig)


def verify_canonical() -> dict[str, Any]:
    manifest_path = CANONICAL / "manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    mismatches = []
    for relative, expected in manifest["artifact_sha256"].items():
        recorded = Path(relative)
        candidates = (
            (recorded,)
            if recorded.is_absolute()
            else (CANONICAL / recorded, ROOT / recorded)
        )
        path = next(
            (candidate for candidate in candidates if candidate.is_file()),
            candidates[0],
        )
        actual = _sha256(path) if path.is_file() else None
        if actual != expected:
            mismatches.append(
                {"path": relative, "expected": expected, "actual": actual}
            )
    scientific_suffixes = (".csv", ".csv.gz", ".npz", ".npy")
    scientific_mismatches = [
        item
        for item in mismatches
        if item["path"].lower().endswith(scientific_suffixes)
    ]
    source_mismatches = []
    for relative, expected in manifest["source_sha256"].items():
        path = ROOT / Path(relative)
        actual = _sha256(path) if path.is_file() else None
        if actual != expected:
            source_mismatches.append(
                {"path": relative, "expected": expected, "actual": actual}
            )
    input_mismatches = []
    for relative, expected in manifest["input_sha256"].items():
        path = ROOT / Path(relative)
        actual = _sha256(path) if path.is_file() else None
        if actual != expected:
            input_mismatches.append(
                {"path": relative, "expected": expected, "actual": actual}
            )
    model_source_names = {
        "examples/natural/holten/holten_reproduction.py",
        "examples/natural/holten/holten_prepare.py",
        "examples/natural/holten/holten_four_bin.py",
    }
    model_source_mismatches = [
        item
        for item in source_mismatches
        if item["path"].replace("\\", "/") in model_source_names
    ]
    try:
        canonical_directory = str(CANONICAL.resolve().relative_to(ROOT.resolve()))
    except ValueError:
        canonical_directory = str(CANONICAL.resolve())
    return {
        "canonical_directory": canonical_directory,
        "canonical_manifest_sha256": _sha256(manifest_path),
        "checked_artifact_count": len(manifest["artifact_sha256"]),
        "all_artifacts_match_manifest": not mismatches,
        "all_scientific_data_artifacts_match_manifest": not scientific_mismatches,
        "mismatches": mismatches,
        "scientific_data_mismatches": scientific_mismatches,
        "all_input_files_match_manifest": not input_mismatches,
        "input_mismatches": input_mismatches,
        "all_holten_model_sources_match_manifest": not model_source_mismatches,
        "holten_model_source_mismatches": model_source_mismatches,
        "all_recorded_sources_match_manifest": not source_mismatches,
        "source_mismatches": source_mismatches,
    }


def write_manifest(
    output: Path,
    jacobian: pd.DataFrame,
    prior_comparison: pd.DataFrame,
    canonical_integrity: dict[str, Any],
) -> None:
    artifacts = [
        path
        for path in output.rglob("*")
        if path.is_file() and path.name != "manifest.json"
    ]
    payload = {
        "repository": repository_provenance(ROOT),
        "created_at": pd.Timestamp.now(tz="Europe/Paris").isoformat(),
        "purpose": "Separate Holten H4 sensitivity test; canonical campaign reused read-only",
        "git_head": subprocess.run(
            ["git", "rev-parse", "HEAD"],
            cwd=ROOT,
            capture_output=True,
            text=True,
            check=True,
        ).stdout.strip(),
        "git_status_porcelain_v2": subprocess.run(
            ["git", "status", "--porcelain=v2"],
            cwd=ROOT,
            capture_output=True,
            text=True,
            check=True,
        ).stdout.splitlines(),
        "versions": {
            "python": platform.python_version(),
            "numpy": np.__version__,
            "scipy": scipy.__version__,
            "pandas": pd.__version__,
        },
        "protocol": {
            "configuration": "H4",
            "tracers": TRACERS_4,
            "bins": BIN_ORDER,
            "selected_forward_convention": CONVENTION.__dict__,
            "reference_prior": "Uniform([-8,8]^3) in latent z",
            "alternative_prior_physical": "Dirichlet(1,1,1,1)",
            "alternative_log_density_in_z": "log(6) + log|df_independent/dz|",
            "analytical_log_abs_jacobian": "log(v1)+3log(1-v1)+log(v2)+2log(1-v2)+log(v3)+log(1-v3)",
            "latent_z_bounds": list(Z_BOUNDS),
            "alternative_prior_boundary_treatment": "Dirichlet conditioned on all three stick logits lying in [-8,8]",
            "likelihood": "exp(-J/2)",
            "pilot_steps": PILOT_STEPS,
            "final_steps_by_well": FINAL_STEPS,
            "chains": NCHAINS,
            "burn_in": BURN_IN,
            "ridge": RIDGE,
            "proposal": "fixed pilot covariance Gaussian random walk",
            "proposal_scale": "2.38/sqrt(3)",
            "coordinate_refresh_probability_per_coordinate": REFRESH_PROBABILITY,
            "seed_rule": "pilot=510000+one_based_well; production=520000+100*one_based_well+zero_based_chain",
            "prior_only_sample_size_each": PRIOR_SAMPLE_SIZE,
            "prior_only_seed": PRIOR_SEED,
            "near_zero_definition": "reference posterior median <= 0.05",
        },
        "validation": {
            "jacobian_points": len(jacobian),
            "jacobian_max_relative_error": float(jacobian["relative_error"].max()),
            "dirichlet_prior_sampling_acceptance": float(
                prior_comparison.loc[
                    prior_comparison["prior"].str.startswith("dirichlet"),
                    "dirichlet_rejection_acceptance",
                ].iloc[0]
            ),
            "canonical_integrity": canonical_integrity,
        },
        "source_sha256": {
            str(Path(__file__).resolve().relative_to(ROOT)): _sha256(
                Path(__file__).resolve()
            ),
            "examples/natural/holten/holten_reproduction.py": _sha256(
                ROOT / "examples" / "natural" / "holten" / "holten_reproduction.py"
            ),
            "examples/natural/holten/holten_prepare.py": _sha256(
                ROOT / "examples" / "natural" / "holten" / "holten_prepare.py"
            ),
            "examples/natural/holten/holten_four_bin.py": _sha256(
                ROOT / "examples" / "natural" / "holten" / "holten_four_bin.py"
            ),
            "scripts/article/run_final_shifted_exponential.py": _sha256(
                ROOT / "scripts" / "article" / "run_final_shifted_exponential.py"
            ),
        },
        "canonical_manifest_sha256": _sha256(CANONICAL / "manifest.json"),
        "artifact_sha256": {
            str(path.relative_to(output)): _sha256(path) for path in sorted(artifacts)
        },
    }
    (output / "manifest.json").write_text(
        json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
    )


def main() -> int:
    output = _guard_output(OUTPUT)
    canonical_before = verify_canonical()
    if not canonical_before["all_scientific_data_artifacts_match_manifest"]:
        raise RuntimeError(
            "Canonical scientific data artifacts do not match their manifest before robustness run"
        )
    if not canonical_before["all_input_files_match_manifest"]:
        raise RuntimeError("Canonical Holten input files do not match their manifest")
    if not canonical_before["all_holten_model_sources_match_manifest"]:
        raise RuntimeError("Canonical Holten model sources do not match their manifest")
    jacobian = validate_jacobian(output)
    priors = compare_priors(output)
    run_campaign(output)
    convergence, chains, summaries = collect_diagnostics(output)
    residuals = posterior_predictions(output)
    comparison = compare_posteriors(output, summaries)
    global_metrics(output, comparison, convergence, chains, residuals)
    make_figure(output, comparison, dirichlet_summaries=summaries)
    canonical_after = verify_canonical()
    if canonical_after != canonical_before:
        raise RuntimeError("Canonical campaign changed during robustness run")
    (output / "canonical_integrity.json").write_text(
        json.dumps(canonical_after, indent=2) + "\n", encoding="utf-8"
    )
    write_manifest(output, jacobian, priors, canonical_after)
    print(f"Robustness campaign complete: {output}")
    return 0


def _cli(argv: list[str] | None = None) -> int:
    global OUTPUT, CANONICAL
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--output",
        type=Path,
        default=OUTPUT,
        help="Fresh directory for the separate prior-sensitivity campaign.",
    )
    parser.add_argument(
        "--canonical-holten",
        type=Path,
        default=CANONICAL,
        help="Read-only canonical Holten campaign used for comparison.",
    )
    args = parser.parse_args(argv)
    OUTPUT = args.output.resolve()
    CANONICAL = args.canonical_holten.resolve()
    return main()


if __name__ == "__main__":
    raise SystemExit(_cli())
