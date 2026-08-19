# -*- coding: utf-8 -*-
"""
Convolution strategy enumeration for LPM models.

Purpose
-------
Defines the available convolution strategies as an enumeration. Each LPM
declares which strategy it requires, allowing the convolution module to
dispatch appropriately without maintaining hardcoded lists of model names.

This enables adding new LPM models without modifying the convolution code,
as long as the new model uses an existing strategy.

Author
------
Jean-Raynald de Dreuzy
"""

from enum import Enum, auto


class ConvolutionStrategy(Enum):
    """
    Enumeration of convolution algorithms available for LPM models.

    Each strategy corresponds to a specific numerical method optimized
    for a particular type of transit time distribution.

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
