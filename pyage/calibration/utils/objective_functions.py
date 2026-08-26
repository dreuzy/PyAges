# -*- coding: utf-8 -*-
"""
Created on Wed Mar 24 20:35:54 2021

@author: Jean-Raynald de Dreuzy

Objective functions for calibration.
"""

import numpy as np


def _as_arrays(data, model, error):
    """
    Normalize inputs to 1D numpy arrays and validate lengths.
    """
    data_arr = np.asarray(data, dtype=float)
    model_arr = np.asarray(model, dtype=float)
    error_arr = np.asarray(error, dtype=float)

    if error_arr.shape == () and data_arr.shape != ():
        error_arr = np.full_like(data_arr, float(error_arr))

    if data_arr.shape != model_arr.shape or data_arr.shape != error_arr.shape:
        raise ValueError(
            "data, model, and error must have the same shape "
            f"(got data={data_arr.shape}, model={model_arr.shape}, error={error_arr.shape})"
        )

    return data_arr, model_arr, error_arr


def L2_norm_diff(data, model, error):
    r"""Return independent Gaussian squared-normalized residuals.

    For observation :math:`y_i`, prediction :math:`m_i`, and reported
    one-standard-deviation uncertainty :math:`\sigma_i`, each contribution is
    :math:`r_i^2=((m_i-y_i)/\sigma_i)^2`. Their sum is the chi-square quantity
    used by :class:`~pyage.calibration.problem.CalibrationProblem`.

    Parameters
    ----------
    data : array-like
        Observed data values.
    model : array-like
        Modeled data values (same shape as data).
    error : array-like
        One-standard-deviation uncertainties in the same units and order as
        ``data``. Scientific calibration callers require finite positive
        values; this low-level vector operation only checks shapes.

    Returns
    -------
    numpy.ndarray
        Dimensionless squared normalized residuals, one per observation.

    Notes
    -----
    The likelihood assumes independent, unbiased Gaussian observation errors
    with known standard deviations. Correlated errors require a covariance
    likelihood and are not represented by this function.
    """
    data_arr, model_arr, error_arr = _as_arrays(data, model, error)
    return np.square((model_arr - data_arr) / error_arr)


def normalized_residual_norm(chi_square, sample_count):
    r"""Return :math:`\sqrt{\chi^2/n}` for normalized residuals.

    This diagnostic is dimensionless because residuals have already been
    divided by observation uncertainty; it is not an RMSE in concentration
    units.

    Parameters
    ----------
    chi_square : array-like or float
        Chi-square value or values, :math:`\chi^2=\sum_i r_i^2`.
    sample_count : int
        Number of residuals used in the sum; must be positive. No fitted-degree
        of-freedom correction is applied.

    Returns
    -------
    numpy.ndarray or float
        Dimensionless :math:`\sqrt{\chi^2/n}` value or values.
    """
    if sample_count <= 0:
        raise ValueError(f"sample_count must be positive (got {sample_count})")
    return np.sqrt(np.asarray(chi_square, dtype=float) / sample_count)
