# Copyright (c) 2021-2026 Centre national de la recherche scientifique (CNRS)
# Contributor: Jean-Raynald de Dreuzy
# SPDX-License-Identifier: CECILL-2.1

"""Public package metadata for PyAges.

Scientific APIs are exposed by their focused subpackages, for example
``pyages.convolution``. Keeping the package root small avoids accidental API
commitments while the first stable release is prepared.
"""

from pyages._version import __version__

__all__ = ["__version__"]
