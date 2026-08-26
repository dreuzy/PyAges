# -*- coding: utf-8 -*-
"""
Distribution helpers for LPM sampling.

Purpose
-------
Sample LPMs from a stored distribution table and assemble
PDF samples and summary statistics.
"""

from __future__ import annotations

import copy
from typing import List, Tuple

import numpy as np
import pandas as pd

from pyage.config.runtime import subdivide_interval


def sample_lpms_from_dist(
    dist: pd.DataFrame,
    lpm_template,
    lpm_number: int = 10,
    array_resolution: int = 1000,
    rng: np.random.Generator | None = None,
) -> Tuple[List[object], pd.DataFrame, pd.DataFrame]:
    """
    Sample LPMs from a distribution table and return PDFs + stats.

    Parameters
    ----------
    dist : DataFrame
        LPM distribution table (e.g., from lpm_dist_calibrated.txt).
    lpm_template : LPM
        Template LPM instance used to load parameters and compute moments.
    lpm_number : int, optional
        Number of LPM samples to draw.
    array_resolution : int, optional
        Resolution of the PDF time grid.
    rng : np.random.Generator, optional
        Random generator for sampling.

    Returns
    -------
    lpm_list : list
        List of sampled LPM instances.
    pdf : DataFrame
        PDF samples (t + one column per sampled LPM).
    lpm_statistics : DataFrame
        Summary statistics for sampled LPMs.
    """
    rng = rng or np.random.default_rng(12345)
    pdf_t = subdivide_interval(0, 70, array_resolution - 1)
    pdf_array = np.empty((lpm_number + 1, array_resolution))
    pdf_array[0, :] = pdf_t
    colnames = ["t"]

    lpm_statistics = pd.DataFrame(
        index=range(lpm_number), columns=lpm_template.moments_name()
    )
    lpm_list: List[object] = []

    for i in range(1, lpm_number + 1):
        lines = lpm_template.load_sample(dist, selection="random_line", rng=rng)
        if lines is None:
            colnames.append("p")
            continue

        lpm_list.append(copy.deepcopy(lpm_template))
        pdf_array[i, :] = lpm_template.pdf(pdf_t)
        colnames.append(f"p{lines}")
        lpm_statistics.iloc[i - 1] = lpm_template.moments()

    pdf = pd.DataFrame(pdf_array.T, columns=colnames)
    return lpm_list, pdf, lpm_statistics
