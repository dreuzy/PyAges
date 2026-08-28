# Copyright (c) 2021-2026 Centre national de la recherche scientifique (CNRS)
# Contributor: Jean-Raynald de Dreuzy
# SPDX-License-Identifier: CECILL-2.1

"""Public entry point for tracer/LPM convolution.

The package exposes the single- and multi-tracer engines together with the
immutable grid records, diagnostics, errors, and numerical settings they use.
"""

from pyages.convolution.batch import ConvolutionTracers
from pyages.convolution.convolution import Convolution
from pyages.convolution.models import (
    ConvolutionDiagnostics,
    ConvolutionError,
    PreparedTracerGrid,
)
from pyages.convolution.settings import (
    DEFAULT_TRACER_GRID_SETTINGS,
    TracerGridSettings,
)

__all__ = [
    "Convolution",
    "ConvolutionDiagnostics",
    "ConvolutionError",
    "ConvolutionTracers",
    "DEFAULT_TRACER_GRID_SETTINGS",
    "PreparedTracerGrid",
    "TracerGridSettings",
]
