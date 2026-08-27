# -*- coding: utf-8 -*-
# Copyright (c) 2021-2026 Centre national de la recherche scientifique (CNRS)
# Contributor: Jean-Raynald de Dreuzy
# SPDX-License-Identifier: CECILL-2.1

"""
Tests for LPM factory utilities.
"""

import pytest

from pyages.lpm import build_lpm
from pyages.lpm.factory import UnknownLPMType


def test_build_lpm_unknown_type_raises():
    with pytest.raises(UnknownLPMType):
        build_lpm("not_a_real_model")
