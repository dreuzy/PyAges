# Copyright (c) 2021-2026 Centre national de la recherche scientifique (CNRS)
# Contributor: Jean-Raynald de Dreuzy
# SPDX-License-Identifier: CECILL-2.1

"""Plot LPM pairs matched by shift, median, and interquartile range."""

from __future__ import annotations

import csv
from dataclasses import dataclass
from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np
from scipy.integrate import quad
from scipy.optimize import least_squares

from pyages.lpm.models.exponential_shifted import ExponentialShiftedLpm
from pyages.lpm.models.inverse_gaussian_shifted import InverseGaussianShiftedLpm

REPOSITORY_ROOT = Path(__file__).resolve().parents[6]
OUTPUT_DIRECTORY = (
    REPOSITORY_ROOT / "results" / "HYP-26-0172" / "figures" / "supporting_information"
)
LPM_PARAMETER_DIRECTORY = REPOSITORY_ROOT / "sites" / "ploemeur" / "params_lpm"
PLOT_POINTS = 5000
XLIM = (0.0, 160.0)


@dataclass(frozen=True)
class ExponentialParameters:
    pair: int
    shift: float
    mu: float


EXPONENTIAL_PARAMETER_SETS = (
    ExponentialParameters(1, 0.0, 15.0),
    ExponentialParameters(2, 0.0, 40.0),
    ExponentialParameters(3, 5.0, 25.0),
    ExponentialParameters(4, 10.0, 20.0),
    ExponentialParameters(5, 10.0, 50.0),
    ExponentialParameters(6, 20.0, 20.0),
)


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


def exponential_model(parameters: ExponentialParameters) -> ExponentialShiftedLpm:
    return ExponentialShiftedLpm(
        mu=parameters.mu,
        shift=parameters.shift,
        directory_lpm=LPM_PARAMETER_DIRECTORY,
    )


def inverse_gaussian_model(
    shift: float, mu_physical: float, lambda_physical: float
) -> InverseGaussianShiftedLpm:
    """Build the repository model from standard physical IG parameters."""
    sigma_physical = np.sqrt(mu_physical**3 / lambda_physical)
    return InverseGaussianShiftedLpm(
        mu=mu_physical,
        sigma=sigma_physical,
        shift=shift,
        directory_lpm=LPM_PARAMETER_DIRECTORY,
    )


def quantiles(model) -> tuple[float, float, float, float]:
    q1, median, q3 = (float(value) for value in model.cdf_inv([0.25, 0.5, 0.75]))
    return q1, median, q3, q3 - q1


def match_inverse_gaussian(
    parameters: ExponentialParameters,
) -> tuple[InverseGaussianShiftedLpm, float, float]:
    """Match IG median and IQR to one shifted exponential distribution."""
    target_median = parameters.shift + parameters.mu * np.log(2.0)
    target_iqr = parameters.mu * np.log(3.0)

    def residuals(log_parameters: np.ndarray) -> np.ndarray:
        mu_ig, lambda_ig = np.exp(log_parameters)
        model = inverse_gaussian_model(parameters.shift, mu_ig, lambda_ig)
        _, median, _, iqr = quantiles(model)
        return np.array(
            [(median - target_median) / target_iqr, (iqr - target_iqr) / target_iqr]
        )

    initial = np.log([1.2262 * parameters.mu, 0.7566 * parameters.mu])
    solution = least_squares(
        residuals, initial, xtol=1e-13, ftol=1e-13, gtol=1e-13, max_nfev=500
    )
    if not solution.success:
        raise RuntimeError(
            f"Quantile matching failed for pair {parameters.pair}: {solution.message}"
        )
    mu_ig, lambda_ig = (float(value) for value in np.exp(solution.x))
    model = inverse_gaussian_model(parameters.shift, mu_ig, lambda_ig)
    _, median, _, iqr = quantiles(model)
    if abs(median - target_median) >= 1e-6 or abs(iqr - target_iqr) >= 1e-6:
        raise RuntimeError(f"Quantile tolerances not met for pair {parameters.pair}")
    return model, mu_ig, lambda_ig


def numerical_moments(model, shift: float) -> tuple[float, float, float]:
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


