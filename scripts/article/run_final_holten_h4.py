# Copyright (c) 2021-2026 Centre national de la recherche scientifique (CNRS)
# Contributor: Jean-Raynald de Dreuzy
# SPDX-License-Identifier: CECILL-2.1

"""Final five-chain Holten H4 production with a fixed pilot covariance."""

# The repository root must be added before importing local example modules.
# ruff: noqa: E402

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

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from examples.natural.holten.holten_four_bin import BIN_ORDER, load_paper_4bin_fractions
from examples.natural.holten.holten_prepare import prepare_holten_inputs
from examples.natural.holten.holten_reproduction import (
    TRACERS_4,
    ForwardConvention,
    _fractions,
    _matrix,
    _objective,
    build_observations,
    build_reproduction_endmembers,
    optimize_well,
)
from pyages.calibration.methods.mh.proposals import regularize_empirical_covariance
from scripts.article.run_final_shifted_exponential import (
    _iact_ess,
    _markdown,
    _split_rhat,
    _summary,
)
from scripts.common.mcmc_diagnostics import mcse_mean
from scripts.common.provenance import repository_provenance
from scripts.common.publication_plotting import (
    PUBLICATION_RC,
    mm_to_in,
    save_pdf_png,
)

OUTPUT = ROOT / "results" / "final_article_simulations" / "holten_h4_final"
CONVENTION = ForwardConvention("two_year_shift_and_decay", 2.0, True, 310.0)
PILOT_STEPS = 4_000
PRODUCTION_STEPS = 10_000
EXTENDED_STEPS = 20_000
BURN_IN = 0.20
RIDGE = 1.0e-6
DIMENSION = 3
PROPOSAL_MULTIPLIER = 2.38 / math.sqrt(DIMENSION)
NCHAINS = 5
MAX_ACF_LAG = 1_000
Z_BOUNDS = (-8.0, 8.0)
# Numerical rescue for two weakly identified latent directions.  Each value is
# the probability of proposing an independent Uniform[-8, 8] refresh for z1
# and, separately, for z2.  The remaining probability uses the qualified fixed
# correlated random walk.  All components are symmetric, so no Hastings term
# is required.  Distinct filenames preserve the initially diagnosed chains.
REFRESH_PROBABILITY = {"73-29": 0.20, "85-34": 0.10}


def _guard_output(path: Path) -> Path:
    resolved = path.resolve()
    if "ploemeur" in str(resolved).lower():
        raise ValueError("The Holten campaign refuses Ploemeur paths")
    resolved.mkdir(parents=True, exist_ok=True)
    return resolved


def _path_label(path: Path, base: Path = ROOT) -> str:
    try:
        return path.resolve().relative_to(base.resolve()).as_posix()
    except ValueError:
        return path.resolve().as_posix()


def _pilot_seed(well_index: int) -> int:
    return 510_000 + well_index


def _seed(well_index: int, chain: int) -> int:
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
    current = np.clip(np.asarray(initial, dtype=float), Z_BOUNDS[0], Z_BOUNDS[1])
    current_objective = _objective(matrix, values, errors, current)
    accepted = 0
    burn_count = int(steps * BURN_IN)
    count = steps - burn_count
    z_samples = np.empty((count, DIMENSION), dtype=float)
    fraction_samples = np.empty((count, len(BIN_ORDER)), dtype=float)
    objective_samples = np.empty(count, dtype=float)
    if covariance is None:
        covariance = np.eye(DIMENSION) * 0.18**2
    else:
        covariance = np.asarray(covariance, dtype=float) * PROPOSAL_MULTIPLIER**2
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
                    np.zeros(DIMENSION), covariance
                )
        else:
            proposal = current + rng.multivariate_normal(
                np.zeros(DIMENSION), covariance
            )
        in_bounds = bool(np.all((proposal >= Z_BOUNDS[0]) & (proposal <= Z_BOUNDS[1])))
        proposal_objective = (
            _objective(matrix, values, errors, proposal) if in_bounds else math.inf
        )
        if in_bounds and np.log(rng.random()) < min(
            0.0, -0.5 * (proposal_objective - current_objective)
        ):
            current = proposal
            current_objective = proposal_objective
            accepted += 1
        if step >= burn_count:
            z_samples[stored] = current
            fraction_samples[stored] = _fractions(current)
            objective_samples[stored] = current_objective
            stored += 1
    return {
        "z": z_samples,
        "fractions": fraction_samples,
        "objective": objective_samples,
        "acceptance": accepted / steps,
        "runtime": time.perf_counter() - started,
        "seed": seed,
        "steps": steps,
    }


