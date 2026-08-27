# Copyright (c) 2021-2026 Centre national de la recherche scientifique (CNRS)
# Contributor: Jean-Raynald de Dreuzy
# SPDX-License-Identifier: CECILL-2.1

"""Final 19-case shifted-exponential article production.

The qualified proposal is fixed here: a 4,000-step legacy pilot followed by
an empirical (mu, t0) covariance, relative ridge 1e-6, and a fixed Gaussian
random walk scaled by 2.38/sqrt(2).  This driver refuses Ploemeur paths.
"""

# The repository root must be added before importing the local package.
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
from concurrent.futures import ProcessPoolExecutor, as_completed
from pathlib import Path
from typing import Any

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import scipy

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from pyages.calibration.methods.metropolis_hastings import MetropolisHastings, MHConfig
from pyages.calibration.mh_proposals import regularize_empirical_covariance
from pyages.calibration.problem import CalibrationProblem
from pyages.config.runtime import DisplayOptions
from pyages.convolution import ConvolutionTracers
from pyages.lpm import build_lpm
from pyages.tools.figures_additional import cmap_white_jet
from scripts.common.mcmc_diagnostics import mcse_mean
from scripts.common.provenance import repository_provenance
from scripts.common.publication_plotting import (
    PUBLICATION_RC,
    mm_to_in,
    save_pdf_png,
)

OUTPUT = ROOT / "results" / "final_article_simulations" / "shifted_exponential"
TRACERS = ("cfc11", "cfc12", "cfc113", "sf6")
DATE = 2010.0
RELATIVE_ERROR = 0.08
BURN_IN = 0.20
PILOT_STEPS = 4_000
PRODUCTION_STEPS = 10_000
EXTENDED_STEPS = 20_000
RIDGE = 1.0e-6
PROPOSAL_MULTIPLIER = 2.38 / math.sqrt(2.0)
MAX_ACF_LAG = 1_000
NCHAINS = 5
CASES = tuple(
    (index, 1.0 if mu == 0 else float(mu), 1.0 if shift == 0 else float(shift))
    for index, (mu, shift) in enumerate(
        (
            (mu, shift)
            for mu in range(0, 50, 10)
            for shift in range(0, 50, 10)
            if mu + shift <= 50
        ),
        start=1,
    )
)


def _guard_output(path: Path) -> Path:
    resolved = path.resolve()
    if "ploemeur" in str(resolved).lower():
        raise ValueError("The shifted-exponential campaign refuses Ploemeur paths")
    resolved.mkdir(parents=True, exist_ok=True)
    return resolved


def _path_label(path: Path, base: Path = ROOT) -> str:
    try:
        return path.resolve().relative_to(base.resolve()).as_posix()
    except ValueError:
        return path.resolve().as_posix()


def _seed(case_index: int, chain: int) -> int:
    return 420_000 + 100 * case_index + chain


def _pilot_seed(case_index: int) -> int:
    return 410_000 + case_index


def _display(path: Path) -> DisplayOptions:
    display = DisplayOptions()
    display.text = False
    display.figure = False
    display.figure_save = False
    display.figure_close = True
    display.directory = path
    return display


def _model(mu: float, t0: float):
    model = build_lpm("exp_shifted", directory_lpm=str(ROOT / "data_core" / "data_lpm"))
    model.p.update({"mu": float(mu), "shift": float(t0)})
    return model


def _observations(mu: float, t0: float):
    tracers = ConvolutionTracers(names=list(TRACERS), date=DATE)
    observations = tracers.convolve(_model(mu, t0), return_type="concentrations")
    observations.error_affect_from_value(RELATIVE_ERROR)
    return observations


