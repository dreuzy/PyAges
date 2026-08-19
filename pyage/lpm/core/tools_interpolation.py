# -*- coding: utf-8 -*-
"""
Created on Mon May 24 17:03:47 2021

@author: Jean-Raynald de Dreuzy

Purpose
-------
Interpolation helpers for LPM Dirac-based models.
Provides a normalized interpolator for discretized PDFs and a
discretized Dirac pulse used by Dirac/Dirac-double distributions.
"""

from scipy import interpolate  # Interpolation function


def interp_normalize(td, pdfd):
    """
    Purpose
    -------
    Return an interpolator normalized to unit integral.

    Parameters
    ----------
    td : array
        Discrete time grid.
    pdfd : array
        PDF values evaluated on td.

    Returns
    -------
    fd : interpolator
        Interpolation function for the normalized PDF.
    """
    fd = interpolate.interp1d(td, pdfd)
    # Ensures integral to one
    step_size = td[1] - td[0]
    sumftd = sum(fd(td) * step_size)
    if sumftd != 0:
        fd = interpolate.interp1d(td, pdfd / sumftd)
    else:
        # Avoid noisy output; return a zero PDF interpolator.
        fd = interpolate.interp1d(td, pdfd, bounds_error=False, fill_value=0.0)
    # sum(fd(td)*step_size)
    return fd


def dirac_discret(t, center=1, width=1):
    """
    Purpose
    -------
    Return a discretized Dirac pulse on a grid.

    The pulse is 1/width on [center - width/2, center + width/2] and 0 elsewhere.

    Parameters
    ----------
    t : array
        Discrete time grid.
    center : float
        Center of the Dirac pulse.
    width : float
        Width of the Dirac pulse.

    Returns
    -------
    array
        Discrete Dirac values on t.
    """
    return ((t >= center - width / 2) * (t <= center + width / 2)).astype(int) / width
