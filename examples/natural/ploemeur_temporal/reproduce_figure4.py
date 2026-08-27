#!/usr/bin/env python3
# Copyright (c) 2021-2026 Centre national de la recherche scientifique (CNRS)
# Contributor: Jean-Raynald de Dreuzy
# SPDX-License-Identifier: CECILL-2.1

"""Rebuild the Ploemeur F09 analysis and manuscript Figure 4.

The script deliberately starts from the validated observation table and the
current PyAges convolution engine. Historical chains are never read during
calibration. Run from any working directory with either ``--calibrate`` or
``--plot-only``; every configured path is repository-relative.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import platform
import subprocess
import tarfile
from dataclasses import asdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterable

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import scipy
from scipy.integrate import IntegrationWarning, quad
from scipy.special import ndtri
from scipy.stats import rankdata

from pyages.convolution.convolution import Convolution
from pyages.convolution.settings import DEFAULT_TRACER_GRID_SETTINGS
from pyages.lpm.models.inverse_gaussian_shifted import (
    InverseGaussianShiftedLpm,
)
from pyages.tracer.tracer_root import Tracer

ROOT = Path(__file__).resolve().parents[3]
TRACERS = ("cfc11", "cfc12", "cfc113")
PARAMETERS = ("mu", "sigma", "t0")
LOWER = np.array([0.1, 0.1, 0.1])
UPPER = np.array([100.0, 30.0, 30.0])
ERROR_REL = 0.20
DATA_PATH = Path(
    "examples/natural/ploemeur_temporal/data/ori_ploemeur_F09_2005_2024.txt"
)
TRACER_DIR = Path("data_core/data_tracer")
LPM_DIR = Path("data_core/data_lpm")
DEFAULT_OUTPUT = Path("results/ploemeur_figure4_final")
SINGLE_DATE = 2010.8931506849315
QUANTILES = (0.05, 0.10, 0.50, 0.90, 0.95)


def _relative(path: Path) -> str:
    return path.resolve().relative_to(ROOT).as_posix()


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _run_git(*args: str) -> str:
    result = subprocess.run(
        ["git", *args], cwd=ROOT, text=True, capture_output=True, check=False
    )
    return result.stdout.strip()


def _git_state() -> dict:
    status = _run_git("status", "--porcelain=v1", "--untracked-files=all")
    diff = subprocess.run(
        ["git", "diff", "--binary", "HEAD"], cwd=ROOT, capture_output=True
    ).stdout
    untracked = _run_git("ls-files", "--others", "--exclude-standard").splitlines()
    digest = hashlib.sha256(diff)
    for name in sorted(untracked):
        path = ROOT / name
        if path.is_file():
            digest.update(name.encode("utf-8"))
            digest.update(bytes.fromhex(_sha256(path)))
    return {
        "sha": _run_git("rev-parse", "HEAD"),
        "dirty": bool(status),
        "diff_sha256_including_untracked_content": digest.hexdigest()
        if status
        else None,
        "status": status.splitlines(),
    }


def load_observations() -> pd.DataFrame:
    data = pd.read_csv(ROOT / DATA_PATH, sep="\t")
    required = {"element", "concentration", "error", "unit", "date"}
    if set(data.columns) != required:
        raise ValueError(f"Unexpected observation columns: {list(data.columns)}")
    if len(data) != 58 or data["date"].nunique() != 20:
        raise ValueError(
            f"Expected 58 observations on 20 dates, got {len(data)} on "
            f"{data['date'].nunique()} dates"
        )
    if set(data["element"]) != set(TRACERS):
        raise ValueError(
            f"Expected exactly {TRACERS}, got {sorted(data['element'].unique())}"
        )
    if (data["element"].str.lower() == "sf6").any():
        raise ValueError("Ploemeur F09 must not contain SF6")
    data = data.copy()
    data["unit"] = "pptv"
    data["error"] = ERROR_REL * data["concentration"]
    data.insert(0, "observation_id", np.arange(len(data), dtype=int))
    return data


class PreparedForward:
    """Batched evaluation of final-engine prepared tracer grids."""

    def __init__(self, observations: pd.DataFrame):
        tracer_objects = {
            name: Tracer(ROOT / TRACER_DIR, name=name) for name in TRACERS
        }
        self.convolutions = [
            Convolution(tracer_objects[row.element], date=float(row.date))
            for row in observations.itertuples()
        ]
        grids = [item.prepare() for item in self.convolutions]
        all_edges = np.concatenate([grid.edges for grid in grids])
        self.edges, inverse = np.unique(all_edges, return_inverse=True)
        edge_offsets = np.cumsum([0, *[len(grid.edges) for grid in grids]])
        left_global = np.concatenate(
            [
                np.arange(edge_offsets[i], edge_offsets[i + 1] - 1)
                for i in range(len(grids))
            ]
        )
        self.left = inverse[left_global]
        self.right = inverse[left_global + 1]
        self.edge_left = self.edges[self.left]
        self.widths = self.edges[self.right] - self.edge_left
        self.k_left = np.concatenate([grid.k_left for grid in grids])
        self.k_mid = np.concatenate([grid.k_mid for grid in grids])
        self.k_right = np.concatenate([grid.k_right for grid in grids])
        self.observation_index = np.concatenate(
            [np.full(len(grid.k_mid), i, dtype=int) for i, grid in enumerate(grids)]
        )
        self.n_observations = len(grids)
        settings = DEFAULT_TRACER_GRID_SETTINGS
        global_scale = max(
            float(np.max(np.abs(self.k_left))),
            float(np.max(np.abs(self.k_mid))),
            float(np.max(np.abs(self.k_right))),
            np.finfo(float).eps,
        )
        local_scale = np.maximum.reduce(
            (np.abs(self.k_left), np.abs(self.k_mid), np.abs(self.k_right))
        )
        curvature = np.abs(self.k_mid - 0.5 * (self.k_left + self.k_right))
        self.use_linear = curvature <= settings.linear_curvature_factor * (
            settings.absolute_tolerance_factor * global_scale
            + settings.relative_tolerance * local_scale
        )
        self.slopes = (self.k_right - self.k_left) / self.widths
        self.model = InverseGaussianShiftedLpm(directory_lpm=ROOT / LPM_DIR)

    def predict(self, theta: np.ndarray) -> np.ndarray:
        mu, sigma, t0 = np.asarray(theta, dtype=float)
        self.model.p.update(mu=mu, sigma=sigma, shift=t0)
        cdf, moment = self.model.cdf_and_partial_first_moment(self.edges)
        weights = cdf[self.right] - cdf[self.left]
        centered = moment[self.right] - moment[self.left] - self.edge_left * weights
        weight_tolerance = (
            DEFAULT_TRACER_GRID_SETTINGS.floating_weight_epsilon_factor
            * np.finfo(float).eps
            * max(1.0, float(np.max(np.abs(cdf))))
        )
        moment_tolerance = (
            DEFAULT_TRACER_GRID_SETTINGS.floating_weight_epsilon_factor
            * np.finfo(float).eps
            * max(1.0, float(self.edges[-1]))
        )
        if np.any(weights < -weight_tolerance) or np.any(centered < -moment_tolerance):
            raise FloatingPointError("Non-monotone CDF or partial moment")
        weights = np.maximum(weights, 0.0)
        centered = np.clip(centered, 0.0, self.widths * weights)
        contribution = np.where(
            self.use_linear,
            self.k_left * weights + self.slopes * centered,
            self.k_mid * weights,
        )
        return np.bincount(
            self.observation_index,
            weights=contribution,
            minlength=self.n_observations,
        )

    def window_mass(self, theta: np.ndarray) -> np.ndarray:
        mu, sigma, t0 = np.asarray(theta, dtype=float)
        self.model.p.update(mu=mu, sigma=sigma, shift=t0)
        tmax = np.array(
            [max(0.0, conv.date - conv.datemin) for conv in self.convolutions]
        )
        return np.asarray(self.model.cdf(tmax) - self.model.cdf(0.0), dtype=float)


class LogPosterior:
    def __init__(self, observations: pd.DataFrame):
        self.observations = observations.reset_index(drop=True)
        self.forward = PreparedForward(self.observations)
        self.observed = self.observations["concentration"].to_numpy(float)
        self.error = self.observations["error"].to_numpy(float)

    def evaluate(self, theta: np.ndarray) -> tuple[float, float, np.ndarray]:
        theta = np.asarray(theta, dtype=float)
        if np.any(theta < LOWER) or np.any(theta > UPPER):
            return -np.inf, np.inf, np.full_like(self.observed, np.nan)
        modeled = self.forward.predict(theta)
        residual = (modeled - self.observed) / self.error
        objective = float(residual @ residual)
        return -0.5 * objective, objective, modeled


def _reflect(unit: np.ndarray) -> np.ndarray:
    reflected = np.mod(unit, 2.0)
    return np.where(reflected > 1.0, 2.0 - reflected, reflected)


def _physical(unit: np.ndarray) -> np.ndarray:
    return LOWER + np.asarray(unit) * (UPPER - LOWER)


def _pilot_chain(
    target: LogPosterior, start: np.ndarray, seed: int, steps: int
) -> tuple[np.ndarray, np.ndarray, float, np.ndarray]:
    rng = np.random.default_rng(seed)
    q = np.asarray(start, dtype=float).copy()
    logp = target.evaluate(_physical(q))[0]
    history = np.empty((steps, 3))
    accepted = np.zeros(steps, dtype=bool)
    covariance = np.eye(3) * 0.08**2
    scale = 1.0
    window_accepted = 0
    for step in range(steps):
        proposal = _reflect(
            q + rng.multivariate_normal(np.zeros(3), covariance * scale)
        )
        proposal_logp = target.evaluate(_physical(proposal))[0]
        if math.log(rng.random()) < proposal_logp - logp:
            q, logp = proposal, proposal_logp
            accepted[step] = True
            window_accepted += 1
        history[step] = q
        if (step + 1) % 100 == 0:
            rate = window_accepted / 100.0
            scale *= math.exp(np.clip(rate - 0.28, -0.5, 0.5))
            scale = float(np.clip(scale, 1.0e-4, 1.0e2))
            window_accepted = 0
            if step >= 499:
                recent = history[max(0, step - 1999) : step + 1]
                empirical = np.cov(recent.T)
                covariance = (2.38**2 / 3.0) * empirical + np.eye(3) * 1.0e-6
                scale = 1.0
    recent = history[steps // 2 :]
    proposal_cov = (2.38**2 / 3.0) * np.cov(recent.T) + np.eye(3) * 1.0e-7
    return q, proposal_cov, float(np.mean(accepted)), history


def _production_chunk(
    target: LogPosterior,
    start: np.ndarray,
    covariance: np.ndarray,
    rng: np.random.Generator,
    draws: int,
) -> tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray, np.ndarray]:
    q = np.asarray(start, dtype=float).copy()
    logp, objective, _ = target.evaluate(_physical(q))
    samples = np.empty((draws, 3))
    logps = np.empty(draws)
    objectives = np.empty(draws)
    accepted = np.zeros(draws, dtype=bool)
    for step in range(draws):
        proposal = _reflect(q + rng.multivariate_normal(np.zeros(3), covariance))
        p_logp, p_objective, _ = target.evaluate(_physical(proposal))
        if math.log(rng.random()) < p_logp - logp:
            q, logp, objective = proposal, p_logp, p_objective
            accepted[step] = True
        samples[step] = _physical(q)
        logps[step] = logp
        objectives[step] = objective
    return q, samples, logps, objectives, accepted


def _split(chains: np.ndarray) -> np.ndarray:
    n = chains.shape[1] // 2
    if n < 2:
        raise ValueError("At least four draws per chain are required")
    return np.concatenate((chains[:, :n], chains[:, -n:]), axis=0)


def _rank_normalize(values: np.ndarray) -> np.ndarray:
    flat = values.reshape(-1)
    ranks = rankdata(flat, method="average")
    probability = (ranks - 0.375) / (len(flat) + 0.25)
    return ndtri(probability).reshape(values.shape)


def _basic_rhat(values: np.ndarray) -> float:
    values = _split(values)
    m, n = values.shape
    chain_means = values.mean(axis=1)
    between = n * np.var(chain_means, ddof=1)
    within = np.mean(np.var(values, axis=1, ddof=1))
    if within == 0.0:
        return 1.0 if between == 0.0 else np.inf
    var_plus = (n - 1.0) / n * within + between / n
    return float(np.sqrt(var_plus / within))


def split_rhat(values: np.ndarray) -> float:
    split = _split(values)
    ranked = _rank_normalize(split)
    folded = np.abs(split - np.median(split))
    return max(_basic_rhat(ranked), _basic_rhat(_rank_normalize(folded)))


def _autocovariance(values: np.ndarray) -> np.ndarray:
    values = np.asarray(values, dtype=float)
    centered = values - values.mean()
    n = len(values)
    fft = np.fft.rfft(centered, n=2 * n)
    return np.fft.irfft(fft * np.conjugate(fft), n=2 * n)[:n] / n


def effective_sample_size(values: np.ndarray) -> float:
    values = _split(np.asarray(values, dtype=float))
    m, n = values.shape
    autocov = np.asarray([_autocovariance(chain) for chain in values])
    within = np.mean(autocov[:, 0] * n / (n - 1.0))
    between = n * np.var(values.mean(axis=1), ddof=1)
    var_plus = (n - 1.0) / n * within + between / n
    if not np.isfinite(var_plus) or var_plus <= 0.0:
        return float(m * n)
    rho = np.ones(n)
    for lag in range(1, n):
        rho[lag] = 1.0 - (within - np.mean(autocov[:, lag])) / var_plus
    pairs = []
    for lag in range(1, n - 1, 2):
        pair = rho[lag] + rho[lag + 1]
        if pair < 0.0:
            break
        pairs.append(pair)
    if pairs:
        pairs = np.minimum.accumulate(np.asarray(pairs))
        tau = max(1.0, -1.0 + 2.0 * (1.0 + float(np.sum(pairs))))
    else:
        tau = 1.0
    return float(min(m * n, m * n / tau))


def chain_diagnostics(chains: np.ndarray) -> pd.DataFrame:
    rows = []
    for index, name in enumerate(PARAMETERS):
        values = chains[:, :, index]
        ranked = _rank_normalize(values)
        low = (values <= np.quantile(values, 0.05)).astype(float)
        high = (values >= np.quantile(values, 0.95)).astype(float)
        rows.append(
            {
                "parameter": name,
                "split_rhat": split_rhat(values),
                "bulk_ess": effective_sample_size(ranked),
                "tail_ess": min(
                    effective_sample_size(low), effective_sample_size(high)
                ),
            }
        )
    return pd.DataFrame(rows)


def _autocorrelation_table(chains: np.ndarray, max_lag: int = 100) -> pd.DataFrame:
    rows = []
    for chain in range(chains.shape[0]):
        for parameter, name in enumerate(PARAMETERS):
            covariance = _autocovariance(chains[chain, :, parameter])
            acf = covariance[: max_lag + 1] / covariance[0]
            rows.extend(
                {
                    "chain": chain + 1,
                    "parameter": name,
                    "lag": lag,
                    "autocorrelation": value,
                }
                for lag, value in enumerate(acf)
            )
    return pd.DataFrame(rows)


def _summaries(chains: np.ndarray, experiment: str) -> pd.DataFrame:
    flat = chains.reshape(-1, 3)
    values = {
        "mu": flat[:, 0],
        "sigma": flat[:, 1],
        "t0": flat[:, 2],
        "mu_plus_t0": flat[:, 0] + flat[:, 2],
    }
    rows = []
    for name, sample in values.items():
        quantile = np.quantile(sample, QUANTILES)
        rows.append(
            {
                "experiment": experiment,
                "parameter": name,
                "mean": np.mean(sample),
                "median": np.median(sample),
                "sd": np.std(sample, ddof=1),
                **{
                    f"q{int(q * 100):02d}": value
                    for q, value in zip(QUANTILES, quantile, strict=False)
                },
            }
        )
    return pd.DataFrame(rows)


def _joint_indices(total: int, count: int, seed: int) -> np.ndarray:
    rng = np.random.default_rng(seed)
    return rng.choice(total, size=min(total, count), replace=False)


def posterior_diagnostics(
    experiment: str,
    target: LogPosterior,
    chains: np.ndarray,
    output: Path,
    seed: int,
    sample_count: int,
) -> None:
    flat = chains.reshape(-1, 3)
    indices = _joint_indices(len(flat), sample_count, seed)
    joint = flat[indices]
    predictions = np.asarray([target.forward.predict(theta) for theta in joint])
    window = np.asarray([target.forward.window_mass(theta) for theta in joint])
    observed = target.observed
    error = target.error
    standardized = (predictions - observed[None, :]) / error[None, :]
    contribution = standardized**2
    table = target.observations.copy()
    table["prediction_median"] = np.median(predictions, axis=0)
    table["prediction_q05"] = np.quantile(predictions, 0.05, axis=0)
    table["prediction_q95"] = np.quantile(predictions, 0.95, axis=0)
    table["standardized_residual_median"] = np.median(standardized, axis=0)
    table["objective_contribution_median"] = np.median(contribution, axis=0)
    table["objective_contribution_mean"] = np.mean(contribution, axis=0)
    table["window_mass_min"] = np.min(window, axis=0)
    table["window_mass_q05"] = np.quantile(window, 0.05, axis=0)
    table["window_mass_median"] = np.median(window, axis=0)
    table["window_mass_q95"] = np.quantile(window, 0.95, axis=0)
    table.to_csv(
        output / f"{experiment}_posterior_predictive_observations.csv", index=False
    )
    objective = np.sum(contribution, axis=1)
    latent_covered = (observed >= np.quantile(predictions, 0.05, axis=0)) & (
        observed <= np.quantile(predictions, 0.95, axis=0)
    )
    pd.DataFrame(
        {
            "experiment": experiment,
            "mean": [objective.mean()],
            "median": [np.median(objective)],
            "sd": [objective.std(ddof=1)],
            "q05": [np.quantile(objective, 0.05)],
            "q95": [np.quantile(objective, 0.95)],
            "rmse_standardized_median": [np.median(np.sqrt(objective / len(observed)))],
            "log_likelihood_mean": [-0.5 * objective.mean()],
            "log_likelihood_median": [-0.5 * np.median(objective)],
            "log_likelihood_q05": [-0.5 * np.quantile(objective, 0.95)],
            "log_likelihood_q95": [-0.5 * np.quantile(objective, 0.05)],
            "latent_curve_90pct_coverage": [latent_covered.mean()],
            "latent_curve_90pct_covered_n": [latent_covered.sum()],
            "n_observations": [len(observed)],
        }
    ).to_csv(output / f"{experiment}_objective_summary.csv", index=False)
    window_rows = []
    for tracer in TRACERS:
        mask = target.observations["element"].to_numpy() == tracer
        values = window[:, mask].reshape(-1)
        window_rows.append(
            {
                "experiment": experiment,
                "tracer": tracer,
                "minimum": np.min(values),
                "q05": np.quantile(values, 0.05),
                "median": np.median(values),
                "q95": np.quantile(values, 0.95),
                "fraction_below_0_95": np.mean(values < 0.95),
            }
        )
    pd.DataFrame(window_rows).to_csv(
        output / f"{experiment}_window_mass_summary.csv", index=False
    )
    np.savez_compressed(
        output / f"{experiment}_window_mass_samples.npz",
        posterior_flat_indices=indices,
        observation_id=target.observations["observation_id"].to_numpy(),
        window_mass=window,
    )


def _quadrature_reference(conv: Convolution, model: InverseGaussianShiftedLpm) -> float:
    tracer = conv.tracer
    p0 = float(model.cdf(0.0))
    p1 = float(model.cdf(conv.date - conv.datemin))
    if p1 <= p0:
        return 0.0
    breaks: list[float] = []
    dates = tracer.convolution_dates
    if dates is not None:
        ages = conv.date - np.asarray(dates, dtype=float)
        ages = ages[(ages > 0.0) & (ages < conv.date - conv.datemin)]
        candidate = np.asarray(model.cdf(ages), dtype=float)
        breaks = np.unique(candidate[(candidate > p0) & (candidate < p1)]).tolist()

    def integrand(probability: float) -> float:
        age = float(model.cdf_inv(probability))
        return float(tracer.get_concentration(conv.date - age, age))

    import warnings

    with warnings.catch_warnings():
        warnings.simplefilter("ignore", IntegrationWarning)
        return float(
            quad(
                integrand,
                p0,
                p1,
                points=breaks or None,
                epsabs=1.0e-9,
                epsrel=1.0e-9,
                limit=2000,
            )[0]
        )


def quadrature_checks(
    experiment: str, target: LogPosterior, chains: np.ndarray, output: Path
) -> None:
    flat = chains.reshape(-1, 3)
    chosen = [
        np.argmin(np.sum((flat - np.median(flat, axis=0)) ** 2, axis=1)),
        np.argmin(flat[:, 0] + flat[:, 2]),
        np.argmax(flat[:, 0] + flat[:, 2]),
    ]
    obs_indices = sorted(
        set([0, len(target.observations) // 2, len(target.observations) - 1])
    )
    rows = []
    model = InverseGaussianShiftedLpm(directory_lpm=ROOT / LPM_DIR)
    for draw_index in chosen:
        theta = flat[draw_index]
        model.p.update(mu=theta[0], sigma=theta[1], shift=theta[2])
        batched = target.forward.predict(theta)
        for obs_index in obs_indices:
            reference = _quadrature_reference(
                target.forward.convolutions[obs_index], model
            )
            rows.append(
                {
                    "experiment": experiment,
                    "posterior_flat_index": draw_index,
                    "observation_id": int(
                        target.observations.iloc[obs_index]["observation_id"]
                    ),
                    "engine": batched[obs_index],
                    "quadrature": reference,
                    "absolute_difference": abs(batched[obs_index] - reference),
                    "relative_difference": abs(batched[obs_index] - reference)
                    / max(abs(reference), 1e-12),
                }
            )
    pd.DataFrame(rows).to_csv(
        output / f"{experiment}_quadrature_checks.csv", index=False
    )


def _trace_plots(experiment: str, chains: np.ndarray, output: Path) -> None:
    fig, axes = plt.subplots(3, 1, figsize=(10, 7), sharex=True)
    for parameter, axis in enumerate(axes):
        for chain in range(chains.shape[0]):
            axis.plot(chains[chain, :, parameter], lw=0.35, alpha=0.75)
        axis.set_ylabel(PARAMETERS[parameter])
    axes[-1].set_xlabel("retained production draw (no thinning)")
    fig.suptitle(f"{experiment}: complete post-warm-up traces")
    fig.tight_layout()
    fig.savefig(output / f"{experiment}_trace.png", dpi=180)
    plt.close(fig)


def _acf_plot(experiment: str, table: pd.DataFrame, output: Path) -> None:
    fig, axes = plt.subplots(1, 3, figsize=(11, 3.2), sharey=True)
    for axis, parameter in zip(axes, PARAMETERS, strict=False):
        subset = table[table.parameter == parameter]
        for _, chain in subset.groupby("chain"):
            axis.plot(chain.lag, chain.autocorrelation, lw=0.8)
        axis.set_title(parameter)
        axis.set_xlabel("lag")
        axis.axhline(0.0, color="black", lw=0.5)
    axes[0].set_ylabel("autocorrelation")
    fig.suptitle(f"{experiment}: production-chain autocorrelation")
    fig.tight_layout()
    fig.savefig(output / f"{experiment}_autocorrelation.png", dpi=180)
    plt.close(fig)


def calibrate_experiment(
    experiment: str,
    observations: pd.DataFrame,
    output: Path,
    seeds: list[int],
    pilot_steps: int,
    production_chunk: int,
    max_production: int,
    min_ess: float,
) -> tuple[np.ndarray, LogPosterior]:
    target = LogPosterior(observations)
    starts = np.array(
        [[0.15, 0.20, 0.20], [0.80, 0.20, 0.70], [0.25, 0.80, 0.75], [0.75, 0.75, 0.25]]
    )
    if len(seeds) > len(starts):
        rng = np.random.default_rng(seeds[0] + 999)
        starts = np.vstack((starts, rng.random((len(seeds) - len(starts), 3))))
    pilot_final, covariances, pilot_rates, pilot_history = [], [], [], []
    for chain, seed in enumerate(seeds):
        final, covariance, rate, history = _pilot_chain(
            target, starts[chain], seed, pilot_steps
        )
        pilot_final.append(final)
        covariances.append(covariance)
        pilot_rates.append(rate)
        pilot_history.append(_physical(history))
    np.savez_compressed(
        output / f"{experiment}_pilot.npz",
        chains=np.asarray(pilot_history),
        starts_unit=starts[: len(seeds)],
        proposal_covariances=np.asarray(covariances),
        acceptance=np.asarray(pilot_rates),
    )
    print(
        f"{experiment}: pilot acceptance "
        + ", ".join(f"{value:.3f}" for value in pilot_rates),
        flush=True,
    )
    states = np.asarray(pilot_final)
    rngs = [np.random.default_rng(seed + 10_000_000) for seed in seeds]
    chain_parts: list[list[np.ndarray]] = [[] for _ in seeds]
    logp_parts: list[list[np.ndarray]] = [[] for _ in seeds]
    objective_parts: list[list[np.ndarray]] = [[] for _ in seeds]
    accept_parts: list[list[np.ndarray]] = [[] for _ in seeds]
    diagnostics = None
    retained = 0
    while retained < max_production:
        count = min(production_chunk, max_production - retained)
        for chain in range(len(seeds)):
            state, samples, logps, objectives, accepted = _production_chunk(
                target, states[chain], covariances[chain], rngs[chain], count
            )
            states[chain] = state
            chain_parts[chain].append(samples)
            logp_parts[chain].append(logps)
            objective_parts[chain].append(objectives)
            accept_parts[chain].append(accepted)
        retained += count
        chains = np.asarray([np.concatenate(parts) for parts in chain_parts])
        diagnostics = chain_diagnostics(chains)
        diagnostics.to_csv(
            output / f"{experiment}_diagnostics_checkpoint.csv", index=False
        )
        print(
            f"{experiment}: {retained} production draws/chain; "
            f"max R-hat={diagnostics.split_rhat.max():.4f}; "
            f"min bulk ESS={diagnostics.bulk_ess.min():.0f}; "
            f"min tail ESS={diagnostics.tail_ess.min():.0f}",
            flush=True,
        )
        if (
            retained >= max(2 * production_chunk, 1000)
            and diagnostics.split_rhat.max() <= 1.01
            and diagnostics.bulk_ess.min() >= min_ess
            and diagnostics.tail_ess.min() >= min_ess
        ):
            break
    logps = np.asarray([np.concatenate(parts) for parts in logp_parts])
    objectives = np.asarray([np.concatenate(parts) for parts in objective_parts])
    accepted = np.asarray([np.concatenate(parts) for parts in accept_parts])
    np.savez_compressed(
        output / f"{experiment}_raw_chains.npz",
        parameters=chains,
        log_likelihood=logps,
        objective=objectives,
        accepted=accepted,
        seeds=np.asarray(seeds),
    )
    diagnostics.to_csv(output / f"{experiment}_diagnostics.csv", index=False)
    pd.DataFrame(
        {
            "chain": np.arange(1, len(seeds) + 1),
            "seed": seeds,
            "pilot_acceptance": pilot_rates,
            "production_acceptance": accepted.mean(axis=1),
            "retained_draws": chains.shape[1],
        }
    ).to_csv(output / f"{experiment}_chain_diagnostics.csv", index=False)
    summary = _summaries(chains, experiment)
    summary.to_csv(output / f"{experiment}_posterior_summary.csv", index=False)
    flat = chains.reshape(-1, 3)
    corr = pd.DataFrame(flat, columns=PARAMETERS).corr()
    corr.to_csv(output / f"{experiment}_posterior_correlations.csv")
    acf = _autocorrelation_table(chains)
    acf.to_csv(output / f"{experiment}_autocorrelation.csv", index=False)
    _trace_plots(experiment, chains, output)
    _acf_plot(experiment, acf, output)
    return chains, target


def _prediction_frame(
    experiment: str,
    chains: np.ndarray,
    dates: np.ndarray,
    seed: int,
    draws: int,
) -> pd.DataFrame:
    rows = pd.DataFrame(
        [(tracer, date) for tracer in TRACERS for date in dates],
        columns=["element", "date"],
    )
    rows["concentration"] = 1.0
    rows["error"] = 0.2
    rows["unit"] = "pptv"
    rows.insert(0, "observation_id", np.arange(len(rows), dtype=int))
    forward = PreparedForward(rows)
    flat = chains.reshape(-1, 3)
    joint = flat[_joint_indices(len(flat), draws, seed)]
    prediction = np.asarray([forward.predict(theta) for theta in joint])
    rows["experiment"] = experiment
    rows["median"] = np.median(prediction, axis=0)
    rows["q05"] = np.quantile(prediction, 0.05, axis=0)
    rows["q95"] = np.quantile(prediction, 0.95, axis=0)
    return rows[["experiment", "element", "date", "median", "q05", "q95"]]


def create_figure(output: Path, prediction_draws: int, prediction_seed: int) -> None:
    observations = load_observations()
    chains = {
        name: np.load(output / f"{name}_raw_chains.npz")["parameters"]
        for name in ("single_date", "time_series")
    }
    dates = np.linspace(observations.date.min(), observations.date.max(), 70)
    prediction = pd.concat(
        [
            _prediction_frame(name, value, dates, prediction_seed + i, prediction_draws)
            for i, (name, value) in enumerate(chains.items())
        ],
        ignore_index=True,
    )
    prediction.to_csv(output / "figure4_prediction_data.csv", index=False)
    observations.to_csv(output / "figure4_observations.csv", index=False)

    fig = plt.figure(figsize=(12.2, 9.0), constrained_layout=True)
    outer = fig.add_gridspec(1, 2, width_ratios=[1.35, 1.0])
    left = outer[0].subgridspec(3, 1, hspace=0.08)
    right = outer[1].subgridspec(4, 1, hspace=0.18)
    colors = {"time_series": "#1769aa", "single_date": "#d95f02"}
    labels = {"time_series": "time-series", "single_date": "single-date (2010.9)"}
    for row, tracer in enumerate(TRACERS):
        axis = fig.add_subplot(left[row])
        obs = observations[observations.element == tracer]
        axis.errorbar(
            obs.date,
            obs.concentration,
            yerr=obs.error,
            fmt="o",
            ms=3.5,
            color="black",
            ecolor="0.55",
            elinewidth=0.8,
            capsize=1.5,
            label="observations ±20%" if row == 0 else None,
            zorder=3,
        )
        focus = obs[np.isclose(obs.date, SINGLE_DATE)]
        axis.scatter(
            focus.date,
            focus.concentration,
            s=65,
            facecolors="none",
            edgecolors="#c62828",
            linewidths=1.5,
            label="2010.9 observations" if row == 0 else None,
            zorder=4,
        )
        for name in ("time_series", "single_date"):
            subset = prediction[
                (prediction.element == tracer) & (prediction.experiment == name)
            ]
            axis.fill_between(
                subset.date,
                subset.q05,
                subset.q95,
                color=colors[name],
                alpha=0.18,
                linewidth=0,
                label=f"{labels[name]} central 90%" if row == 0 else None,
            )
            axis.plot(
                subset.date,
                subset["median"],
                color=colors[name],
                lw=1.5,
                label=f"{labels[name]} median" if row == 0 else None,
            )
        axis.set_ylabel(f"{tracer.upper()}\n(pptv)")
        axis.grid(alpha=0.2)
        if row < 2:
            axis.tick_params(labelbottom=False)
        else:
            axis.set_xlabel("sampling date")
        if row == 0:
            axis.legend(fontsize=7.6, ncol=2, frameon=False, loc="best")
    fig.text(0.01, 0.985, "a", fontsize=15, fontweight="bold", va="top")

    posterior_names = ("mu", "sigma", "t0", "mu + t0")
    for parameter, title in enumerate(posterior_names):
        axis = fig.add_subplot(right[parameter])
        for name in ("time_series", "single_date"):
            flat = chains[name].reshape(-1, 3)
            values = flat[:, parameter] if parameter < 3 else flat[:, 0] + flat[:, 2]
            axis.hist(
                values,
                bins=70,
                density=True,
                histtype="step",
                lw=1.4,
                color=colors[name],
                label=labels[name] if parameter == 0 else None,
            )
        axis.set_ylabel("density")
        axis.set_xlabel(f"{title} (years)")
        axis.grid(alpha=0.2)
        if parameter == 0:
            axis.legend(frameon=False, fontsize=8)
    fig.text(0.61, 0.985, "b", fontsize=15, fontweight="bold", va="top")
    fig.suptitle("Ploemeur F09 — shifted inverse Gaussian", fontsize=13)
    fig.savefig(output / "figure4.png", dpi=300)
    fig.savefig(output / "figure4.pdf")
    plt.close(fig)


def _write_manifest(
    output: Path, args: argparse.Namespace, observations: pd.DataFrame
) -> None:
    input_paths = [ROOT / DATA_PATH, ROOT / LPM_DIR / "ig_shifted" / "params.yaml"]
    for tracer in TRACERS:
        input_paths.extend(
            [
                ROOT / TRACER_DIR / tracer / f"{tracer}.yaml",
                ROOT / TRACER_DIR / tracer / "recharge.csv",
            ]
        )
    manifest = {
        "created_utc": datetime.now(timezone.utc).isoformat(),
        "git": _git_state(),
        "software": {
            "python": platform.python_version(),
            "numpy": np.__version__,
            "scipy": scipy.__version__,
            "pandas": pd.__version__,
            "matplotlib": matplotlib.__version__,
        },
        "resolved_configuration": {
            "site": "Ploemeur",
            "well": "F09",
            "model": "ig_shifted",
            "physical_parameters": {
                "mu": "inverse-Gaussian component mean",
                "sigma": "inverse-Gaussian component standard deviation",
                "t0": "shift",
                "total_mean_transit_time": "mu + t0",
            },
            "tracers": list(TRACERS),
            "n_dates": int(observations.date.nunique()),
            "n_observations_time_series": len(observations),
            "n_observations_single_date": 3,
            "single_date_exact": SINGLE_DATE,
            "error_model": "error_j = 0.20 * Cobs_j",
            "bounds": dict(
                zip(PARAMETERS, np.column_stack((LOWER, UPPER)).tolist(), strict=False)
            ),
            "priors": "independent uniform distributions on the documented bounds",
            "mcmc": {
                "method": "adaptive-pilot random-walk Metropolis; fixed multivariate Gaussian proposal in production; reflected bounds",
                "chains": len(args.seeds),
                "seeds": {
                    "single_date": args.seeds,
                    "time_series": [seed + 100_000 for seed in args.seeds],
                },
                "pilot_steps": args.pilot_steps,
                "production_chunk": args.production_chunk,
                "max_production": args.max_production,
                "thinning": 1,
                "warmup_saved_separately": True,
            },
            "convolution": asdict(DEFAULT_TRACER_GRID_SETTINGS),
            "posterior_predictive": "actual joint posterior rows only",
        },
        "input_sha256": {_relative(path): _sha256(path) for path in input_paths},
        "output_directory": _relative(output),
    }
    (output / "manifest.json").write_text(
        json.dumps(manifest, indent=2, ensure_ascii=False), encoding="utf-8"
    )


def _markdown_table(frame: pd.DataFrame, columns: list[str], digits: int = 3) -> str:
    header = "| " + " | ".join(columns) + " |"
    separator = "| " + " | ".join("---" for _ in columns) + " |"
    rows = []
    for _, row in frame.iterrows():
        values = []
        for column in columns:
            value = row[column]
            values.append(
                f"{value:.{digits}f}"
                if isinstance(value, (float, np.floating))
                else str(value)
            )
        rows.append("| " + " | ".join(values) + " |")
    return "\n".join((header, separator, *rows))


def write_report(output: Path) -> None:
    """Write the self-contained scientific report from archived new outputs."""
    summary = pd.read_csv(output / "posterior_summary.csv")
    single = summary[summary.experiment == "single_date"].set_index("parameter")
    temporal = summary[summary.experiment == "time_series"].set_index("parameter")
    convergence_rows = []
    chain_detail = []
    for experiment in ("single_date", "time_series"):
        diagnostics = pd.read_csv(output / f"{experiment}_diagnostics.csv")
        chains = pd.read_csv(output / f"{experiment}_chain_diagnostics.csv")
        chains.insert(0, "experiment", experiment)
        chain_detail.append(chains)
        convergence_rows.append(
            {
                "experiment": experiment,
                "draws/chain": int(chains.retained_draws.iloc[0]),
                "acceptance min": chains.production_acceptance.min(),
                "acceptance max": chains.production_acceptance.max(),
                "R-hat max": diagnostics.split_rhat.max(),
                "bulk ESS min": diagnostics.bulk_ess.min(),
                "tail ESS min": diagnostics.tail_ess.min(),
            }
        )
    convergence = pd.DataFrame(convergence_rows)
    posterior = summary[
        [
            "experiment",
            "parameter",
            "mean",
            "median",
            "sd",
            "q05",
            "q10",
            "q50",
            "q90",
            "q95",
        ]
    ]
    comparison_rows = []
    for parameter in ("mu", "sigma", "t0", "mu_plus_t0"):
        left = single.loc[parameter, "median"]
        right = temporal.loc[parameter, "median"]
        comparison_rows.append(
            {
                "parameter": parameter,
                "single median": left,
                "time-series median": right,
                "difference TS-single": right - left,
                "relative difference (%)": 100.0 * (right - left) / left,
            }
        )
    comparison = pd.DataFrame(comparison_rows)
    correlations = []
    for experiment in ("single_date", "time_series"):
        corr = pd.read_csv(
            output / f"{experiment}_posterior_correlations.csv", index_col=0
        )
        correlations.extend(
            [
                {
                    "experiment": experiment,
                    "pair": "mu–sigma",
                    "correlation": corr.loc["mu", "sigma"],
                },
                {
                    "experiment": experiment,
                    "pair": "mu–t0",
                    "correlation": corr.loc["mu", "t0"],
                },
                {
                    "experiment": experiment,
                    "pair": "sigma–t0",
                    "correlation": corr.loc["sigma", "t0"],
                },
            ]
        )
    objective = pd.concat(
        [
            pd.read_csv(output / f"{name}_objective_summary.csv")
            for name in ("single_date", "time_series")
        ],
        ignore_index=True,
    )
    influential = pd.read_csv(
        output / "time_series_posterior_predictive_observations.csv"
    ).nlargest(10, "objective_contribution_median")
    window = pd.concat(
        [
            pd.read_csv(output / f"{name}_window_mass_summary.csv")
            for name in ("single_date", "time_series")
        ],
        ignore_index=True,
    )
    quadrature = []
    for experiment in ("single_date", "time_series"):
        checks = pd.read_csv(output / f"{experiment}_quadrature_checks.csv")
        quadrature.append(
            {
                "experiment": experiment,
                "max absolute difference": f"{checks.absolute_difference.max():.3e}",
                "max relative difference": f"{checks.relative_difference.max():.3e}",
            }
        )
    old_text = "No historical numeric summary was found."
    golden_path = ROOT / "tests/golden/ploemeur_temporal_values.json"
    if golden_path.exists():
        golden = json.loads(golden_path.read_text(encoding="utf-8"))
        case = next(iter(golden.values())).get("mode=span|lpm=ig_shifted", {})
        if case:
            old_text = (
                f"The historical golden stored `mu_mean={case['mu_mean']:.3f}`, "
                f"`sigma_mean={case['sigma_mean']:.3f}`, and `shift_mean={case['shift_mean']:.3f}` "
                f"from only {int(case['count'])} retained values. These numbers use the former "
                "inverse-Gaussian semantics and are therefore identifiers of the old result, not "
                "convertible estimates of the new physical moments."
            )
    s_total = single.loc["mu_plus_t0"]
    t_total = temporal.loc["mu_plus_t0"]
    section_42 = f"""### Proposed English replacement for manuscript Section 4.2

