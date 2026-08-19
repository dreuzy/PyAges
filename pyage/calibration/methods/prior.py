"""Prior distributions used by Metropolis-Hastings calibration."""

from __future__ import annotations

import copy
import math
from typing import Any, Sequence

import numpy as np
import pandas as pd
from scipy.interpolate import interp1d


def make_prior_expo(
    x_data: Sequence[float],
    y_data: Sequence[float],
    xmin: float = 0.0,
    xmax: float = 70.0,
    n_points: int = 2000,
    decay_left: float = 10.0,
    decay_right: float = 10.0,
    normalize: bool = True,
) -> tuple[np.ndarray, np.ndarray]:
    """Interpolate histogram points and extend them with exponential tails."""
    x_data = np.asarray(x_data)
    y_data = np.asarray(y_data)
    interpolate = interp1d(
        x_data,
        y_data,
        kind="linear",
        bounds_error=False,
        fill_value=0,
    )

    x_cont = np.linspace(xmin, xmax, n_points)
    y_cont = interpolate(x_cont)
    left_mask = x_cont < x_data.min()
    right_mask = x_cont > x_data.max()
    if y_data[0] > 0:
        y_cont[left_mask] = y_data[0] * np.exp(
            -decay_left * (x_data[0] - x_cont[left_mask])
        )
    if y_data[-1] > 0:
        y_cont[right_mask] = y_data[-1] * np.exp(
            -decay_right * (x_cont[right_mask] - x_data[-1])
        )

    if normalize:
        # ``numpy.trapezoid`` was introduced in NumPy 2.0.  ``trapz`` keeps
        # the declared NumPy 1.x compatibility without changing the result.
        integrate_trapezoid = getattr(np, "trapezoid", None)
        if integrate_trapezoid is None:
            integrate_trapezoid = np.trapz
        area = integrate_trapezoid(y_cont, x_cont)
        if area > 0:
            y_cont /= area
    return x_cont, y_cont


def gauss(x: float, x0: float, sigma: float) -> float:
    """Evaluate a Gaussian probability density at one point."""
    numerator = math.exp(-((x - x0) ** 2) / (2.0 * sigma**2))
    denominator = math.sqrt(2 * math.pi * sigma**2)
    return numerator / denominator


def moments_histo(histogram: np.ndarray) -> tuple[float, float]:
    """Return the weighted mean and variance of a two-column histogram."""
    weights = histogram[:, 1]
    values = histogram[:, 0]
    total = np.sum(weights)
    mean = float(np.sum(values * weights) / total)
    variance = float(np.sum(values**2 * weights) / total - mean**2)
    return mean, variance


