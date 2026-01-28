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
    CLASSIC : enum
        Standard numerical integration using Simpson's rule.
        Suitable for smooth distributions (uniform, gamma, inverse gaussian).

    DIRAC : enum
        Direct lookup in the recharge chronicle.
        For delta function distributions (single spike).

    DIRAC_DOUBLE : enum
        Weighted combination of two direct lookups.
        For bi-modal delta function distributions.

    EXPONENTIAL : enum
        Adapted discretization near the distribution discontinuity.
        For exponential and shifted exponential distributions.

    MIX_DIRAC_EXPONENTIAL : enum
        Weighted combination of Dirac and exponential strategies.
        For mixed distributions with both spike and tail components.
    """

    CLASSIC = auto()
    DIRAC = auto()
    DIRAC_DOUBLE = auto()
    EXPONENTIAL = auto()
    MIX_DIRAC_EXPONENTIAL = auto()

    def requires_dirac_time(self) -> bool:
        """
        Check if this strategy requires the get_dirac_time() method.

        Returns
        -------
        bool
            True if the LPM must implement get_dirac_time().
        """
        return self in {
            ConvolutionStrategy.DIRAC,
            ConvolutionStrategy.MIX_DIRAC_EXPONENTIAL,
        }

    def requires_dirac_double_time(self) -> bool:
        """
        Check if this strategy requires the get_dirac_double_time() method.

        Returns
        -------
        bool
            True if the LPM must implement get_dirac_double_time().
        """
        return self == ConvolutionStrategy.DIRAC_DOUBLE

    def requires_shift_parameter(self) -> bool:
        """
        Check if this strategy requires a 'shift' parameter.

        Returns
        -------
        bool
            True if the LPM must have a 'shift' parameter.
        """
        return self in {
            ConvolutionStrategy.EXPONENTIAL,
            ConvolutionStrategy.MIX_DIRAC_EXPONENTIAL,
        }

    def is_special(self) -> bool:
        """
        Check if this strategy requires special handling (not classic).

        Returns
        -------
        bool
            True if this is not the CLASSIC strategy.
        """
        return self != ConvolutionStrategy.CLASSIC

    @property
    def description(self) -> str:
        """
        Human-readable description of the strategy.

        Returns
        -------
        str
            Description of what this strategy does.
        """
        descriptions = {
            ConvolutionStrategy.CLASSIC: (
                "Standard numerical integration (Simpson's rule) for smooth distributions"
            ),
            ConvolutionStrategy.DIRAC: (
                "Direct chronicle lookup for delta function distributions"
            ),
            ConvolutionStrategy.DIRAC_DOUBLE: (
                "Weighted combination of two chronicle lookups for bi-modal deltas"
            ),
            ConvolutionStrategy.EXPONENTIAL: (
                "Adapted discretization near discontinuity for exponential distributions"
            ),
            ConvolutionStrategy.MIX_DIRAC_EXPONENTIAL: (
                "Weighted combination of Dirac lookup and exponential integration"
            ),
        }
        return descriptions.get(self, "Unknown strategy")