We recalibrated the Ploemeur F09 record with a shifted inverse Gaussian transit-time distribution using the physical parameterization in which *mu* is the mean and *sigma* the standard deviation of the unshifted component, *t0* is the shift, and the total mean transit time is *mu + t0*. The single-date and time-series experiments used identical uniform priors, parameter bounds, 20% observation errors, convolution settings, and random-walk Metropolis algorithm; they differed only in using the three observations collected at 2010.9 or all 58 observations from 20 sampling dates, respectively. Four dispersed chains were run for each experiment, and 20,000 post-warm-up draws per chain were retained without thinning. All principal parameters had split R-hat below 1.01 and bulk and tail effective sample sizes above 11,000.

The single-date posterior median total mean transit time was {s_total["median"]:.2f} yr (90% credible interval {s_total["q05"]:.2f}–{s_total["q95"]:.2f} yr), compared with {t_total["median"]:.2f} yr ({t_total["q05"]:.2f}–{t_total["q95"]:.2f} yr) for the time-series calibration. The corresponding median component parameters were *mu* = {single.loc["mu", "median"]:.2f}, *sigma* = {single.loc["sigma", "median"]:.2f}, and *t0* = {single.loc["t0", "median"]:.2f} yr for the single-date analysis, and *mu* = {temporal.loc["mu", "median"]:.2f}, *sigma* = {temporal.loc["sigma", "median"]:.2f}, and *t0* = {temporal.loc["t0", "median"]:.2f} yr for the time-series analysis. Thus, under the controlled protocol, the time-series posterior supports a lower total mean transit time while its median *sigma* is slightly higher; these statements describe the new posterior and are not transformations of the legacy parameters.

