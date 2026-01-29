# -*- coding: utf-8 -*-
"""
Tests for lpm_build utilities.
"""

import pytest

from pyage.LPM.lpm_build import lpm_build, UnknownLPMType


def test_lpm_build_unknown_type_raises():
    with pytest.raises(UnknownLPMType):
        lpm_build("not_a_real_model")