def _pilot_path(output: Path, well: str) -> Path:
    return output / "pilots" / f"{well}_pilot.npz"


def _covariance_path(output: Path, well: str) -> Path:
    return output / "pilots" / f"{well}_covariance.npy"


def _chain_path(output: Path, well: str, chain: int, steps: int) -> Path:
    rescue = well in REFRESH_PROBABILITY and steps == EXTENDED_STEPS
    suffix = "_symmetric_refresh" if rescue else ""
    return output / "chains" / f"{well}_chain_{chain + 1}_n{steps}{suffix}.npz"


def _save(path: Path, data: dict[str, Any]) -> None:
    np.savez_compressed(path, **data)


def _load(path: Path) -> dict[str, Any]:
    with np.load(path) as data:
        return {key: data[key].copy() for key in data.files}


def _scientific_inputs():
    prepared = prepare_holten_inputs()
    endmembers = build_reproduction_endmembers(prepared, CONVENTION)
    return prepared, endmembers


def run_pilots(output: Path) -> dict[str, np.ndarray]:
    _guard_output(output / "pilots")
    prepared, endmembers = _scientific_inputs()
    covariances: dict[str, np.ndarray] = {}
    for well_index, well in enumerate(prepared.context.selected_wells, start=1):
        covariance_path = _covariance_path(output, well)
        if covariance_path.exists():
            covariances[well] = np.load(covariance_path)
            continue
        observations = build_observations(prepared, well, True)
        optimum = optimize_well(observations, endmembers)
        pilot = _sample(
            optimum["matrix"],
            optimum["values"],
            optimum["errors"],
            optimum["z"],
            _pilot_seed(well_index),
            PILOT_STEPS,
            None,
        )
        covariance = regularize_empirical_covariance(pilot["z"], RIDGE)
        _save(_pilot_path(output, well), pilot)
        np.save(covariance_path, covariance)
        covariances[well] = covariance
        print(f"Holten pilot {well_index}/7: {well}", flush=True)
    return covariances


def run_production(
    output: Path,
    steps: int,
    selected_wells: set[str] | None = None,
) -> None:
    _guard_output(output / "chains")
    covariances = run_pilots(output)
    prepared, endmembers = _scientific_inputs()
    jobs = 0
    for well_index, well in enumerate(prepared.context.selected_wells, start=1):
        if selected_wells is not None and well not in selected_wells:
            continue
        observations = build_observations(prepared, well, True)
        optimum = optimize_well(observations, endmembers)
        for chain in range(NCHAINS):
            path = _chain_path(output, well, chain, steps)
            if path.exists():
                continue
            data = _sample(
                optimum["matrix"],
                optimum["values"],
                optimum["errors"],
                optimum["z"],
                _seed(well_index, chain),
                steps,
                covariances[well],
                REFRESH_PROBABILITY.get(well, 0.0) if steps == EXTENDED_STEPS else 0.0,
            )
            _save(path, data)
            jobs += 1
            print(
                f"Holten production {well} chain {chain + 1}/5 (n={steps})", flush=True
            )
    if not jobs:
        print(
            f"Holten production n={steps}: all requested chains already present",
            flush=True,
        )


def _series(data: dict[str, Any], parameter: str) -> np.ndarray:
    if parameter.startswith("z"):
        return np.asarray(data["z"][:, int(parameter[1:])], dtype=float)
    if parameter in BIN_ORDER:
        return np.asarray(data["fractions"][:, BIN_ORDER.index(parameter)], dtype=float)
    if parameter == "objective":
        return np.asarray(data["objective"], dtype=float)
    raise KeyError(parameter)


