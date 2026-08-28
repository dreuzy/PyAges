# Copyright (c) 2021-2026 Centre national de la recherche scientifique (CNRS)
# Contributor: Jean-Raynald de Dreuzy
# SPDX-License-Identifier: CECILL-2.1

"""Backward-compatible tracer protocol and utility-tracer imports.

New code should import structural interfaces from
:mod:`pyages.tracer.protocols` and in-memory implementations from
:mod:`pyages.tracer.simple_tracers`. This module remains as a compatibility
facade for existing contributor code.
"""

from pyages.tracer.protocols import ConvolutionTracerProtocol, TracerProtocol
from pyages.tracer.simple_tracers import ConstantTracer, DecayTracer, SyntheticTracer

__all__ = [
    "ConstantTracer",
    "ConvolutionTracerProtocol",
    "DecayTracer",
    "SyntheticTracer",
    "TracerProtocol",
]