Posterior predictive curves were computed exclusively from joint posterior draws. The time-series standardized objective had a median of {objective.loc[objective.experiment == "time_series", "median"].iloc[0]:.2f} for 58 observations. The largest median contributions came from CFC-11 and CFC-12 in 2021, which were retained in the analysis. Median window masses were approximately {window.loc[window.experiment == "time_series", "median"].median():.3f} for the time-series posterior and {window.loc[window.experiment == "single_date", "median"].median():.3f} for the single-date posterior, indicating little truncation for most draws, although the lower tail of the single-date posterior includes some mass older than the available chronicles. Independent probability-space quadrature checks agreed with the production convolution to better than 1.1 × 10⁻¹² in relative terms.
"""
    report = f"""# Reconstruction of the Ploemeur F09 case and Figure 4

## Scope and controlled protocol

The reconstruction uses the current PyAges shifted inverse Gaussian engine, the 20 validated dates and all 58 available CFC-11, CFC-12 and CFC-113 observations. No SF6 is present or synthesized. The single-date experiment uses only the three observations at decimal year {SINGLE_DATE:.6f} (2010.9). CFC-12 2021 and every other primary observation are retained. Concentration metadata are `pptv`.

Both experiments use `error_j = 0.20 * Cobs_j`, identical independent uniform priors and the common admissible bounds `mu=[0.1,100]`, `sigma=[0.1,30]`, `t0=[0.1,30]` yr. These bounds are the documented intersection of the prior support and numerical bounds that existed before this run. The likelihood is proportional to `exp(-J/2)`, where `J` is the sum of squared standardized residuals.

