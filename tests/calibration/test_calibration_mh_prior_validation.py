# Copyright (c) 2021-2026 Centre national de la recherche scientifique (CNRS)
# Contributor: Jean-Raynald de Dreuzy
# SPDX-License-Identifier: CECILL-2.1

"""
Prior-only MH validation checks with tolerance thresholds.
"""

from pathlib import Path

import pytest

from pyages.calibration.methods.mh import MetropolisHastings, MHConfig
from pyages.config.runtime import DisplayOptions
from pyages.workflows.synthetic_recovery import SyntheticRecoveryWorkflow


@pytest.mark.parametrize("lpm_type", ["exp", "ig", "ig_shifted", "gamma"])
def test_calibration_mh_prior_validation_tolerances(tmp_path: Path, lpm_type: str):
    display = DisplayOptions()
    display.figure = False
    display.text = False
    display.figure_save = False
    display.directory = tmp_path / lpm_type

    mh_config = MHConfig(
        nstep=2000,
        burn_in=0.2,
        nskip=5,
        prior_option=True,
        likelihood=False,
        monitor=False,
        display_traj=False,
        display_text=False,
    )
    calib_mh = MetropolisHastings(config=mh_config)

    calib = SyntheticRecoveryWorkflow(
        calib_strategy=calib_mh,
        ncase=1,
        error=0.0,
        tracer_names=["cfc11"],
        date=2000,
        lpm_type=lpm_type,
        display_options=display,
    )

    calib.perform_ncase()

    stats = calib_mh.prior_validation_stats
    assert stats is not None
    assert "difference_percent" in stats

    tolerance = 100.0
    for _key, values in stats["difference_percent"].items():
        assert abs(values["mean"]) < tolerance
        assert abs(values["var"]) < tolerance
