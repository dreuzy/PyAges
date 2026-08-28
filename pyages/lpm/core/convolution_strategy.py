# Copyright (c) 2021-2026 Centre national de la recherche scientifique (CNRS)
# Contributor: Jean-Raynald de Dreuzy
# SPDX-License-Identifier: CECILL-2.1

"""Declare how an LPM must be convolved with a tracer chronicle.

Why this type exists
--------------------
An LPM is not only a set of probability functions. Its probability measure
may be continuous, made of one or more Dirac masses, or combine discrete and
continuous parts. Those representations cannot all be evaluated by the same
numerical operation. Every :class:`~pyages.lpm.core.lpm_base.LpmBase`
subclass therefore exposes a ``convolution_strategy`` class attribute. The
convolution engine dispatches on that declaration instead of inspecting the
concrete LPM class or maintaining a list of model names.

This enum is deliberately declarative: it does not contain convolution
algorithms. Their implementations belong to :mod:`pyages.convolution`. It is
the small, stable protocol between an LPM, which describes the probability
measure, and the forward model, which evaluates that measure against a tracer
chronicle. Consequently, a new LPM can reuse an existing strategy without any
change to the convolution engine.

Why it lives in ``pyages.lpm.core``
----------------------------------
The strategy is part of the LPM contract and is selected by LPM authors, so
its definition is owned by the LPM package. Moving it under
``pyages.convolution`` would make the LPM abstraction depend on the execution
layer that consumes it, while that layer already depends on ``LpmBase``.
Keeping the enum here preserves the dependency direction: convolution knows
about LPMs, but the LPM core does not know about convolution implementations.

Naming
------
``convolution_strategy.py`` mirrors its sole public type,
``ConvolutionStrategy``. Here *strategy* means the declared family of
algorithm to use, not an implementation of the object-oriented Strategy
pattern; the executable algorithms remain in :mod:`pyages.convolution`.

"""

from enum import Enum, auto


class ConvolutionStrategy(Enum):
    """Select the convolution algorithm required by an LPM representation.

    Each strategy corresponds to a specific numerical method optimized
    for a particular type of transit-time probability measure. Values are
    declarations consumed by :class:`pyages.convolution.convolution.Convolution`;
    they do not implement the algorithms themselves.

    Attributes
    ----------
    CONTINUOUS : enum
        Cached tracer-response grid integrated with exact CDF bin masses and
        partial first moments.

    DIRAC : enum
        Direct lookup in the recharge chronicle.
        For delta function distributions (single spike).

    DIRAC_DOUBLE : enum
        Weighted combination of two direct lookups.
        For bi-modal delta function distributions.

    MIXED_DIRAC_CONTINUOUS : enum
        Weighted combination of direct Dirac lookup and a normalized
        continuous component.
    """

    CONTINUOUS = auto()
    DIRAC = auto()
    DIRAC_DOUBLE = auto()
    MIXED_DIRAC_CONTINUOUS = auto()
