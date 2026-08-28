# Copyright (c) 2021-2026 Centre national de la recherche scientifique (CNRS)
# Contributor: Jean-Raynald de Dreuzy
# SPDX-License-Identifier: CECILL-2.1

"""Contracts for the numerical tracer protocol."""

import importlib.util

from pyages.tracer.protocols import ConvolutionTracerProtocol
from pyages.tracer.simple_tracers import (
    ConstantTracer,
    DecayTracer,
    SyntheticTracer,
)


def test_simple_tracers_implement_convolution_protocol():
    for tracer in (ConstantTracer(), DecayTracer(), SyntheticTracer()):
        assert isinstance(tracer, ConvolutionTracerProtocol)


def test_historical_tracer_protocol_facade_is_absent():
    assert importlib.util.find_spec("pyages.tracer.tracer_protocol") is None