class Prior:
    """Prior distribution used by the Bayesian calibration.

    The prior can be parametric or defined empirically by a histogram.

    Parameters
    ----------
    option : bool
        Whether the prior contributes to the posterior.
    typ : str
        ``"parametric"`` or ``"empirical"``.
    prior_file : str
        Path prefix for empirical prior files.
    """

    def __init__(
        self,
        option: bool = True,
        typ: str = "parametric",
        prior_file: str = "",
    ) -> None:
        self.option = option
        self.typ = typ
        self.prior_file = prior_file
        self.MHapriori_dist: dict[str, str] = {}
        self.MHapriori_para: dict[str, Any] = {}

    def __param_init_parametric(
        self,
        key: str,
        pmin: float,
        pmax: float,
        rng: np.random.Generator,
        strategy: str,
    ) -> float:
        distribution = self.MHapriori_dist[key]
        first, second = self.MHapriori_para[key]
        if distribution == "normal":
            value = first if strategy == "map" else rng.normal(first, second)
            return float(np.clip(value, pmin, pmax))
        if distribution == "uniform":
            value = 0.5 * (first + second) if strategy == "map" else rng.uniform(first, second)
            return float(np.clip(value, pmin, pmax))
        return 0.5 * (pmin + pmax)

    def __param_init_empirical(
        self,
        key: str,
        pmin: float,
        pmax: float,
        rng: np.random.Generator,
        strategy: str,
    ) -> float:
        values, probabilities = self.MHapriori_para[key].T
        if np.all((probabilities <= 0) | ~np.isfinite(probabilities)):
            return 0.5 * (pmin + pmax)
        if strategy == "map":
            value = float(values[np.argmax(probabilities)])
        else:
            increments = 0.5 * (probabilities[:-1] + probabilities[1:]) * np.diff(values)
            cdf = np.concatenate([[0.0], np.cumsum(increments)])
            if cdf[-1] > 0:
                cdf /= cdf[-1]
                value = float(np.interp(rng.random(), cdf, values))
            else:
                value = float(values[np.argmax(probabilities)])
        return float(np.clip(value, pmin, pmax))

    def param_init(self, lpm: Any, strategy: str = "map") -> None:
        """Initialize model parameters from the configured prior."""
        rng = np.random.default_rng()
        parameters = []
        for key in lpm.p:
            bounds = lpm.get_p_min(key), lpm.get_p_max(key)
            if self.typ == "parametric":
                value = self.__param_init_parametric(key, *bounds, rng, strategy)
            elif self.typ == "empirical":
                value = self.__param_init_empirical(key, *bounds, rng, strategy)
            else:
                value = 0.5 * sum(bounds)
            parameters.append(value)
        lpm.set_param_from_array(parameters)

    def __load_parametric_priors(self, lpm: Any) -> None:
        from pyage.data_io import lpm_params

        params = lpm_params.load_params(lpm.name, lpm.lpm_data_directory)
        for name, prior in lpm_params.get_priors(params).items():
            prior_type = prior.get("type")
            if not prior_type:
                continue
            self.MHapriori_dist[name] = prior_type
            if prior_type == "uniform":
                self.MHapriori_para[name] = [prior.get("min"), prior.get("max")]
            elif prior_type in {"normal", "gaussian"}:
                self.MHapriori_para[name] = [prior.get("mean"), prior.get("std")]
            else:
                self.MHapriori_para[name] = list(prior.get("args", []))[:2]
        if not self.MHapriori_dist:
            raise ValueError(f"No MH priors found in params.yaml for {lpm.name}.")

    def __load_empirical_priors(self, lpm: Any) -> None:
        self.MHapriori_para = {}
        for parameter in lpm.get_param_names():
            histogram = pd.read_csv(
                f"{self.prior_file}_{parameter}.txt",
                sep="\t",
            ).to_numpy()
            decay = 500.0 / abs(lpm.get_p_min(parameter) - lpm.get_p_max(parameter))
            x_values, probabilities = make_prior_expo(
                histogram[:, 0],
                histogram[:, 1],
                xmin=lpm.get_p_min(parameter),
                xmax=lpm.get_p_max(parameter),
                n_points=101,
                decay_left=decay,
                decay_right=decay,
            )
            self.MHapriori_para[parameter] = np.column_stack((x_values, probabilities))

    def load(self, lpm: Any) -> None:
        """Load prior definitions for a model."""
        if not self.option:
            return
        if self.typ == "parametric":
            self.__load_parametric_priors(lpm)
        elif self.typ == "empirical":
            self.__load_empirical_priors(lpm)
        else:
            raise ValueError(f"Unsupported prior type: {self.typ}")

    def __evaluate_parametric(self, lpm: Any, params: list[float]) -> float:
        probability = 1.0
        for index, key in enumerate(lpm.p):
            distribution = self.MHapriori_dist[key]
            first, second = self.MHapriori_para[key]
            if distribution == "normal":
                probability *= gauss(params[index], first, second)
            elif distribution == "uniform":
                if first < params[index] < second:
                    probability /= abs(second - first)
                else:
                    probability = 0
            elif distribution == "lognormal":
                raise ValueError("Lognormal prior is not implemented for errors.")
            else:
                raise ValueError(f"Unsupported prior distribution: {distribution}")
        return probability

    def __evaluate_empirical(self, lpm: Any, params: list[float]) -> float:
        probability = 1.0
        for index, parameter in enumerate(lpm.get_param_names()):
            histogram = self.MHapriori_para[parameter]
            if params[index] < histogram[0, 0] or params[index] > histogram[-1, 0]:
                return 0.0
            nearest = np.argmin(abs(histogram[:, 0] - params[index]))
            probability *= histogram[nearest, 1]
        return probability

    def evaluate(self, lpm: Any, params: list[float]) -> float:
        """Evaluate the prior density for the current parameters."""
        if self.typ == "parametric":
            probability = self.__evaluate_parametric(lpm, params)
        elif self.typ == "empirical":
            probability = self.__evaluate_empirical(lpm, params)
        else:
            raise ValueError(f"Unsupported prior type: {self.typ}")
        return max(probability, 1e-300)

    def validation_MH_prior(
        self,
        path: pd.DataFrame,
        lpm: Any,
    ) -> dict[str, dict[str, dict[str, float]]]:
        """Compare sampled prior moments with theoretical expectations."""
        sampled = {
            key: [
                np.nanmean(path[key].to_numpy(), dtype="float"),
                np.nanvar(path[key].to_numpy(), dtype="float"),
            ]
            for key in lpm.p
        }
        theory = copy.deepcopy(sampled)
        if self.typ == "parametric":
            for key in lpm.p:
                first, second = self.MHapriori_para[key]
                if self.MHapriori_dist[key] == "normal":
                    theory[key] = [first, second**2]
                elif self.MHapriori_dist[key] == "uniform":
                    theory[key] = [(first + second) / 2, ((second - first) / np.sqrt(12)) ** 2]
        elif self.typ == "empirical":
            for key in lpm.p:
                theory[key] = list(moments_histo(self.MHapriori_para[key]))

        differences = copy.deepcopy(sampled)
        for key in lpm.p:
            differences[key][0] = 100 * (1 - sampled[key][0] / theory[key][0])
            differences[key][1] = 100 * (1 - sampled[key][1] / theory[key][1])
        return {
            "sampled": {key: {"mean": value[0], "var": value[1]} for key, value in sampled.items()},
            "theory": {key: {"mean": value[0], "var": value[1]} for key, value in theory.items()},
            "difference_percent": {
                key: {"mean": value[0], "var": value[1]}
                for key, value in differences.items()
            },
        }
