# Copyright (c) 2021-2026 Centre national de la recherche scientifique (CNRS)
# Contributor: Jean-Raynald de Dreuzy
# SPDX-License-Identifier: CECILL-2.1

"""Stable names used by calibration tables, methods, and output folders.

Keeping these persisted identifiers in one module makes their meaning explicit
and prevents readers and writers from silently drifting to different schemas.
"""

OBJECTIVE_COLUMN = "obj_function"
HALF_LOG_CHI_SQUARE_COLUMN = "half_log_chi_square"

SIMPLEX_METHOD = "Simplex"
MULTI_START_METHOD = "Simplex_multi_start"
FORWARD_UNCERTAINTY_METHOD = "forward_uncertainty_quantification"
METROPOLIS_HASTINGS_METHOD = "Metropolis_Hastings"

SIMPLEX_METHODS = frozenset({SIMPLEX_METHOD, MULTI_START_METHOD})
DISTRIBUTION_PLOT_METHODS = frozenset(
    {FORWARD_UNCERTAINTY_METHOD, METROPOLIS_HASTINGS_METHOD}
)

__all__ = [
    "FORWARD_UNCERTAINTY_METHOD",
    "HALF_LOG_CHI_SQUARE_COLUMN",
    "METROPOLIS_HASTINGS_METHOD",
    "MULTI_START_METHOD",
    "OBJECTIVE_COLUMN",
    "DISTRIBUTION_PLOT_METHODS",
    "SIMPLEX_METHOD",
    "SIMPLEX_METHODS",
]
