# Copyright (c) 2021-2026 Centre national de la recherche scientifique (CNRS)
# Contributor: Jean-Raynald de Dreuzy
# SPDX-License-Identifier: CECILL-2.1
# This file lists the MH classes and functions available to other packages.

"""Provide the public entry points for Metropolis--Hastings calibration.

Importing from this package gives callers the supported high-level chain and
run configurations, samplers, run record, and convergence error without
requiring knowledge of the files in which they are implemented. Leaf result
and seed records remain available from their defining contributor modules.
"""

from pyages.calibration.methods.mh.config import MHConfig
from pyages.calibration.methods.mh.errors import MHConvergenceError
from pyages.calibration.methods.mh.results import MHRunRecord
from pyages.calibration.methods.mh.run_config import (
    MHDiagnosticsConfig,
    MHInitializationConfig,
    MHPilotConfig,
    MHRunConfig,
)
from pyages.calibration.methods.mh.runner import MetropolisHastingsRunner
from pyages.calibration.methods.mh.sampler import MetropolisHastings

__all__ = [
    "MHConfig",
    "MHConvergenceError",
    "MHDiagnosticsConfig",
    "MHRunConfig",
    "MHInitializationConfig",
    "MHPilotConfig",
    "MHRunRecord",
    "MetropolisHastings",
    "MetropolisHastingsRunner",
]
