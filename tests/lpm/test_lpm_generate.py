# -*- coding: utf-8 -*-
"""
Tests for lpm_build utilities.
"""

import pytest

from pyage.lpm.lpm_build import UnknownLPMType, lpm_build


def test_lpm_build_unknown_type_raises():
    with pytest.raises(UnknownLPMType):
        lpm_build("not_a_real_model")
