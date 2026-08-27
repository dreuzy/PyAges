# Copyright (c) 2021-2026 Centre national de la recherche scientifique (CNRS)
# Contributor: Jean-Raynald de Dreuzy
# SPDX-License-Identifier: CECILL-2.1

"""Public API for tracer/LPM convolution."""

from pyages.convolution.convolution import (
    Convolution,
    ConvolutionDiagnostics,
    ConvolutionError,
    PreparedTracerGrid,
)
from pyages.convolution.convolution_tracers import ConvolutionTracers
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
