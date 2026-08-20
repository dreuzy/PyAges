"""Public package metadata for PyAge.

Scientific APIs are exposed by their focused subpackages, for example
``pyage.convolution``. Keeping the package root small avoids accidental API
commitments while the first stable release is prepared.
"""

from pyage._version import __version__

__all__ = ["__version__"]
