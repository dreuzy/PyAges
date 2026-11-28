# Copyright (c) 2021-2026 Centre national de la recherche scientifique (CNRS)
# SPDX-License-Identifier: CECILL-2.1

"""Public exports for the complete bounded-power plugin example.

Normal users do not import this package explicitly: PyAges discovers
``definition`` from the entry point declared in ``pyproject.toml``.
"""

from .model import BoundedPowerLpm, definition

__all__ = ["BoundedPowerLpm", "definition"]