def collect_diagnostics(
    output: Path, lengths: dict[str, int]
) -> dict[str, pd.DataFrame]:
    prepared, _ = _scientific_inputs()
    parameters = ("z0", "z1", "z2", *BIN_ORDER)
    summary_rows: list[dict[str, Any]] = []
    convergence_rows: list[dict[str, Any]] = []
    run_rows: list[dict[str, Any]] = []
    acf_rows: list[dict[str, Any]] = []
    for well in prepared.context.selected_wells:
        steps = lengths[well]
        loaded = [
            _load(_chain_path(output, well, chain, steps)) for chain in range(NCHAINS)
        ]
        for chain, data in enumerate(loaded):
            run_rows.append(
                {
                    "well": well,
                    "chain": chain + 1,
                    "seed": int(data["seed"]),
                    "steps": steps,
                    "stored_samples": len(data["objective"]),
                    "acceptance_rate": float(data["acceptance"]),
                    "runtime_seconds": float(data["runtime"]),
                    "best_objective": float(np.min(data["objective"])),
                    "chain_file": _path_label(
                        _chain_path(output, well, chain, steps), output
                    ),
                }
            )
        local_diagnostics: list[dict[str, Any]] = []
        local_chains: dict[str, list[np.ndarray]] = {}
        for parameter in parameters:
            chains = [_series(data, parameter) for data in loaded]
            local_chains[parameter] = chains
            pooled = np.concatenate(chains)
            rhat = _split_rhat(chains)
            ess_values = []
            iact_values = []
            for chain, values in enumerate(chains):
                acf, iact, ess = _iact_ess(values)
                ess_values.append(ess)
                iact_values.append(iact)
                acf_rows.extend(
                    {
                        "well": well,
                        "chain": chain + 1,
                        "parameter": parameter,
                        "lag": lag,
                        "acf": float(value),
                    }
                    for lag, value in enumerate(acf[: MAX_ACF_LAG + 1])
                )
            total_ess = float(sum(ess_values))
            local_diagnostics.append(
                {
                    "well": well,
                    "parameter": parameter,
                    "space": "latent_z"
                    if parameter.startswith("z")
                    else "physical_fraction",
                    "steps_per_chain": steps,
                    "split_rhat": rhat,
                    "ess_sum_chains": total_ess,
                    "mcse_mean": mcse_mean(pooled, total_ess),
                    "iact_max_chain": float(max(iact_values)),
                    "converged": bool(rhat < 1.01 and total_ess >= 300.0),
                }
            )
        well_converged = all(row["converged"] for row in local_diagnostics)
        convergence_rows.extend(local_diagnostics)
        for parameter in (*parameters, "objective"):
            chains = local_chains.get(parameter) or [
                _series(data, parameter) for data in loaded
            ]
            values = np.concatenate(chains)
            diagnostic = next(
                (row for row in local_diagnostics if row["parameter"] == parameter),
                None,
            )
            if diagnostic is None:
                objective_ess = float(sum(_iact_ess(chain)[2] for chain in chains))
                mean_mcse = mcse_mean(values, objective_ess)
            else:
                objective_ess = diagnostic["ess_sum_chains"]
                mean_mcse = diagnostic["mcse_mean"]
            stats = (
                _summary(values)
                if well_converged
                else {
                    name: np.nan
                    for name in (
                        "mean",
                        "median",
                        "sd",
                        "q025",
                        "q10",
                        "q25",
                        "q75",
                        "q90",
                        "q975",
                    )
                }
            )
            summary_rows.append(
                {
                    "well": well,
                    "parameter": parameter,
                    "space": "latent_z"
                    if parameter.startswith("z")
                    else (
                        "physical_fraction" if parameter in BIN_ORDER else "objective"
                    ),
                    "steps_per_chain": steps,
                    "chains": NCHAINS,
                    "pooled_samples": len(values) if well_converged else 0,
                    "well_converged": well_converged,
                    "ess_sum_chains": objective_ess,
                    "mcse_mean": mean_mcse if well_converged else np.nan,
                    **stats,
                }
            )
    return {
        "summaries": pd.DataFrame(summary_rows),
        "convergence": pd.DataFrame(convergence_rows),
        "runs": pd.DataFrame(run_rows),
        "acf": pd.DataFrame(acf_rows),
    }


