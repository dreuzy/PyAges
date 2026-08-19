# -*- coding: utf-8 -*-
"""Reproduce the shifted-exponential synthetic validation shown in Figure 2.

This launcher is intentionally limited to the manuscript Figure 2 case.  It
uses the current PyAge scientific kernels, but makes the historically implicit
choices explicit:

* shifted exponential target: ``mu=10 years``, ``shift=30 years``;
* sampling date: 2010;
* tracers: CFC-11, CFC-12, CFC-113, and SF6;
* tracer uncertainty: ``sigma_j = 0.08 * C_target,j``;
* Metropolis-Hastings: 10000 steps, no parameter prior, seed 12345;
* objective-function grid: nominal resolution 10000 (10201 cells);
* plot coordinates: ``x=mu`` and ``y=t0``;
* colour: ``sqrt(J_data/m)`` with four normalized tracer residuals;
* publication outputs: hybrid-vector PDF, LZW TIFF, and PNG at 600 dpi.

The historical workflow assigned uncertainties to exact synthetic
concentrations; it did not perturb those concentrations with an additional
random draw.  This script preserves that behaviour.
"""

from __future__ import annotations

import argparse
import json
import math
from dataclasses import asdict, dataclass
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

from pyage.calibration.methods.metropolis_hastings import MetropolisHastings, MHConfig
from pyage.calibration.utils.calibration_core import CalibrationCore
from pyage.config.paths import ROOT_DIRECTORY_RESULTS
from pyage.config.runtime import DisplayOptions
from pyage.convolution.convolution_tracers import ConvolutionTracers
from pyage.lpm.lpm_build import lpm_build
from pyage.tools.figures_additional import cmap_white_jet


@dataclass(frozen=True)
class Figure2Config:
    """Numerical definition of the manuscript Figure 2 experiment."""

    target_mu: float = 10.0
    target_shift: float = 30.0
    sample_date: float = 2010.0
    relative_error: float = 0.08
    mh_steps: int = 10000
    mh_skip: int = 5
    mh_seed: int = 12345
    grid_resolution: int = 10000
    axis_min: float = 0.0
    axis_max: float = 50.0
    max_mh_points: int = 2000
    point_size: float = 13.0
    output_dpi: int = 600


TRACERS = ("cfc11", "cfc12", "cfc113", "sf6")
LPM_NAME = "exp_shifted"


def _validate_config(config: Figure2Config) -> None:
    if config.target_mu <= 0:
        raise ValueError("target_mu must be positive")
    if config.target_shift < 0:
        raise ValueError("target_shift must be non-negative")
    if not 0 < config.relative_error < 1:
        raise ValueError("relative_error must be between 0 and 1")
    if config.mh_steps <= 0:
        raise ValueError("mh_steps must be positive")
    if config.mh_skip <= 0:
        raise ValueError("mh_skip must be positive")
    if config.grid_resolution <= 0:
        raise ValueError("grid_resolution must be positive")
    if config.axis_max <= config.axis_min:
        raise ValueError("axis_max must be greater than axis_min")
    if config.output_dpi < 300:
        raise ValueError("output_dpi must be at least 300 for publication output")


def build_target(config: Figure2Config):
    """Build the target without relying on positional parameter ordering."""

    target = lpm_build(LPM_NAME)
    parameter_names = list(target.p.keys())
    if parameter_names != ["mu", "shift"]:
        raise RuntimeError(
            "Unexpected shifted-exponential parameter order: "
            f"{parameter_names}; expected ['mu', 'shift']."
        )

    target.p["mu"] = float(config.target_mu)
    target.p["shift"] = float(config.target_shift)
    return target


def build_synthetic_data(config: Figure2Config, target):
    """Convolve the four tracers and attach the historical 8% uncertainties."""

    tracers = ConvolutionTracers(names=list(TRACERS), date=config.sample_date)
    observations = tracers.convolve(
        target,
        return_type="concentrations",
    )
    observations.error_affect_from_value(config.relative_error)
    return observations


def run_metropolis_hastings(
    config: Figure2Config,
    observations,
    output_directory: Path,
):
    """Calibrate the shifted exponential with the manuscript MH settings."""

    display = DisplayOptions()
    display.text = False
    display.figure = False
    display.figure_save = False
    display.figure_close = True
    display.directory = output_directory

    calibration = CalibrationCore(
        observations,
        LPM_NAME,
        display_options=display,
        nmodels=config.grid_resolution,
        objfunc=True,
        reachconc=False,
    )
    calibration.prepare()

    mh = MetropolisHastings(
        config=MHConfig(
            nstep=config.mh_steps,
            nskip=config.mh_skip,
            prior_option=False,
            likelihood=True,
            monitor=False,
            display_traj=False,
            display_text=False,
            seed=config.mh_seed,
        )
    )
    mh.MH_step.define_by_value()
    mh.update_calibbasis(calibration)
    posterior = mh.perform()
    return mh, posterior


