# Copyright (c) 2021-2026 Centre national de la recherche scientifique (CNRS)
# Contributor: Jean-Raynald de Dreuzy
# SPDX-License-Identifier: CECILL-2.1
# This file lists the MH classes and functions available to other packages.

"""Provide the public entry points for Metropolis--Hastings calibration.

Importing from this package gives callers the supported high-level chain and
ensemble configurations, samplers, run record, and convergence error without
requiring knowledge of the files in which they are implemented. Leaf result
and seed records remain available from their defining contributor modules.
"""

from pyages.calibration.methods.mh.config import MHConfig
from pyages.calibration.methods.mh.ensemble import MultiChainMetropolisHastings
from pyages.calibration.methods.mh.ensemble_config import (
    MHDiagnosticsConfig,
    MHEnsembleConfig,
    MHInitializationConfig,
    MHPilotConfig,
)
from pyages.calibration.methods.mh.errors import MHConvergenceError
from pyages.calibration.methods.mh.results import MHRunRecord
from pyages.calibration.methods.mh.sampler import MetropolisHastings

__all__ = [
    "MHConfig",
    "MHConvergenceError",
    "MHDiagnosticsConfig",
    "MHEnsembleConfig",
    "MHInitializationConfig",
    "MHPilotConfig",
    "MHRunRecord",
    "MetropolisHastings",
    "MultiChainMetropolisHastings",
]