def _posterior_predictions(
    output: Path,
    lengths: dict[str, int],
    convergence: pd.DataFrame,
) -> pd.DataFrame:
    prepared, endmembers = _scientific_inputs()
    rows: list[dict[str, Any]] = []
    for well in prepared.context.selected_wells:
        converged = bool(
            convergence.loc[convergence["well"] == well, "converged"].all()
        )
        if not converged:
            continue
        observations = build_observations(prepared, well, True)
        elements = observations["element"]
        if elements.isna().any():
            raise RuntimeError(f"Missing tracer name in observations for {well}")
        tracer_names = elements.map(str).tolist()
        matrix = _matrix(endmembers, tracer_names)
        fractions = np.concatenate(
            [
                _load(_chain_path(output, well, chain, lengths[well]))["fractions"]
                for chain in range(NCHAINS)
            ],
            axis=0,
        )
        modeled = fractions @ matrix.T
        observed = observations["concentration"].to_numpy(float)
        errors = observations["error"].to_numpy(float)
        median_modeled = np.median(modeled, axis=0)
        standardized = (observed - median_modeled) / errors
        total = float(np.sum(standardized**2))
        for index, tracer in enumerate(tracer_names):
            rows.append(
                {
                    "well": well,
                    "tracer": tracer,
                    "observed": observed[index],
                    "uncertainty": errors[index],
                    "modeled_mean": float(np.mean(modeled[:, index])),
                    "modeled_median": float(median_modeled[index]),
                    "modeled_q10": float(np.quantile(modeled[:, index], 0.10)),
                    "modeled_q90": float(np.quantile(modeled[:, index], 0.90)),
                    "residual_observed_minus_modeled_median": float(
                        observed[index] - median_modeled[index]
                    ),
                    "standardized_residual": float(standardized[index]),
                    "objective_contribution": float(standardized[index] ** 2),
                    "objective_from_median_predictions": total,
                }
            )
    return pd.DataFrame(rows)


def _comparison(
    summaries: pd.DataFrame,
    output: Path,
) -> tuple[pd.DataFrame, pd.DataFrame]:
    prepared, _ = _scientific_inputs()
    paper = load_paper_4bin_fractions(prepared).set_index("well_id")
    rows = []
    for well in prepared.context.selected_wells:
        local = summaries.loc[
            (summaries["well"] == well) & (summaries["parameter"].isin(BIN_ORDER))
        ].set_index("parameter")
        for fraction in BIN_ORDER:
            rows.append(
                {
                    "well": well,
                    "fraction": fraction,
                    "visser": float(paper.loc[well, fraction]),
                    "pyages_mean": float(local.loc[fraction, "mean"]),
                    "pyages_median": float(local.loc[fraction, "median"]),
                    "pyages_sd": float(local.loc[fraction, "sd"]),
                    "pyages_q025": float(local.loc[fraction, "q025"]),
                    "pyages_q10": float(local.loc[fraction, "q10"]),
                    "pyages_q90": float(local.loc[fraction, "q90"]),
                    "pyages_q975": float(local.loc[fraction, "q975"]),
                }
            )
    comparison = pd.DataFrame(rows)
    errors = np.abs(comparison["pyages_median"] - comparison["visser"])
    valid_errors = errors.dropna()
    metrics = pd.DataFrame(
        [
            {
                "n_fractions": len(errors),
                "n_valid_fractions": len(valid_errors),
                "mae": float(valid_errors.mean()),
                "median_absolute_error": float(valid_errors.median()),
                "rmse": float(np.sqrt(np.mean(valid_errors**2))),
                "maximum_absolute_error": float(valid_errors.max()),
                "n_error_le_0p02": int((valid_errors <= 0.02).sum()),
                "n_error_le_0p05": int((valid_errors <= 0.05).sum()),
                "n_error_le_0p10": int((valid_errors <= 0.10).sum()),
            }
        ]
    )
    comparison.to_csv(output / "visser_vs_pyages_h4.csv", index=False)
    metrics.to_csv(output / "visser_vs_pyages_h4_metrics.csv", index=False)
    return comparison, metrics