def _run_chain(
    mu: float,
    t0: float,
    seed: int,
    steps: int,
    output: Path,
    covariance: np.ndarray | None,
) -> tuple[pd.DataFrame, float, float]:
    observations = _observations(mu, t0)
    problem = CalibrationProblem(
        observations,
        "exp_shifted",
        display_options=_display(output),
        sample_count=10_000,
        explore_objective=False,
        explore_reachable=False,
    ).prepare()
    kwargs: dict[str, Any] = {"componentwise_source": "model"}
    if covariance is not None:
        kwargs = {
            "proposal_kind": "correlated",
            "proposal_multiplier": PROPOSAL_MULTIPLIER,
            "proposal_covariance": tuple(
                tuple(float(v) for v in row) for row in covariance
            ),
        }
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
    started = time.perf_counter()
    posterior = mh.run(problem)
    runtime = time.perf_counter() - started
    frame = posterior.frame.copy()
    frame["t0"] = frame["shift"]
    frame["mtt"] = frame["mu"] + frame["t0"]
    spec: dict[str, Any] = {}
    mh.write_results_spec(spec)
    return frame, float(spec["success_rate"]), runtime


def _pilot_path(output: Path, case_index: int) -> Path:
    return output / "pilots" / f"case_{case_index:02d}_pilot.npz"


def _covariance_path(output: Path, case_index: int) -> Path:
    return output / "pilots" / f"case_{case_index:02d}_covariance.npy"


def _chain_path(output: Path, case_index: int, chain: int, steps: int) -> Path:
    return output / "chains" / f"case_{case_index:02d}_chain_{chain + 1}_n{steps}.npz"


def run_pilots(output: Path) -> dict[int, np.ndarray]:
    _guard_output(output / "pilots")
    covariances: dict[int, np.ndarray] = {}
    for case_index, mu, t0 in CASES:
        covariance_path = _covariance_path(output, case_index)
        if covariance_path.exists():
            covariances[case_index] = np.load(covariance_path)
            continue
        frame, acceptance, runtime = _run_chain(
            mu, t0, _pilot_seed(case_index), PILOT_STEPS, output / "pilots", None
        )
        values = frame[["mu", "t0"]].to_numpy(float)
        covariance = regularize_empirical_covariance(values, RIDGE)
        np.save(covariance_path, covariance)
        np.savez_compressed(
            _pilot_path(output, case_index),
            mu=frame["mu"].to_numpy(float),
            t0=frame["t0"].to_numpy(float),
            mtt=frame["mtt"].to_numpy(float),
            objective=frame["obj_function"].to_numpy(float),
            acceptance=acceptance,
            runtime=runtime,
            seed=_pilot_seed(case_index),
        )
        covariances[case_index] = covariance
        print(f"pilot {case_index}/19", flush=True)
    return covariances


def _production_job(job: tuple[Any, ...]) -> str:
    output_text, case_index, mu, t0, chain, steps, covariance = job
    output = Path(output_text)
    path = _chain_path(output, case_index, chain, steps)
    if path.exists():
        return str(path)
    frame, acceptance, runtime = _run_chain(
        mu, t0, _seed(case_index, chain), steps, output / "chains", covariance
    )
    np.savez_compressed(
        path,
        mu=frame["mu"].to_numpy(float),
        t0=frame["t0"].to_numpy(float),
        mtt=frame["mtt"].to_numpy(float),
        objective=frame["obj_function"].to_numpy(float),
        acceptance=acceptance,
        runtime=runtime,
        seed=_seed(case_index, chain),
        steps=steps,
    )
    return str(path)


def run_production(
    output: Path,
    workers: int,
    steps: int,
    case_indices: set[int] | None = None,
) -> None:
    _guard_output(output / "chains")
    covariances = run_pilots(output)
    jobs = []
    for case_index, mu, t0 in CASES:
        if case_indices is not None and case_index not in case_indices:
            continue
        for chain in range(NCHAINS):
            path = _chain_path(output, case_index, chain, steps)
            if not path.exists():
                jobs.append(
                    (
                        str(output),
                        case_index,
                        mu,
                        t0,
                        chain,
                        steps,
                        covariances[case_index],
                    )
                )
    if not jobs:
        return
    with ProcessPoolExecutor(max_workers=max(1, workers)) as executor:
        futures = [executor.submit(_production_job, job) for job in jobs]
        for done, future in enumerate(as_completed(futures), start=1):
            future.result()
            print(f"production {done}/{len(futures)} (n={steps})", flush=True)