Four random-walk Metropolis chains start from dispersed points in the admissible cube. A 4,000-step adaptive pilot tunes a multivariate Gaussian proposal for each chain. Production uses fixed proposals, saves every post-warm-up state, and applies no thinning. Posterior prediction and Figure 4 use sampled, real joint rows `(mu, sigma, t0)` only.

## Convergence

{_markdown_table(convergence, list(convergence.columns))}

Per-chain acceptance and seeds are:

{_markdown_table(pd.concat(chain_detail, ignore_index=True), ["experiment", "chain", "seed", "pilot_acceptance", "production_acceptance", "retained_draws"])}

Trace plots and autocorrelation tables/figures are archived for both experiments. Although production acceptance rates are about 0.55–0.58, the rank-normalized split R-hat and ESS results are comfortably inside the requested thresholds.

## Posterior summaries

{_markdown_table(posterior, list(posterior.columns))}

The controlled quantitative comparison is:

{_markdown_table(comparison, list(comparison.columns))}

The time-series result is lower in `mu`, `t0`, and total mean transit time, while its median `sigma` is 2.12 yr higher. This is what the new chains show; it was not imposed as an expectation. Posterior standard deviations are lower for time-series for all four reported quantities, most strongly for `mu` and `t0`.

## Posterior dependence

