# Copyright (c) 2021-2026 Centre national de la recherche scientifique (CNRS)
# Contributor: Jean-Raynald de Dreuzy
# SPDX-License-Identifier: CECILL-2.1

"""Contracts for tracer protocols and compatibility imports."""

from pyages.tracer.protocols import ConvolutionTracerProtocol, TracerProtocol
from pyages.tracer.simple_tracers import (
    ConstantTracer,
    DecayTracer,
    SyntheticTracer,
)
from pyages.tracer.tracer_protocol import (
    ConstantTracer as LegacyConstantTracer,
)
from pyages.tracer.tracer_protocol import DecayTracer as LegacyDecayTracer
from pyages.tracer.tracer_protocol import SyntheticTracer as LegacySyntheticTracer


def test_simple_tracers_implement_both_protocols():
    for tracer in (ConstantTracer(), DecayTracer(), SyntheticTracer()):
        assert isinstance(tracer, ConvolutionTracerProtocol)
        assert isinstance(tracer, TracerProtocol)


def test_historical_module_reexports_simple_tracers_without_wrapping():
    assert LegacyConstantTracer is ConstantTracer
    assert LegacyDecayTracer is DecayTracer
    assert LegacySyntheticTracer is SyntheticTracer
