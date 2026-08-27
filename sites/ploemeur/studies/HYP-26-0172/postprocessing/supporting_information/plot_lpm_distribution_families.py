# Copyright (c) 2021-2026 Centre national de la recherche scientifique (CNRS)
# Contributor: Jean-Raynald de Dreuzy
# SPDX-License-Identifier: CECILL-2.1

"""Plot comparable shifted-exponential and shifted-inverse-Gaussian TTDs."""

from __future__ import annotations

import csv
from dataclasses import dataclass
from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np
from scipy.integrate import quad

from pyages.lpm.models.exponential_shifted import ExponentialShiftedLpm
from pyages.lpm.models.inverse_gaussian_shifted import InverseGaussianShiftedLpm

REPOSITORY_ROOT = Path(__file__).resolve().parents[6]
OUTPUT_DIRECTORY = (
    REPOSITORY_ROOT / "results" / "HYP-26-0172" / "figures" / "supporting_information"
)
LPM_PARAMETER_DIRECTORY = REPOSITORY_ROOT / "sites" / "ploemeur" / "params_lpm"
PLOT_T_MAX = 300.0
PLOT_POINTS = 5000
XLIM = (0.0, 160.0)


@dataclass(frozen=True)
class CurveParameters:
    number: int
    shift: float
    mu: float
    shape_lambda: float


# Deliberately diverse illustrative cases; these are not calibration results.
CURVES = (
    CurveParameters(1, shift=0.0, mu=15.0, shape_lambda=10.0),
    CurveParameters(2, shift=0.0, mu=40.0, shape_lambda=40.0),
    CurveParameters(3, shift=5.0, mu=25.0, shape_lambda=60.0),
    CurveParameters(4, shift=10.0, mu=20.0, shape_lambda=10.0),
    CurveParameters(5, shift=10.0, mu=50.0, shape_lambda=100.0),
    CurveParameters(6, shift=20.0, mu=20.0, shape_lambda=20.0),
)

# Match the restrained article/SI style used by the other Ploemeur plots.
plt.rcParams.update(
    {
        "font.family": "sans-serif",
        "font.size": 8.4,
        "axes.labelsize": 9.1,
        "axes.titlesize": 9.8,
        "axes.linewidth": 1.0,
        "xtick.labelsize": 7.7,
        "ytick.labelsize": 7.7,
        "legend.fontsize": 5.6,
    }
)


def build_models(parameters: CurveParameters):
    """Return both LPMs for one numbered physical parameter set."""
    exponential = ExponentialShiftedLpm(
        mu=parameters.mu,
        shift=parameters.shift,
        directory_lpm=LPM_PARAMETER_DIRECTORY,
    )

    # PyAges exposes the physical mean and standard deviation.  In the common
    # IG(mean, lambda) parameterization, variance = mean**3 / lambda.
    sigma_physical = np.sqrt(parameters.mu**3 / parameters.shape_lambda)
    inverse_gaussian = InverseGaussianShiftedLpm(
        mu=parameters.mu,
        sigma=sigma_physical,
        shift=parameters.shift,
        directory_lpm=LPM_PARAMETER_DIRECTORY,
    )
    return exponential, inverse_gaussian


def numerical_moments(model, shift: float) -> tuple[float, float, float]:
    """Numerically integrate mass, mean, and variance on the full support."""

    def pdf(value: float) -> float:
        return float(model.pdf(value))

    integral = quad(pdf, shift, np.inf, epsabs=1e-11, epsrel=1e-11, limit=500)[0]
    mean = (
        quad(
            lambda value: value * pdf(value),
            shift,
            np.inf,
            epsabs=1e-10,
            epsrel=1e-10,
            limit=500,
        )[0]
        / integral
    )
    variance = (
        quad(
            lambda value: (value - mean) ** 2 * pdf(value),
            shift,
            np.inf,
            epsabs=1e-9,
            epsrel=1e-9,
            limit=500,
        )[0]
        / integral
    )
    return integral, mean, variance


