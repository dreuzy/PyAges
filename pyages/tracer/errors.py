# Copyright (c) 2021-2026 Centre national de la recherche scientifique (CNRS)
# Contributor: Jean-Raynald de Dreuzy
# SPDX-License-Identifier: CECILL-2.1

"""Domain errors raised while loading tracer definitions."""


class TracerConfigError(Exception):
    """A tracer YAML file is readable but contains an invalid definition."""


class TracerDataError(Exception):
    """A tracer configuration or chronicle file cannot be read."""