def _load(path: Path) -> dict[str, Any]:
    with np.load(path) as data:
        return {key: data[key].copy() for key in data.files}


def _acf(values: np.ndarray, max_lag: int = MAX_ACF_LAG) -> np.ndarray:
    values = np.asarray(values, dtype=float)
    centered = values - values.mean()
    n = len(values)
    denominator = float(np.dot(centered, centered))
    if n < 2 or denominator == 0.0:
        return np.ones(1)
    fft_size = 1 << (2 * n - 1).bit_length()
    spectrum = np.fft.rfft(centered, n=fft_size)
    covariance = np.fft.irfft(spectrum * np.conjugate(spectrum), n=fft_size)[:n]
    covariance /= np.arange(n, 0, -1)
    result = covariance / covariance[0]
    return result[: min(max_lag, n - 1) + 1]


def _iact_ess(values: np.ndarray) -> tuple[np.ndarray, float, float]:
    acf = _acf(values)
    pairs = []
    for start in range(1, len(acf) - 1, 2):
        value = float(acf[start] + acf[start + 1])
        if value <= 0.0:
            break
        pairs.append(value)
    tau = 1.0
    if pairs:
        tau = max(1.0, 1.0 + 2.0 * float(np.minimum.accumulate(pairs).sum()))
    return acf, tau, min(float(len(values)), float(len(values)) / tau)


def _split_rhat(chains: list[np.ndarray]) -> float:
    length = min(len(chain) for chain in chains)
    half = length // 2
    split = np.asarray(
        [part for chain in chains for part in (chain[:half], chain[length - half :])],
        dtype=float,
    )
    within = float(np.mean(np.var(split, axis=1, ddof=1)))
    if within == 0.0:
        return 1.0
    between = half * float(np.var(np.mean(split, axis=1), ddof=1))
    variance = (half - 1.0) / half * within + between / half
    return float(math.sqrt(variance / within))


def _summary(values: np.ndarray) -> dict[str, float]:
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
    }


def collect_diagnostics(
    output: Path, lengths: dict[int, int]
) -> dict[str, pd.DataFrame]:
    summary_rows: list[dict[str, Any]] = []
    convergence_rows: list[dict[str, Any]] = []
    run_rows: list[dict[str, Any]] = []
    acf_rows: list[dict[str, Any]] = []
    for case_index, target_mu, target_t0 in CASES:
        steps = lengths[case_index]
        loaded = [
            _load(_chain_path(output, case_index, chain, steps))
            for chain in range(NCHAINS)
        ]
        for chain, data in enumerate(loaded):
            run_rows.append(
                {
                    "case": case_index,
                    "target_mu": target_mu,
                    "target_t0": target_t0,
                    "chain": chain + 1,
                    "seed": int(data["seed"]),
                    "steps": steps,
                    "stored_samples": len(data["mu"]),
                    "acceptance_rate": float(data["acceptance"]),
                    "runtime_seconds": float(data["runtime"]),
                    "best_sqrt_J_data_over_m": float(np.min(data["objective"])),
                    "chain_file": _path_label(
                        _chain_path(output, case_index, chain, steps), output
                    ),
                }
            )
        local: list[dict[str, Any]] = []
        for parameter, target in (
            ("mu", target_mu),
            ("t0", target_t0),
            ("mtt", target_mu + target_t0),
        ):
            chains = [np.asarray(data[parameter], dtype=float) for data in loaded]
            rh = _split_rhat(chains)
            ess_values = []
            iact_values = []
            for chain, values in enumerate(chains):
                acf, iact, ess = _iact_ess(values)
                ess_values.append(ess)
                iact_values.append(iact)
                acf_rows.extend(
                    {
                        "case": case_index,
                        "chain": chain + 1,
                        "parameter": parameter,
                        "lag": lag,
                        "acf": float(value),
                    }
                    for lag, value in enumerate(acf)
                )
            pooled = np.concatenate(chains)
            total_ess = float(sum(ess_values))
            mean_mcse = mcse_mean(pooled, total_ess)
            converged = bool(rh < 1.01 and total_ess >= 300.0)
            local.append(
                {
                    "parameter": parameter,
                    "target": target,
                    "pooled": pooled,
                    "rhat": rh,
                    "ess": total_ess,
                    "mcse_mean": mean_mcse,
                    "iact": float(max(iact_values)),
                    "acf1": float(np.median([_acf(values)[1] for values in chains])),
                    "converged": converged,
                }
            )
            convergence_rows.append(
                {
                    "case": case_index,
                    "parameter": parameter,
                    "steps_per_chain": steps,
                    "split_rhat": rh,
                    "ess_sum_chains": total_ess,
                    "mcse_mean": mean_mcse,
                    "iact_max_chain": float(max(iact_values)),
                    "converged": converged,
                }
            )
        case_converged = all(item["converged"] for item in local)
        for item in local:
            pooled = item["pooled"]
            pooled_summary = (
                _summary(pooled)
                if case_converged
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
                    "case": case_index,
                    "target_mu": target_mu,
                    "target_t0": target_t0,
                    "target_mtt": target_mu + target_t0,
                    "parameter": item["parameter"],
                    "target": item["target"],
                    "steps_per_chain": steps,
                    "chains": NCHAINS,
                    "pooled_samples": len(pooled) if case_converged else 0,
                    "case_converged": case_converged,
                    **pooled_summary,
                    "acf1_median_chain": item["acf1"],
                    "iact_max_chain": item["iact"],
                    "ess_sum_chains": item["ess"],
                    "mcse_mean": item["mcse_mean"] if case_converged else np.nan,
                    "split_rhat": item["rhat"],
                }
            )
    return {
        "summaries": pd.DataFrame(summary_rows),
        "convergence": pd.DataFrame(convergence_rows),
        "runs": pd.DataFrame(run_rows),
        "acf": pd.DataFrame(acf_rows),
    }


