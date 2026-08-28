# Copyright (c) 2021-2026 Centre national de la recherche scientifique (CNRS)
# Contributor: Jean-Raynald de Dreuzy
# SPDX-License-Identifier: CECILL-2.1

"""Exceptions shared by tracer/LPM convolution components."""


class ConvolutionError(Exception):
    """Report a violated numerical contract during preparation or execution."""


__all__ = ["ConvolutionError"]
