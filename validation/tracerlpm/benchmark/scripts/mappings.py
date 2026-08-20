"""Pure, reversible parameter mappings between TracerLPM and PyAge."""

from __future__ import annotations

from dataclasses import dataclass
from math import sqrt


def _positive(name: str, value: float) -> float:
    value = float(value)
    if value <= 0:
        raise ValueError(f"{name} must be positive, got {value}")
    return value


@dataclass(frozen=True)
class ShiftedExponentialParameters:
    mu: float
    shift: float


@dataclass(frozen=True)
class EpmParameters:
    tau: float
    eta: float


@dataclass(frozen=True)
class InverseGaussianParameters:
    mu: float
    sigma: float


@dataclass(frozen=True)
class DmParameters:
    tau: float
    dispersion_parameter: float


def pfm_to_dirac(tau: float) -> float:
    return _positive("tau", tau)


def emm_to_exponential(tau: float) -> float:
    return _positive("tau", tau)


def epm_to_shifted_exponential(tau: float, eta: float) -> ShiftedExponentialParameters:
    tau = _positive("tau", tau)
    eta = _positive("eta", eta)
    if eta < 1:
        raise ValueError(f"eta must be greater than or equal to 1, got {eta}")
    return ShiftedExponentialParameters(mu=tau / eta, shift=tau * (1 - 1 / eta))


def shifted_exponential_to_epm(mu: float, shift: float) -> EpmParameters:
    mu = _positive("mu", mu)
    shift = float(shift)
    if shift < 0:
        raise ValueError(f"shift must be non-negative, got {shift}")
    return EpmParameters(tau=shift + mu, eta=1 + shift / mu)


def dm_to_inverse_gaussian(
    tau: float, dispersion_parameter: float
) -> InverseGaussianParameters:
    tau = _positive("tau", tau)
    dispersion_parameter = _positive("dispersion_parameter", dispersion_parameter)
    return InverseGaussianParameters(
        mu=tau,
        sigma=tau * sqrt(2 * dispersion_parameter),
    )


def inverse_gaussian_to_dm(mu: float, sigma: float) -> DmParameters:
    mu = _positive("mu", mu)
    sigma = _positive("sigma", sigma)
    return DmParameters(tau=mu, dispersion_parameter=sigma**2 / (2 * mu**2))