def _markdown(frame: pd.DataFrame) -> str:
    values = frame.copy().round(5).replace({np.nan: ""})
    columns = [str(column) for column in values.columns]
    lines = [
        "| " + " | ".join(columns) + " |",
        "| " + " | ".join("---" for _ in columns) + " |",
    ]
    lines.extend(
        "| " + " | ".join(str(value).replace("|", "\\|") for value in row) + " |"
        for row in values.itertuples(index=False, name=None)
    )
    return "\n".join(lines)


def _table4(
    output: Path, tables: dict[str, pd.DataFrame], lengths: dict[int, int]
) -> pd.DataFrame:
    summaries = tables["summaries"]
    runs = tables["runs"]
    rows = []
    for case_index, target_mu, target_t0 in CASES:
        observations = _observations(target_mu, target_t0)
        row: dict[str, Any] = {
            "case": case_index,
            "target_mu": target_mu,
            "target_t0": target_t0,
            "target_mtt": target_mu + target_t0,
            "relative_error": RELATIVE_ERROR,
            "steps_per_chain": lengths[case_index],
            "chains": NCHAINS,
        }
        for tracer, concentration in zip(
            TRACERS,
            observations.cv["concentration"].to_numpy(float),
            strict=True,
        ):
            row[f"C_{tracer}"] = concentration
        subset = summaries.loc[summaries["case"] == case_index].set_index("parameter")
        for parameter in ("mu", "t0", "mtt"):
            for statistic in (
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
                row[f"posterior_{parameter}_{statistic}"] = float(
                    subset.loc[parameter, statistic]
                )
            row[f"{parameter}_ess"] = float(subset.loc[parameter, "ess_sum_chains"])
            row[f"{parameter}_split_rhat"] = float(subset.loc[parameter, "split_rhat"])
        row["best_sqrt_J_data_over_m"] = float(
            runs.loc[runs["case"] == case_index, "best_sqrt_J_data_over_m"].min()
        )
        rows.append(row)
    table = pd.DataFrame(rows)
    table.to_csv(output / "table4_final.csv", index=False)
    (output / "table4_final.md").write_text(
        "# Table 4 — shifted exponential\n\n"
        "Production corrélée finale; `MTT = mu + t0`.\n\n" + _markdown(table),
        encoding="utf-8",
        newline="\n",
    )
    return table


def _render_figure2(
    surface: pd.DataFrame,
    posterior: pd.DataFrame,
    output: Path,
) -> None:
    """Render all requested physical-width variants from canonical data."""

    for width_mm in (120, 110, 100):
        with plt.rc_context(PUBLICATION_RC):
            fig, axis = plt.subplots(
                figsize=(mm_to_in(width_mm), mm_to_in(width_mm * 0.76)),
                layout="constrained",
            )
            colour = axis.pcolormesh(
                surface.columns.to_numpy(float),
                surface.index.to_numpy(float),
                surface.to_numpy(float),
                shading="auto",
                cmap=cmap_white_jet(),
                rasterized=True,
            )
            bar = fig.colorbar(colour, ax=axis, pad=0.025)
            bar.set_label(r"Normalized RMS data misfit, $\sqrt{J/4}$")
            axis.scatter(
                posterior["mu"],
                posterior["t0"],
                s=7,
                facecolors="white",
                edgecolors="black",
                linewidths=0.25,
                alpha=0.52,
                label="Posterior samples",
            )
            axis.scatter(
                [10.0],
                [30.0],
                marker="*",
                s=105,
                facecolors="white",
                edgecolors="black",
                linewidths=1.1,
                label="Generating target",
            )
            axis.set(
                xlabel=r"Exponential timescale, $\mu$ (yr)",
                ylabel=r"Shift, $t_0$ (yr)",
                xlim=(0, 50),
                ylim=(0, 50),
            )
            axis.legend(loc="upper right", framealpha=0.92)
            save_pdf_png(
                fig,
                output,
                f"figure2_shifted_exponential_{width_mm}mm",
            )
            if width_mm == 110:
                save_pdf_png(fig, output, "figure2_shifted_exponential_final")
                fig.savefig(
                    output / "figure2_shifted_exponential_final.tiff",
                    dpi=600,
                    facecolor="white",
                    bbox_inches=None,
                    pil_kwargs={"compression": "tiff_lzw"},
                )
            plt.close(fig)


def _figure2(output: Path, lengths: dict[int, int]) -> None:
    case_index = next(index for index, mu, t0 in CASES if mu == 10.0 and t0 == 30.0)
    steps = lengths[case_index]
    samples = []
    for chain in range(NCHAINS):
        data = _load(_chain_path(output, case_index, chain, steps))
        stride = max(1, len(data["mu"]) // 500)
        samples.append(
            pd.DataFrame({"mu": data["mu"][::stride], "t0": data["t0"][::stride]})
        )
    posterior = pd.concat(samples, ignore_index=True)
    observations = _observations(10.0, 30.0)
    problem = CalibrationProblem(
        observations,
        "exp_shifted",
        display_options=_display(output),
        sample_count=10_000,
        explore_objective=True,
        explore_reachable=False,
    ).prepare()
    sampling = problem.sampling
    sampling.compute_concentrations()
    sampling.objective_function_build()
    grid = sampling.objective_function_frame().rename(
        columns={"half_log_chi_square": "half_log_J"}
    )
    grid["sqrt_J_data_over_4"] = np.sqrt(
        np.exp(2.0 * grid["half_log_J"].to_numpy(float)) / 4.0
    )
    figure_grid = grid[["mu", "shift", "sqrt_J_data_over_4"]].copy()
    figure_grid.to_csv(
        output / "figure2_objective_grid_sqrt_J_data_over_4.csv", index=False
    )
    surface = (
        figure_grid.pivot(index="shift", columns="mu", values="sqrt_J_data_over_4")
        .sort_index()
        .sort_index(axis=1)
    )
    _render_figure2(surface, posterior, output)
    posterior.to_csv(output / "figure2_final_chain_samples.csv", index=False)


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _manifest(output: Path, lengths: dict[int, int]) -> None:
    sources = (
        Path(__file__).resolve(),
        ROOT / "pyages" / "calibration" / "mh_proposals.py",
        ROOT / "pyages" / "calibration" / "methods" / "metropolis_hastings.py",
        ROOT / "pyages" / "convolution" / "convolution.py",
        ROOT / "pyages" / "lpm" / "models" / "exponential_shifted.py",
        ROOT / "data_core" / "data_lpm" / "exp_shifted" / "params.yaml",
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
            "cases": CASES,
            "tracers": TRACERS,
            "date": DATE,
            "relative_error": RELATIVE_ERROR,
            "synthetic_noise_added": False,
            "bounds": {"mu": [0.1, 70.0], "t0": [0.0, 70.0]},
            "pilot_steps": PILOT_STEPS,
            "burn_in": BURN_IN,
            "ridge": RIDGE,
            "proposal_scale": "2.38/sqrt(2)",
            "chains": NCHAINS,
            "seed_rule": "pilot=410000+case; production=420000+100*case+zero_based_chain",
            "final_steps_by_case": lengths,
            "thinning_for_diagnostics": 1,
        },
        "source_sha256": {_path_label(path): _sha256(path) for path in sources},
        "artifact_sha256": {
            _path_label(path, output): _sha256(path) for path in artifacts
        },
    }
    (output / "manifest.json").write_text(
        json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
    )


def analyze_and_extend(output: Path, workers: int) -> dict[str, pd.DataFrame]:
    lengths = {case_index: PRODUCTION_STEPS for case_index, _, _ in CASES}
    initial = collect_diagnostics(output, lengths)
    failing = set(
        initial["convergence"]
        .loc[
            (initial["convergence"]["ess_sum_chains"] < 300.0)
            | (initial["convergence"]["split_rhat"] >= 1.01),
            "case",
        ]
        .astype(int)
    )
    if failing:
        print(f"targeted extension cases: {sorted(failing)}", flush=True)
        run_production(output, workers, EXTENDED_STEPS, failing)
        lengths.update({case_index: EXTENDED_STEPS for case_index in failing})
    tables = collect_diagnostics(output, lengths)
    tables["summaries"].to_csv(output / "posterior_summaries.csv", index=False)
    tables["convergence"].to_csv(output / "convergence_diagnostics.csv", index=False)
    tables["runs"].to_csv(output / "chain_diagnostics.csv", index=False)
    tables["acf"].to_csv(
        output / "autocorrelation_functions.csv.gz", index=False, compression="gzip"
    )
    _table4(output, tables, lengths)
    if bool(tables["convergence"]["converged"].all()):
        _figure2(output, lengths)
    else:
        print(
            "Figure 2 withheld: at least one final chain group did not converge",
            flush=True,
        )
    report_table = (
        tables["convergence"]
        .groupby("case", as_index=False)
        .agg(
            max_split_rhat=("split_rhat", "max"),
            min_ess=("ess_sum_chains", "min"),
            steps_per_chain=("steps_per_chain", "max"),
            converged=("converged", "all"),
        )
    )
    (output / "shifted_exponential_final.md").write_text(
        "# Production finale shifted-exponential\n\n"
        + _markdown(report_table)
        + "\n\nLes chaînes ne sont poolées dans Table 4 que si tous les diagnostics finaux du cas satisfont split-Rhat < 1.01 et ESS ≥ 300.\n",
        encoding="utf-8",
        newline="\n",
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
    parser.add_argument("--workers", type=int, default=1)
    parser.add_argument("--case-min", type=int, default=1)
    parser.add_argument("--case-max", type=int, default=len(CASES))
    args = parser.parse_args(argv)
    if not (1 <= args.case_min <= args.case_max <= len(CASES)):
        parser.error(f"case range must satisfy 1 <= min <= max <= {len(CASES)}")
    selected_cases = set(range(args.case_min, args.case_max + 1))
    output = _guard_output(args.output)
    if args.phase in {"pilot", "all"}:
        run_pilots(output)
    if args.phase in {"production", "all"}:
        run_production(output, args.workers, PRODUCTION_STEPS, selected_cases)
    if args.phase in {"analyze", "all"}:
        analyze_and_extend(output, args.workers)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