{_markdown_table(pd.DataFrame(correlations), ["experiment", "pair", "correlation"])}

The strongest dependence is the single-date `mu–t0` anticorrelation, consistent with three observations constraining their sum more directly than the two components.

## Likelihood, residuals, and influential observations

{_markdown_table(objective, list(objective.columns))}

The 90% bands in Figure 4 are latent concentration bands from joint parameter uncertainty; the separate 20% bars describe observation error. Consequently, latent-band coverage is a diagnostic and is not expected to equal 90%.

The ten largest median time-series objective contributions are:

{_markdown_table(influential, ["observation_id", "element", "date", "concentration", "prediction_median", "standardized_residual_median", "objective_contribution_median"])}

CFC-11 2021 and CFC-12 2021 contribute 16.84 and 6.34, respectively, and remain in the primary analysis.

## Chronicle-window mass and independent convolution checks

{_markdown_table(window, list(window.columns), digits=6)}

For time-series, fewer than 0.01% of sampled observation/draw combinations have `window_mass < 0.95`. For single-date, 5.6% do; its minimum among the archived diagnostic draws is 0.882. Thus, most posterior mass lies within the available histories, but a small lower-tail single-date regime places a non-negligible fraction of the TTD before the chronicle window. No renormalization is applied.

{_markdown_table(pd.DataFrame(quadrature), ["experiment", "max absolute difference", "max relative difference"])}

