# Copyright (c) 2021-2026 Centre national de la recherche scientifique (CNRS)
# Contributor: Jean-Raynald de Dreuzy
# SPDX-License-Identifier: CECILL-2.1
# This file defines the public import surface for tracer/LPM convolution.
# It gives callers the single- and multi-tracer engines, settings, diagnostics,
# prepared grids, and errors without exposing their implementation modules.

"""Public entry point for tracer/LPM convolution.

The package exposes the single- and multi-tracer engines together with the
immutable grid records, diagnostics, errors, and numerical settings they use.
"""

from pyages.convolution.continuous_integration import ConvolutionDiagnostics
from pyages.convolution.convolution import Convolution
from pyages.convolution.errors import ConvolutionError
from pyages.convolution.multi_tracer import ConvolutionTracers
from pyages.convolution.settings import (
    DEFAULT_CONVOLUTION_SETTINGS,
    ConvolutionSettings,
)
from pyages.convolution.tracer_grid import PreparedTracerGrid

__all__ = [
    "Convolution",
    "ConvolutionDiagnostics",
    "ConvolutionError",
    "ConvolutionSettings",
    "ConvolutionTracers",
    "DEFAULT_CONVOLUTION_SETTINGS",
    "PreparedTracerGrid",
]
