# Copyright (c) 2021-2026 Centre national de la recherche scientifique (CNRS)
# Contributor: Jean-Raynald de Dreuzy
# SPDX-License-Identifier: CECILL-2.1

"""
Smoke test for MH prior-only calibration.

Based on calibration.test_calibration_MH_prior, but with reduced settings
to keep the test fast and deterministic.
"""

from pathlib import Path

from pyages.calibration.methods.metropolis_hastings import MetropolisHastings, MHConfig
from pyages.calibration.workflows import synthetic_test as cst
from pyages.config.runtime import DisplayOptions


def test_calibration_mh_prior_smoke(tmp_path: Path):
    display = DisplayOptions()
    display.figure = False
    display.text = False
    display.figure_save = False
    display.directory = tmp_path

    mh_config = MHConfig(
        nstep=50,
        burn_in=0.2,
        nskip=5,
        prior_option=True,
        likelihood=False,
        monitor=False,
        display_traj=False,
        display_text=False,
    )
    calib_mh = MetropolisHastings(config=mh_config)

    calib = cst.CalibrationSyntheticTest(
        calib_strategy=calib_mh,
        ncase=1,
        error=0.0,
        tracer_names=["cfc11"],
        date=2000,
        lpm_type="exp",
        display_options=display,
    )

    calib.perform_ncase()
