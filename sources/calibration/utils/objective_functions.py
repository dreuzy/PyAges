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
    """
    Basic objective function contribution (squared normalized residuals).

    Parameters
    ----------
    data : array-like
        Observed data values.
    model : array-like
        Modeled data values (same shape as data).
    error : array-like
        Error/uncertainty values (same shape as data).

    Returns
    -------
    numpy.ndarray
        Squared normalized residuals.
    """
    data_arr, model_arr, error_arr = _as_arrays(data, model, error)
    return np.square((model_arr - data_arr) / error_arr)


def RMSE(ojf, n):
    """
    Normalized objective function (root mean squared error).

    Parameters
    ----------
    ojf : array-like or float
        Objective function value(s).
    n : int
        Normalization factor (must be > 0).

    Returns
    -------
    numpy.ndarray or float
        Normalized objective value(s).
    """
    if n <= 0:
        raise ValueError(f"n must be positive (got {n})")
    return np.sqrt(np.asarray(ojf, dtype=float) / n)
