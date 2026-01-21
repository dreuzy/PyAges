# -*- coding: utf-8 -*-
"""
Objective function utilities for calibration.
"""

import numpy as np


def objective_function(data, model, error):
    """
    Basic objective function contribution.
    """
    return np.square((model - data) / error)


def objective_function_norm(ojf, n):
    """
    Normalized objective function (consistent usage across the codebase).
    """
    return np.sqrt(ojf / n)