def _draw_figure3(
    comparison: pd.DataFrame,
    *,
    layout: tuple[int, int],
) -> tuple[plt.Figure, np.ndarray]:
    """Draw one publication layout of the canonical Holten comparison."""

    wells = comparison["well"].drop_duplicates().tolist()
    tab10 = plt.get_cmap("tab10").colors
    pyages_color = tab10[0]
    visser_color = tab10[1]
    rows, columns = layout
    height_mm = 78 if layout == (1, 4) else 118
    fig, axes = plt.subplots(
        rows,
        columns,
        figsize=(mm_to_in(165), mm_to_in(height_mm)),
        sharey=True,
        squeeze=False,
    )
    flat_axes = axes.ravel()
    y = np.arange(len(wells))
    panel_titles = ("(a) 0–20 yr", "(b) 20–40 yr", "(c) 40–60 yr", "(d) >60 yr")
    for panel_index, (axis, fraction, title) in enumerate(
        zip(flat_axes, BIN_ORDER, panel_titles, strict=True)
    ):
        values = (
            comparison.loc[comparison["fraction"] == fraction]
            .set_index("well")
            .loc[wells]
        )
        for row, well in enumerate(wells):
            pyages_y = row + 0.08
            visser_y = row - 0.08
            pyages_median = values.loc[well, "pyages_median"]
            axis.errorbar(
                pyages_median,
                pyages_y,
                xerr=[
                    [pyages_median - values.loc[well, "pyages_q10"]],
                    [values.loc[well, "pyages_q90"] - pyages_median],
                ],
                fmt="o",
                color=pyages_color,
                ecolor=pyages_color,
                markersize=4.2,
                elinewidth=1.3,
                capsize=2.2,
                capthick=1.0,
                zorder=3,
                label=(
                    "PyAges posterior median and 10–90 % credible interval"
                    if row == 0
                    else None
                ),
            )
            axis.scatter(
                values.loc[well, "visser"],
                visser_y,
                facecolors="none",
                edgecolors=visser_color,
                linewidths=1.3,
                s=31,
                marker="D",
                zorder=4,
                label="Visser et al. (2013)" if row == 0 else None,
            )
        axis.set_title(title, fontweight="bold", fontsize=9.0)
        axis.set_xlim(-0.025, 1.025)
        axis.set_xticks((0.0, 0.5, 1.0) if layout == (1, 4) else np.linspace(0, 1, 5))
        if layout == (1, 4):
            axis.xaxis.set_major_formatter(FormatStrFormatter("%g"))
        axis.grid(alpha=0.22)
        if panel_index != 0:
            axis.tick_params(axis="y", labelleft=False)
    flat_axes[0].set_yticks(y, wells)
    flat_axes[0].invert_yaxis()
    handles, labels = flat_axes[0].get_legend_handles_labels()
    handles_by_label = dict(zip(labels, handles, strict=False))
    legend_labels = (
        "PyAges posterior median and 10–90 % credible interval",
        "Visser et al. (2013)",
    )
    fig.supxlabel("Age fraction", x=0.55 if layout == (1, 4) else 0.52, y=0.19)
    fig.legend(
        [handles_by_label[label] for label in legend_labels],
        legend_labels,
        loc="lower center",
        bbox_to_anchor=(0.5, 0.015),
        ncol=1,
        frameon=False,
    )
    if layout == (1, 4):
        fig.subplots_adjust(left=0.10, right=0.99, top=0.84, bottom=0.29, wspace=0.18)
    else:
        fig.subplots_adjust(
            left=0.10, right=0.99, top=0.92, bottom=0.20, wspace=0.10, hspace=0.30
        )
    return fig, flat_axes


def _figure3(comparison: pd.DataFrame, output: Path) -> None:
    """Export the preferred 1 × 4 layout and a 2 × 2 fallback."""

    with plt.rc_context(PUBLICATION_RC):
        final, _ = _draw_figure3(comparison, layout=(1, 4))
        save_pdf_png(final, output, "figure3_holten_final")
        plt.close(final)

        alternative, _ = _draw_figure3(comparison, layout=(2, 2))
        save_pdf_png(alternative, output, "figure3_holten_alt_2x2")
        plt.close(alternative)


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _manifest(output: Path, lengths: dict[str, int]) -> None:
    prepared, _ = _scientific_inputs()
    sources = (
        Path(__file__).resolve(),
        ROOT / "examples" / "natural" / "holten" / "holten_reproduction.py",
        ROOT / "examples" / "natural" / "holten" / "holten_prepare.py",
        ROOT / "examples" / "natural" / "holten" / "holten_four_bin.py",
        ROOT / "pyages" / "calibration" / "mh_proposals.py",
    )
    inputs = (
        prepared.context.paths.sampling_raw_path,
        prepared.context.paths.tritium_raw_path,
        prepared.context.paths.kr85_raw_path,
        prepared.context.paths.reference_results_path,
        prepared.context.paths.doc_dir / "visser_shape_free_models.csv",
    )
    artifacts = [
        path
        for path in output.rglob("*")
        if path.is_file() and path.name != "manifest.json"
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
            "latent_z_bounds": list(Z_BOUNDS),
            "latent_prior": "uniform within canonical shapefree_n_oldbin z bounds",
            "tritium_half_life_years": 12.32,
            "helium_sigma_TU": {"reported_six_wells": 0.5, "59-05_imputed": 0.5},
            "pilot_steps": PILOT_STEPS,
            "burn_in": BURN_IN,
            "ridge": RIDGE,
            "proposal_scale": "2.38/sqrt(3)",
            "numerical_rescue": {
                well: {
                    "steps": EXTENDED_STEPS,
                    "symmetric_uniform_refresh_probability_per_coordinate": probability,
                    "coordinates": ["z1", "z2"],
                    "reason": "short pilot covariance remained trapped in one near-zero-fraction regime",
                }
                for well, probability in REFRESH_PROBABILITY.items()
            },
            "chains": NCHAINS,
            "seed_rule": "pilot=510000+one_based_well; production=520000+100*one_based_well+zero_based_chain",
            "final_steps_by_well": lengths,
            "thinning_for_diagnostics": 1,
        },
        "source_sha256": {_path_label(path): _sha256(path) for path in sources},
        "input_sha256": {_path_label(path): _sha256(path) for path in inputs},
        "artifact_sha256": {
            _path_label(path, output): _sha256(path) for path in artifacts
        },
    }
    (output / "manifest.json").write_text(
        json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
    )