def validate_and_write_tables() -> list[dict[str, float | str]]:
    """Run required checks and save reproducible parameter/control tables."""
    OUTPUT_DIRECTORY.mkdir(parents=True, exist_ok=True)
    parameter_rows = []
    control_rows: list[dict[str, float | str]] = []

    for parameters in CURVES:
        exponential, inverse_gaussian = build_models(parameters)
        expected_mean = parameters.shift + parameters.mu
        for name, model, lambda_value in (
            ("shifted exponential", exponential, "not applicable"),
            ("shifted inverse Gaussian", inverse_gaussian, parameters.shape_lambda),
        ):
            probe = np.linspace(parameters.shift, PLOT_T_MAX, PLOT_POINTS)
            density = np.asarray(model.pdf(probe), dtype=float)
            if not np.all(np.isfinite(density)) or np.any(density < 0.0):
                raise ValueError(
                    f"Invalid density values for curve {parameters.number}"
                )
            integral, mean, variance = numerical_moments(model, parameters.shift)
            if abs(integral - 1.0) >= 1e-3 or abs(mean - expected_mean) >= 0.1:
                raise ValueError(f"Moment check failed for curve {parameters.number}")
            q1, median, q3 = (
                float(value) for value in model.cdf_inv([0.25, 0.5, 0.75])
            )
            control_rows.append(
                {
                    "curve_number": parameters.number,
                    "model": name,
                    "shift": parameters.shift,
                    "mu": parameters.mu,
                    "lambda": lambda_value,
                    "integral": integral,
                    "mean": mean,
                    "variance": variance,
                    "q1": q1,
                    "median": median,
                    "q3": q3,
                    "interquartile_range": q3 - q1,
                }
            )
            parameter_rows.append(
                {
                    "curve_number": parameters.number,
                    "model": name,
                    "mean_total": expected_mean,
                    "shift": parameters.shift,
                    "mu": parameters.mu,
                    "lambda": lambda_value,
                }
            )

    for filename, rows, fields in (
        (
            "LPM_distribution_families_parameters.csv",
            parameter_rows,
            ["curve_number", "model", "mean_total", "shift", "mu", "lambda"],
        ),
        (
            "LPM_distribution_families_numerical_checks.csv",
            control_rows,
            [
                "curve_number",
                "model",
                "shift",
                "mu",
                "lambda",
                "integral",
                "mean",
                "variance",
                "q1",
                "median",
                "q3",
                "interquartile_range",
            ],
        ),
    ):
        with (OUTPUT_DIRECTORY / filename).open(
            "w", newline="", encoding="utf-8"
        ) as stream:
            writer = csv.DictWriter(stream, fieldnames=fields)
            writer.writeheader()
            writer.writerows(rows)
    return control_rows


def make_figure() -> tuple[Path, Path]:
    """Generate the two-panel SI figure."""
    times = np.linspace(0.0, PLOT_T_MAX, PLOT_POINTS)
    colors = plt.get_cmap("viridis")(np.linspace(0.02, 0.98, len(CURVES)))
    fig, axes = plt.subplots(1, 2, figsize=(7.1, 3.45), sharex=True, sharey=True)
    global_max = 0.0

    for parameters, color in zip(CURVES, colors, strict=False):
        exponential, inverse_gaussian = build_models(parameters)
        for axis, model in zip(axes, (exponential, inverse_gaussian), strict=False):
            density = np.asarray(model.pdf(times), dtype=float)
            axis.plot(
                times,
                density,
                color=color,
                linestyle="-",
                linewidth=1.7,
                label=str(parameters.number),
            )
            global_max = max(global_max, float(np.max(density)))

    for axis, title in zip(
        axes, ("(a) Shifted exponential", "(b) Shifted inverse Gaussian"), strict=False
    ):
        axis.set_title(title)
        axis.set_xlabel("Transit time (years)")
        axis.set_xlim(*XLIM)
        axis.set_ylim(0.0, global_max * 1.08)
        axis.tick_params(direction="out", width=1.0)
    axes[0].set_ylabel("Probability density (year⁻¹)")
    fig.legend(
        *axes[0].get_legend_handles_labels(),
        loc="lower center",
        ncol=6,
        frameon=False,
        fontsize=5.6,
        handlelength=2.2,
        columnspacing=1.0,
        title="Curve number",
        title_fontsize=5.6,
        bbox_to_anchor=(0.5, -0.01),
    )
    fig.subplots_adjust(left=0.11, right=0.98, top=0.88, bottom=0.23, wspace=0.12)

    png_path = OUTPUT_DIRECTORY / "LPM_distribution_families.png"
    pdf_path = OUTPUT_DIRECTORY / "LPM_distribution_families.pdf"
    fig.savefig(png_path, dpi=300, bbox_inches="tight")
    fig.savefig(pdf_path, bbox_inches="tight")
    plt.close(fig)
    return png_path, pdf_path


def main() -> None:
    controls = validate_and_write_tables()
    outputs = make_figure()
    print(
        "No. | Model | Shift | mu | lambda | Integral | Mean | Variance | Q1 | Median | Q3 | IQR"
    )
    for row in controls:
        print(
            f"{row['curve_number']} | {row['model']} | {row['shift']:g} | "
            f"{row['mu']:g} | {row['lambda']} | "
            f"{row['integral']:.6f} | {row['mean']:.6f} | {row['variance']:.6f} | "
            f"{row['q1']:.6f} | {row['median']:.6f} | {row['q3']:.6f} | "
            f"{row['interquartile_range']:.6f}"
        )
    for output in outputs:
        print(output)


if __name__ == "__main__":
    main()