def build_objective_grid(calibration: MetropolisHastings) -> pd.DataFrame:
    """Evaluate ``sqrt(J_data / m)`` on the model grid."""

    calibration.compute_concentrations()
    calibration.objective_function_build()
    grid = calibration.objective_function_frame()
    grid = grid.rename(columns={"log-ojf": "half_log_J"})
    grid["J"] = np.exp(2.0 * grid["half_log_J"].to_numpy(dtype=float))
    grid["m"] = len(TRACERS)
    grid["rms_normalized_data_misfit"] = np.sqrt(
        grid["J"].to_numpy(dtype=float) / grid["m"].to_numpy(dtype=float)
    )
    return grid


def _surface_from_grid(grid: pd.DataFrame) -> pd.DataFrame:
    """Return Z(shift, mu) for the declared ``x=mu, y=shift`` axes."""

    required = {"mu", "shift", "rms_normalized_data_misfit"}
    missing = required.difference(grid.columns)
    if missing:
        raise ValueError(f"Objective grid is missing columns: {sorted(missing)}")
    return (
        grid.pivot(
            index="shift",
            columns="mu",
            values="rms_normalized_data_misfit",
        )
        .sort_index(axis=0)
        .sort_index(axis=1)
    )


def plot_figure2(
    config: Figure2Config,
    grid: pd.DataFrame,
    posterior_frame: pd.DataFrame,
    output_directory: Path,
) -> tuple[Path, Path, Path]:
    """Plot the objective map, MH samples, and the explicit target marker."""

    surface = _surface_from_grid(grid)
    mu_values = surface.columns.to_numpy(dtype=float)
    shift_values = surface.index.to_numpy(dtype=float)

    fig, ax = plt.subplots(figsize=(7.2, 5.4), constrained_layout=True)
    colour = ax.pcolormesh(
        mu_values,
        shift_values,
        surface.to_numpy(dtype=float),
        shading="auto",
        cmap=cmap_white_jet(),
        rasterized=True,
    )
    colorbar = fig.colorbar(colour, ax=ax)
    colorbar.set_label(r"RMS normalized data misfit, $\sqrt{J_{data}/m}$", fontsize=13)
    colorbar.ax.tick_params(labelsize=12, width=0.9)

    chain = posterior_frame.iloc[1 : config.max_mh_points + 1]
    ax.scatter(
        chain["mu"],
        chain["shift"],
        facecolors="white",
        edgecolors="black",
        linewidths=0.35,
        s=config.point_size,
        marker="o",
        alpha=0.82,
        label="Metropolis–Hastings",
        zorder=3,
    )
    ax.scatter(
        [config.target_mu],
        [config.target_shift],
        c="white",
        edgecolors="black",
        linewidths=1.5,
        s=165,
        marker="*",
        label="Target",
        zorder=4,
    )

    ax.set_xlabel(r"Exponential timescale, $\mu$ (years)", fontsize=15, labelpad=7)
    ax.set_ylabel("Shift, $t_0$ (years)", fontsize=15, labelpad=7)
    ax.tick_params(axis="both", labelsize=12, width=0.9)
    ax.set_xlim(config.axis_min, config.axis_max)
    ax.set_ylim(config.axis_min, config.axis_max)
    ax.legend(
        loc="upper right",
        fontsize=12,
        markerscale=1.25,
        framealpha=0.92,
    )

    png_path = output_directory / "figure2_shifted_exponential.png"
    pdf_path = output_directory / "figure2_shifted_exponential.pdf"
    tiff_path = output_directory / "figure2_shifted_exponential.tiff"
    save_options = {
        "bbox_inches": "tight",
        "facecolor": "white",
    }
    fig.savefig(png_path, dpi=config.output_dpi, **save_options)
    fig.savefig(pdf_path, dpi=config.output_dpi, **save_options)
    fig.savefig(
        tiff_path,
        dpi=config.output_dpi,
        pil_kwargs={"compression": "tiff_lzw"},
        **save_options,
    )
    plt.close(fig)
    return png_path, pdf_path, tiff_path


def build_residual_table(
    observations,
    posterior,
) -> tuple[pd.DataFrame, dict[str, float]]:
    """Report individual residuals and recompute J for the best MH row."""

    posterior_frame = posterior.dist()
    best = posterior.best_row()
    if best is None:
        raise RuntimeError("Metropolis-Hastings returned no posterior samples")

    concentration_columns = posterior.get_concentration_names()
    if len(concentration_columns) != len(observations.cv):
        raise RuntimeError("Posterior concentration columns do not match observations")

    observed = observations.cv["concentration"].to_numpy(dtype=float)
    sigma = observations.cv["error"].to_numpy(dtype=float)
    modelled = best[concentration_columns].to_numpy(dtype=float)
    residual = modelled - observed
    normalized = residual / sigma
    squared_normalized = np.square(normalized)
    j_value = float(np.sum(squared_normalized))
    m_value = int(len(observed))
    rms_normalized = float(math.sqrt(j_value / m_value))

    table = pd.DataFrame(
        {
            "tracer": observations.cv["element"].astype(str).to_numpy(),
            "observed": observed,
            "sigma": sigma,
            "modelled_best_mh": modelled,
            "residual_model_minus_observed": residual,
            "normalized_residual": normalized,
            "squared_normalized_residual": squared_normalized,
        }
    )
    summary = {
        "J_best_mh": j_value,
        "m": m_value,
        "sqrt_J_over_m_best_mh": rms_normalized,
        "stored_obj_function_best_mh": float(best["obj_function"]),
        "best_mu": float(best["mu"]),
        "best_shift": float(best["shift"]),
        "posterior_rows": int(len(posterior_frame)),
    }
    return table, summary