def calculate_rows():
    parameter_rows = []
    check_rows = []
    matched_models = []

    for parameters in EXPONENTIAL_PARAMETER_SETS:
        exp_model = exponential_model(parameters)
        ig_model, mu_ig, lambda_ig = match_inverse_gaussian(parameters)
        exp_q1, exp_median, exp_q3, exp_iqr = quantiles(exp_model)
        ig_q1, ig_median, ig_q3, ig_iqr = quantiles(ig_model)
        delta_median = ig_median - exp_median
        delta_iqr = ig_iqr - exp_iqr
        if abs(delta_median) >= 0.01 or abs(delta_iqr) >= 0.01:
            raise RuntimeError(f"Pair-level check failed for pair {parameters.pair}")

        for name, model, mu, lambda_value, values in (
            (
                "shifted exponential",
                exp_model,
                parameters.mu,
                "not applicable",
                (exp_q1, exp_median, exp_q3, exp_iqr),
            ),
            (
                "shifted inverse Gaussian",
                ig_model,
                mu_ig,
                lambda_ig,
                (ig_q1, ig_median, ig_q3, ig_iqr),
            ),
        ):
            density = np.asarray(
                model.pdf(np.linspace(parameters.shift, 300.0, PLOT_POINTS))
            )
            if np.any(~np.isfinite(density)) or np.any(density < 0.0):
                raise RuntimeError(
                    f"Invalid density for pair {parameters.pair}, {name}"
                )
            integral, mean, variance = numerical_moments(model, parameters.shift)
            if abs(integral - 1.0) >= 1e-3:
                raise RuntimeError(
                    f"Integral check failed for pair {parameters.pair}, {name}"
                )
            q1, median, q3, iqr = values
            base = {
                "pair": parameters.pair,
                "model": name,
                "shift": parameters.shift,
                "mu": mu,
                "lambda": lambda_value,
                "q1": q1,
                "median": median,
                "q3": q3,
                "iqr": iqr,
                "mean": mean,
                "variance": variance,
            }
            parameter_rows.append(base)
            check_rows.append(
                {
                    **base,
                    "integral": integral,
                    "median_error_within_pair": delta_median,
                    "iqr_error_within_pair": delta_iqr,
                }
            )
        matched_models.append((parameters.pair, exp_model, ig_model))
    return parameter_rows, check_rows, matched_models


def write_csv_files(parameter_rows, check_rows) -> tuple[Path, Path]:
    OUTPUT_DIRECTORY.mkdir(parents=True, exist_ok=True)
    parameter_path = (
        OUTPUT_DIRECTORY / "LPM_distribution_families_matched_quantiles_parameters.csv"
    )
    check_path = OUTPUT_DIRECTORY / "LPM_distribution_families_quantile_checks.csv"
    parameter_fields = [
        "pair",
        "model",
        "shift",
        "mu",
        "lambda",
        "q1",
        "median",
        "q3",
        "iqr",
        "mean",
        "variance",
    ]
    check_fields = [
        "pair",
        "model",
        "shift",
        "mu",
        "lambda",
        "integral",
        "q1",
        "median",
        "q3",
        "iqr",
        "mean",
        "variance",
        "median_error_within_pair",
        "iqr_error_within_pair",
    ]
    for path, rows, fields in (
        (parameter_path, parameter_rows, parameter_fields),
        (check_path, check_rows, check_fields),
    ):
        with path.open("w", newline="", encoding="utf-8") as stream:
            writer = csv.DictWriter(stream, fieldnames=fields)
            writer.writeheader()
            writer.writerows(rows)
    return parameter_path, check_path


def make_figure(matched_models) -> tuple[Path, Path]:
    times = np.linspace(XLIM[0], XLIM[1], PLOT_POINTS)
    colors = plt.get_cmap("viridis")(np.linspace(0.02, 0.98, len(matched_models)))
    fig, axes = plt.subplots(1, 2, figsize=(7.1, 3.45), sharex=True, sharey=True)
    global_max = 0.0
    for (pair, exp_model, ig_model), color in zip(matched_models, colors, strict=False):
        for axis, model in zip(axes, (exp_model, ig_model), strict=False):
            density = np.asarray(model.pdf(times), dtype=float)
            axis.plot(times, density, color=color, linewidth=1.7, label=str(pair))
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
        title="Parameter set",
        title_fontsize=5.6,
        bbox_to_anchor=(0.5, -0.01),
    )
    fig.subplots_adjust(left=0.11, right=0.98, top=0.88, bottom=0.23, wspace=0.12)
    png_path = OUTPUT_DIRECTORY / "LPM_distribution_families_matched_quantiles.png"
    pdf_path = OUTPUT_DIRECTORY / "LPM_distribution_families_matched_quantiles.pdf"
    fig.savefig(png_path, dpi=300, bbox_inches="tight")
    fig.savefig(pdf_path, bbox_inches="tight")
    plt.close(fig)
    return pdf_path, png_path


def main() -> None:
    parameter_rows, check_rows, matched_models = calculate_rows()
    outputs = (
        *make_figure(matched_models),
        *write_csv_files(parameter_rows, check_rows),
    )
    print(
        "Pair | Model | Shift | Mu | Lambda | Q1 | Median | Q3 | IQR | Mean | Variance"
    )
    for row in parameter_rows:
        print(
            f"{row['pair']} | {row['model']} | {row['shift']:.6g} | {row['mu']:.9g} | "
            f"{row['lambda']} | {row['q1']:.6f} | {row['median']:.6f} | "
            f"{row['q3']:.6f} | {row['iqr']:.6f} | {row['mean']:.6f} | "
            f"{row['variance']:.6f}"
        )
    print("Pair | delta median | delta IQR")
    for row in check_rows[1::2]:
        print(
            f"{row['pair']} | {row['median_error_within_pair']:.3e} | "
            f"{row['iqr_error_within_pair']:.3e}"
        )
    for output in outputs:
        print(output)


if __name__ == "__main__":
    main()