def analyze_and_extend(output: Path) -> dict[str, pd.DataFrame]:
    prepared, _ = _scientific_inputs()
    lengths = {well: PRODUCTION_STEPS for well in prepared.context.selected_wells}
    initial = collect_diagnostics(output, lengths)
    failing = set(
        initial["convergence"].loc[~initial["convergence"]["converged"], "well"]
    )
    if failing:
        print(f"Holten targeted extension: {sorted(failing)}", flush=True)
        run_production(output, EXTENDED_STEPS, failing)
        lengths.update({well: EXTENDED_STEPS for well in failing})
    tables = collect_diagnostics(output, lengths)
    tables["summaries"].to_csv(output / "posterior_summaries.csv", index=False)
    tables["convergence"].to_csv(output / "convergence_diagnostics.csv", index=False)
    tables["runs"].to_csv(output / "chain_diagnostics.csv", index=False)
    tables["acf"].to_csv(
        output / "autocorrelation_functions.csv.gz", index=False, compression="gzip"
    )
    predictions = _posterior_predictions(output, lengths, tables["convergence"])
    predictions.to_csv(output / "posterior_modeled_concentrations.csv", index=False)
    comparison, metrics = _comparison(tables["summaries"], output)
    if bool(tables["convergence"]["converged"].all()):
        _figure3(comparison, output)
    summary = (
        tables["convergence"]
        .groupby("well", as_index=False)
        .agg(
            max_split_rhat=("split_rhat", "max"),
            min_ess=("ess_sum_chains", "min"),
            steps_per_chain=("steps_per_chain", "max"),
            converged=("converged", "all"),
        )
    )
    report = (
        "# Holten H4 final multi-chain\n\n"
        "Observables : ³H, ³He tritiogénique corrigé, ⁸⁵Kr et ³⁹Ar. "
        "Le sigma de ³He vaut 0,5 TU pour les six valeurs publiées et 0,5 TU imputé pour 59-05. "
        "Aucune correction gaz noble supplémentaire n'est appliquée. Les latents `z` utilisent les bornes "
        "canoniques `[-8, 8]` de `shapefree_n_oldbin`; elles rendent propre le posterior qui dérivait dans "
        "les directions correspondant aux fractions nulles. Le scale corrélé reste `2.38/sqrt(3)`. "
        "Après l'échec diagnostique à 20 000 pas du proposal pur, 73-29 et 85-34 utilisent en plus "
        "un mélange MH symétrique documenté : rafraîchissement uniforme de `z1` ou `z2` avec une "
        "probabilité respective de 20 % et 10 % par coordonnée. Les chaînes initiales restent "
        "conservées sans remplacement.\n\n"
        "## Convergence\n\n" + _markdown(summary) + "\n\n"
        "## Comparaison aux fractions de Visser\n\n" + _markdown(metrics) + "\n"
    )
    (output / "holten_h4_final_multichain.md").write_text(
        report, encoding="utf-8", newline="\n"
    )
    _manifest(output, lengths)
    return tables


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "phase",
        choices=("pilot", "production", "analyze", "all"),
        default="all",
        nargs="?",
    )
    parser.add_argument("--output", type=Path, default=OUTPUT)
    args = parser.parse_args(argv)
    output = _guard_output(args.output)
    if args.phase in {"pilot", "all"}:
        run_pilots(output)
    if args.phase in {"production", "all"}:
        run_production(output, PRODUCTION_STEPS)
    if args.phase in {"analyze", "all"}:
        analyze_and_extend(output)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
