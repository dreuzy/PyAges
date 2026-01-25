"""
Prior-only MH validation checks with tolerance thresholds.
"""

import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
SRC_DIR = REPO_ROOT / "sources"
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

import global_parameters as gp
from calibration.methods.metropolis_hastings import MHConfig, MetropolisHastings
from calibration.workflows import synthetic_test as cst



@pytest.mark.parametrize("lpm_type", ["exp", "ig", "ig_shifted", "gamma"])
def test_calibration_mh_prior_validation_tolerances(tmp_path: Path, lpm_type: str):
    display = gp.display_options()
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
        lpm_number=3,
    )
    calib_mh = MetropolisHastings(config=mh_config)

    calib = cst.CalibrationSyntheticTest(
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
    for key, values in stats["difference_percent"].items():
        assert abs(values["mean"]) < tolerance
        assert abs(values["var"]) < tolerance
