# Copyright (c) 2021-2026 Centre national de la recherche scientifique (CNRS)
# Contributor: Jean-Raynald de Dreuzy
# SPDX-License-Identifier: CECILL-2.1
# This file keeps the top-level package API deliberately small by exposing only
# the installed version string. Scientific objects remain in their subpackages,
# so importing ``pyages`` does not initialize calibration or plotting code.

"""Public package metadata for PyAges.

Scientific APIs are exposed by their focused subpackages, for example
``pyages.convolution``. Keeping the package root small avoids accidental API
commitments while the first stable release is prepared.
"""

from pyages._version import __version__

__all__ = ["__version__"]