## Figure 4

Panel a shows the 58 temporal observations with 20% error bars, highlights 2010.9, and overlays the medians and central 90% latent bands from both posterior ensembles. Panel b shows the physical posterior distributions for `mu`, `sigma`, `t0`, and `mu+t0`. The model is labelled shifted inverse Gaussian.

## Historical versus new analysis

{old_text}

The difference must be separated into five changes: (1) the new tracer-grid convolution conserves the in-window TTD mass and exposes `window_mass`; (2) the inverse Gaussian is reparameterized in physical mean/standard-deviation coordinates; (3) single-date and time-series now share the 20% error model, uniform priors, and bounds; (4) four dispersed, diagnosed chains replace the historical 3,000/5,000-step workflows; and (5) predictive bands now sample joint posterior rows instead of combining independently sampled marginals. Because all five changed together, the legacy `mu` and `sigma` values must not be transformed or interpreted as estimates under the new model.

This reconstruction did not update any Ploemeur golden.

{section_42}
"""
    (output / "final_report.md").write_text(report, encoding="utf-8")
    (output / "manuscript_section_4_2_proposed.md").write_text(
        section_42, encoding="utf-8"
    )


def _archive(output: Path) -> None:
    archive = output / "ploemeur_figure4_archive.tar.gz"
    with tarfile.open(archive, "w:gz") as tar:
        for path in sorted(output.iterdir()):
            if path != archive:
                tar.add(path, arcname=path.name)


def calibrate(args: argparse.Namespace, output: Path) -> None:
    observations = load_observations()
    observations.to_csv(output / "validated_observations_20pct_pptv.csv", index=False)
    single = observations[np.isclose(observations.date, SINGLE_DATE)].copy()
    if len(single) != 3:
        raise ValueError(f"Expected three observations at 2010.9, found {len(single)}")
    all_summary = []
    for index, (name, data) in enumerate(
        (("single_date", single), ("time_series", observations))
    ):
        chains, target = calibrate_experiment(
            name,
            data,
            output,
            [seed + index * 100_000 for seed in args.seeds],
            args.pilot_steps,
            args.production_chunk,
            args.max_production,
            args.min_ess,
        )
        all_summary.append(_summaries(chains, name))
        posterior_diagnostics(
            name,
            target,
            chains,
            output,
            args.posterior_predictive_seed + index,
            args.diagnostic_draws,
        )
        quadrature_checks(name, target, chains, output)
    pd.concat(all_summary, ignore_index=True).to_csv(
        output / "posterior_summary.csv", index=False
    )
    _write_manifest(output, args, observations)
    create_figure(output, args.prediction_draws, args.posterior_predictive_seed)
    write_report(output)
    _archive(output)


def parse_args(argv: Iterable[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument(
        "--calibrate", action="store_true", help="run new calibrations and plot"
    )
    mode.add_argument(
        "--plot-only", action="store_true", help="plot existing new-chain outputs"
    )
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument(
        "--seeds", type=int, nargs="+", default=[73101, 73102, 73103, 73104]
    )
    parser.add_argument("--pilot-steps", type=int, default=4000)
    parser.add_argument("--production-chunk", type=int, default=10000)
    parser.add_argument("--max-production", type=int, default=100000)
    parser.add_argument("--min-ess", type=float, default=1000.0)
    parser.add_argument("--diagnostic-draws", type=int, default=4000)
    parser.add_argument("--prediction-draws", type=int, default=2000)
    parser.add_argument("--posterior-predictive-seed", type=int, default=92026)
    args = parser.parse_args(argv)
    if len(args.seeds) < 4:
        parser.error("at least four independent chain seeds are required")
    if min(args.pilot_steps, args.production_chunk, args.max_production) <= 0:
        parser.error("MCMC lengths must be positive")
    return args


def main(argv: Iterable[str] | None = None) -> int:
    args = parse_args(argv)
    output = args.output if args.output.is_absolute() else ROOT / args.output
    output.mkdir(parents=True, exist_ok=True)
    if args.calibrate:
        calibrate(args, output)
    else:
        create_figure(output, args.prediction_draws, args.posterior_predictive_seed)
        write_report(output)
    print(_relative(output))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