def write_outputs(
    config: Figure2Config,
    output_directory: Path,
    observations,
    posterior,
    grid: pd.DataFrame,
) -> tuple[Path, Path]:
    """Write data needed to audit or redraw the figure independently."""

    posterior_frame = posterior.dist().copy()
    residuals, best_summary = build_residual_table(observations, posterior)
    objective_values = posterior_frame["obj_function"].astype(float)

    posterior_path = output_directory / "figure2_mh_samples.csv"
    grid_path = output_directory / "figure2_objective_grid.csv"
    residual_path = output_directory / "figure2_best_fit_residuals.csv"
    metadata_path = output_directory / "figure2_manifest.json"

    posterior_frame.to_csv(posterior_path, index=False)
    grid.to_csv(grid_path, index=False)
    residuals.to_csv(residual_path, index=False)

    metadata = {
        "experiment": "manuscript_figure2_shifted_exponential",
        "global_run_manifest": "../run_manifest.yaml",
        "historical_launcher": {
            "commit": "5ef068e32394c225ebd0499fe775ae45fa1f0d19",
            "path": "sources/test_specific_article.py",
        },
        "config": asdict(config),
        "tracers": list(TRACERS),
        "lpm": LPM_NAME,
        "target_parameter_assignment": {
            "mu": config.target_mu,
            "shift": config.target_shift,
            "scipy_scale": config.target_mu,
            "scipy_loc": config.target_shift,
        },
        "synthetic_noise_added": False,
        "uncertainty_formula": "sigma_j = relative_error * C_observed_j",
        "objective_formula": "J = sum_j (((C_model_j - C_observed_j) / sigma_j) ** 2)",
        "stored_mh_objective_formula": "sqrt(J / m)",
        "colour_formula": "sqrt(J_data / m), with m = 4",
        "plot_coordinates": {"x": "mu", "y": "shift"},
        "target_plot_coordinate": [config.target_mu, config.target_shift],
        "objective_grid_rows": int(len(grid)),
        "best_mh": best_summary,
        "posterior_sqrt_J_over_m": {
            "count": int(objective_values.count()),
            "minimum": float(objective_values.min()),
            "median": float(objective_values.median()),
            "mean": float(objective_values.mean()),
            "standard_deviation": float(objective_values.std()),
            "maximum": float(objective_values.max()),
        },
    }
    metadata_path.write_text(
        json.dumps(metadata, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    return residual_path, metadata_path


def reproduce(config: Figure2Config, output_directory: Path) -> dict[str, Path]:
    """Run the complete Figure 2 reproduction workflow."""

    _validate_config(config)
    output_directory.mkdir(parents=True, exist_ok=True)

    target = build_target(config)
    observations = build_synthetic_data(config, target)
    calibration, posterior = run_metropolis_hastings(
        config,
        observations,
        output_directory,
    )
    grid = build_objective_grid(calibration)
    posterior_frame = posterior.dist()
    png_path, pdf_path, tiff_path = plot_figure2(
        config,
        grid,
        posterior_frame,
        output_directory,
    )
    residual_path, metadata_path = write_outputs(
        config,
        output_directory,
        observations,
        posterior,
        grid,
    )
    return {
        "png": png_path,
        "pdf": pdf_path,
        "tiff": tiff_path,
        "residuals": residual_path,
        "metadata": metadata_path,
    }


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Reproduce the manuscript Figure 2 shifted-exponential case."
    )
    parser.add_argument(
        "--output-directory",
        type=Path,
        default=ROOT_DIRECTORY_RESULTS / "manuscript_figure2",
        help="Directory receiving the figure and audit tables.",
    )
    parser.add_argument(
        "--mh-steps",
        type=int,
        default=Figure2Config.mh_steps,
        help="Override 10000 only for development or convergence checks.",
    )
    parser.add_argument(
        "--mh-skip",
        type=int,
        default=Figure2Config.mh_skip,
        help="Store one posterior state every N MH steps (default: 5).",
    )
    parser.add_argument(
        "--grid-resolution",
        type=int,
        default=Figure2Config.grid_resolution,
        help="Override 10000 only for development or convergence checks.",
    )
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    config = Figure2Config(
        mh_steps=args.mh_steps,
        mh_skip=args.mh_skip,
        grid_resolution=args.grid_resolution,
    )
    outputs = reproduce(config, args.output_directory.resolve())
    print("Figure 2 reproduction completed:")
    for name, path in outputs.items():
        print(f"  {name}: {path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
