# -*- coding: utf-8 -*-
"""
Tests for LPM_generate utilities.
"""

import pytest

from LPM.LPM_generate import LPM_generate, UnknownLPMType


def test_lpm_generate_unknown_type_raises():
    with pytest.raises(UnknownLPMType):
        LPM_generate("not_a_real_model")
