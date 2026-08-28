# Copyright (c) 2021-2026 Centre national de la recherche scientifique (CNRS)
# Contributor: Jean-Raynald de Dreuzy
# SPDX-License-Identifier: CECILL-2.1

"""
Golden tests for Metropolis-Hastings calibration.

Targets:
- LPM types: exp, ig
- Tracers: cfc11, cfc12, cfc113
- Fixed nstep for reproducibility
"""

from pathlib import Path

import numpy as np
import pytest

from pyages.calibration.exploration.systematic import SystematicSampling
from pyages.calibration.methods.mh import MetropolisHastings, MHConfig
from pyages.config.runtime import DisplayOptions
from pyages.workflows.synthetic_recovery import SyntheticRecoveryWorkflow
from tests.utils import golden as golden_utils
from tests.utils import paths as test_paths

# Test matrix
LPM_TYPES = ["exp", "ig"]
TRACER_NAMES = ["cfc11", "cfc12", "cfc113"]
NSTEP = 500
NMODELS = 50
PRIOR_MODES = ["full", "prior_only"]
REACHCONC_TRACERS = ["cfc11", "cfc12", "cfc113"]


def _golden_path() -> Path:
    # Golden values for MH calibration
    return test_paths.repo_root() / "tests" / "golden" / "calibration_mh_values.json"


def _run_mh_one_case(
    lpm_type: str,
    tracer_name: str,
    work_dir: Path,
    prior_only: bool,
) -> dict:
    # Minimal, deterministic MH run to collect summary stats
    display = DisplayOptions()
    display.figure = False
    display.text = False
    display.directory = work_dir

    # Configure MH calibration (fixed nstep for reproducibility)
    mh_config = MHConfig(
        nstep=NSTEP,
        burn_in=0.2,
        nskip=10,
        prior_option=True,
        prior_type="parametric",
        likelihood=not prior_only,
        monitor=False,
        display_traj=False,
        display_text=False,
    )
    calib_mh = MetropolisHastings(config=mh_config)

    # Synthetic calibration setup (single case)
    calib = SyntheticRecoveryWorkflow(
        calib_strategy=calib_mh,
        ncase=1,
        error=0.03,
        tracer_names=[tracer_name],
        date=2010,
        lpm_type=lpm_type,
        display_options=display,
        sample_count=NMODELS,
    )

    # Run one synthetic case and extract stats
    _, _, _, lpm_results, _ = calib.perform_one_case(0)
    lpm_results.validate()
    stats = lpm_results.statistics()

    # Record stable summary values for golden checks
    record = {
        "obj_mean": float(stats.loc["mean"]["obj_function"]),
        "obj_std": float(stats.loc["std"]["obj_function"]),
    }
    # Include parameter summaries for the current LPM type
    for key in lpm_results.lpm_template.p:
        record[f"{key}_mean"] = float(stats.loc["mean"][key])
        record[f"{key}_std"] = float(stats.loc["std"][key])
    return record


def _run_reachconc_mean(lpm_type: str, work_dir: Path) -> dict:
    # Deterministic reachable concentrations mean values
    display = DisplayOptions()
    display.figure = False
    display.text = False
    display.directory = work_dir

    cr = SystematicSampling(
        lpm_type,
        REACHCONC_TRACERS,
        date=[2010] * len(REACHCONC_TRACERS),
        sample_count=NMODELS,
        display_options=display,
        explore_reachable=False,
    )
    cr.compute_concentrations()

    concentrations = cr.concentrations_frame()
    means = concentrations.mean()
    return {f"{name}_mean": float(value) for name, value in means.items()}


@pytest.mark.parametrize("lpm_type", LPM_TYPES)
@pytest.mark.parametrize("tracer_name", TRACER_NAMES)
@pytest.mark.parametrize("prior_mode", PRIOR_MODES)
def test_calibration_mh_golden(
    lpm_type,
    tracer_name,
    prior_mode,
    update_golden,
    tmp_path,
):
    # Golden test for MH calibration outputs
    prior_only = prior_mode == "prior_only"
    record = _run_mh_one_case(
        lpm_type,
        tracer_name,
        tmp_path / "calibration_mh",
        prior_only=prior_only,
    )

    key = f"mh:{lpm_type}:{tracer_name}:{prior_mode}:nstep={NSTEP}"
    store = golden_utils.load_golden(_golden_path())

    if update_golden:
        # Update reference values on demand
        store[key] = record
        golden_utils.save_golden(_golden_path(), store)
        pytest.skip(f"Golden updated for {key}")

    if key not in store:
        pytest.fail(f"Golden value missing for {key}. Run: pytest -s --update-golden")

    expected = store[key]
    # Compare all stored keys
    for k, v in record.items():
        assert v == pytest.approx(expected[k], rel=1e-6, abs=1e-6)


@pytest.mark.parametrize("lpm_type", LPM_TYPES)
def test_reachconc_mean_golden(lpm_type, update_golden, tmp_path):
    # Golden test for reachable concentrations mean values
    record = _run_reachconc_mean(lpm_type, tmp_path / "reachconc")

    key = (
        f"reachmean:{lpm_type}:tracers={','.join(REACHCONC_TRACERS)}:nmodels={NMODELS}"
    )
    store = golden_utils.load_golden(_golden_path())

    if update_golden:
        # Update reference values on demand
        store[key] = record
        golden_utils.save_golden(_golden_path(), store)
        pytest.skip(f"Golden updated for {key}")

    if key not in store:
        pytest.fail(f"Golden value missing for {key}. Run: pytest -s --update-golden")

    expected = store[key]
    for k, v in record.items():
        assert v == pytest.approx(expected[k], rel=1e-6, abs=1e-6)


@pytest.mark.extensive
@pytest.mark.parametrize("lpm_type", ["exp", "ig", "exp_shifted", "ig_shifted"])
def test_calibration_mh_extensive(lpm_type, tmp_path):
    """
    Long-running MH calibration with multiple tracers and cases.

    This test is opt-in via --run-extensive.
    """
    display = DisplayOptions()
    display.figure = True
    display.text = True
    display.figure_save = True
    display.directory = tmp_path / "calibration_mh_extensive"

    mh_config = MHConfig(
        nstep=500,
        burn_in=0.2,
        nskip=10,
        prior_option=True,
        prior_type="parametric",
        likelihood=True,
        monitor=False,
        display_traj=False,
        display_text=False,
    )
    calib_mh = MetropolisHastings(config=mh_config)

    calib = SyntheticRecoveryWorkflow(
        calib_strategy=calib_mh,
        ncase=5,
        error=0.03,
        tracer_names=TRACER_NAMES,
        date=2010,
        lpm_type=lpm_type,
        display_options=display,
        sample_count=200,
    )

    mean_distance = calib.perform_ncase()
    assert np.isfinite(mean_distance)
