# Copyright (c) 2021-2026 Centre national de la recherche scientifique (CNRS)
# Contributor: Jean-Raynald de Dreuzy
# SPDX-License-Identifier: CECILL-2.1

"""Independent analytical distributions and slow forward convolution."""

from __future__ import annotations

from math import pi
from typing import Callable

import numpy as np
from scipy.special import ndtr

from .mappings import dm_to_inverse_gaussian, epm_to_shifted_exponential


def pdf(model: str, age: float | np.ndarray, parameters: dict) -> np.ndarray:
    """Evaluate a continuous LPM density without calling PyAges model classes."""
    age = np.asarray(age, dtype=float)
    result = np.zeros_like(age)
    model = model.upper()
    if model == "EMM":
        tau = float(parameters["tau"])
        valid = age >= 0
        result[valid] = np.exp(-age[valid] / tau) / tau
    elif model == "EPM":
        mapped = epm_to_shifted_exponential(parameters["tau"], parameters["eta"])
        valid = age >= mapped.shift
        result[valid] = np.exp(-(age[valid] - mapped.shift) / mapped.mu) / mapped.mu
    elif model == "DM":
        tau = float(parameters["tau"])
        dp = float(parameters["DP"])
        valid = age > 0
        a = age[valid]
        result[valid] = np.sqrt(tau / (4 * pi * dp * a**3)) * np.exp(
            -((a - tau) ** 2) / (4 * dp * tau * a)
        )
    else:
        raise ValueError(f"No continuous PDF for model {model}")
    return result


def cdf(model: str, age: float | np.ndarray, parameters: dict) -> np.ndarray:
    """Evaluate analytical CDFs used to diagnose covered distribution mass."""
    age = np.asarray(age, dtype=float)
    model = model.upper()
    if model == "PFM":
        return (age >= float(parameters["tau"])).astype(float)
    if model == "EMM":
        tau = float(parameters["tau"])
        return np.where(age >= 0, 1 - np.exp(-np.maximum(age, 0) / tau), 0.0)
    if model == "EPM":
        mapped = epm_to_shifted_exponential(parameters["tau"], parameters["eta"])
        return np.where(
            age >= mapped.shift,
            1 - np.exp(-(np.maximum(age, mapped.shift) - mapped.shift) / mapped.mu),
            0.0,
        )
    if model == "DM":
        mapped = dm_to_inverse_gaussian(parameters["tau"], parameters["DP"])
        tau, sigma = mapped.mu, mapped.sigma
        positive = np.maximum(age, np.finfo(float).tiny)
        lam = tau**3 / sigma**2
        root = np.sqrt(lam / positive)
        values = ndtr(root * (positive / tau - 1)) + np.exp(2 * lam / tau) * ndtr(
            -root * (positive / tau + 1)
        )
        return np.where(age > 0, values, 0.0)
    raise ValueError(f"Unknown model {model}")


def moments(model: str, parameters: dict) -> tuple[float, float]:
    """Return analytical mean and standard deviation."""
    model = model.upper()
    tau = float(parameters["tau"])
    if model == "PFM":
        return tau, 0.0
    if model == "EMM":
        return tau, tau
    if model == "EPM":
        mapped = epm_to_shifted_exponential(tau, parameters["eta"])
        return tau, mapped.mu
    if model == "DM":
        mapped = dm_to_inverse_gaussian(tau, parameters["DP"])
        return mapped.mu, mapped.sigma
    raise ValueError(f"Unknown model {model}")


def forward(
    model: str,
    parameters: dict,
    observation_year: float,
    input_function: Callable[[float], float],
    maximum_age: float,
    integration_points: np.ndarray | None = None,
) -> tuple[float, float]:
    """Return concentration and covered mass using adaptive quadrature."""
    model = model.upper()
    if maximum_age < 0:
        return 0.0, 0.0
    if model == "PFM":
        tau = float(parameters["tau"])
        return (
            (float(input_function(observation_year - tau)), 1.0)
            if tau <= maximum_age
            else (0.0, 0.0)
        )

    points = (
        []
        if integration_points is None
        else [float(point) for point in integration_points if 0 < point < maximum_age]
    )
    if model == "EPM":
        points.append(
            epm_to_shifted_exponential(parameters["tau"], parameters["eta"]).shift
        )
    boundaries = np.asarray([0.0, *sorted(set(points)), maximum_age])
    left, right = boundaries[:-1], boundaries[1:]
    nodes, weights = np.polynomial.legendre.leggauss(8)
    ages = ((right - left)[:, None] * nodes + (right + left)[:, None]) / 2
    sample_years = observation_year - ages
    try:
        input_values = np.asarray(input_function(sample_years), dtype=float)
        if input_values.shape != sample_years.shape:
            raise ValueError
    except (TypeError, ValueError):
        input_values = np.asarray(
            [input_function(float(year)) for year in sample_years.ravel()]
        ).reshape(sample_years.shape)
    density = pdf(model, ages, parameters)
    interval_integrals = (
        (right - left) / 2 * np.sum(weights * input_values * density, axis=1)
    )
    value = float(np.sum(interval_integrals))
    return value, float(cdf(model, maximum_age, parameters))
