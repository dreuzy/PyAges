# -*- coding: utf-8 -*-
# Copyright (c) 2021-2026 Centre national de la recherche scientifique (CNRS)
# Contributor: Jean-Raynald de Dreuzy
# SPDX-License-Identifier: CECILL-2.1

"""
Integration test script (manual/interactive).

Runs broad, slow checks across LPM generation and calibration methods.
Not intended for CI; use pytest for automated regression testing.

"""

import argparse
from pathlib import Path
from typing import Optional

import yaml
from pydantic import ValidationError

from pyages.calibration.methods.mh import MetropolisHastings, MHConfig
from pyages.calibration.methods.simplex import Simplex
from pyages.config.models import SystemCheckConfig
from pyages.config.paths import (
    ROOT_DIRECTORY_RESULTS,
    result_subdirectory,
    timestamp_name,
)
from pyages.config.runtime import DisplayOptions
from pyages.lpm.reporting import run_model_diagnostic
from pyages.workflows.synthetic_recovery import SyntheticRecoveryWorkflow


class TestIntegration:
    """
    Extensive tests for PyAges

    Arguments
         ---------
    date: float
        date(year) at which convolutions are computed taken

    Attributes, public
    ----------
    __date: float
        date(year) at which convolutions are computed taken
    LPM_all : array of str
        list of all LPM models
    LPM_calib : array of str
        list of LPM on which calibration is tested
    tracers_all : array of str
        list of all Tracers
    tracers_conv: array of str
        list of Tracers on which convolution functions are tested
    tracers_calib: array of str
        list of Tracers on which calibration functions are tested
    reachable_resolution : int
        Number of iteration allowed for the computation of reachable concentrations
    display: DisplayOptions
        display options


    Methods (principal)
    -------
    __init__(self)
        Constructor: main parameter tests

    """

    def __init__(self, config: Optional[SystemCheckConfig] = None):
        cfg = config or SystemCheckConfig()
        self.LPM_all = cfg.lpm_all
        self.LPM_calib = cfg.lpm_calib
        self.tracers_all = cfg.tracers_all
        self.tracers_conv = cfg.tracers_conv
        self.tracers_calib = cfg.tracers_calib
        # Reachable Concentrations
        self.reachable_resolution = cfg.reachable_resolution
        # Output options
        self.display = DisplayOptions()
        self.display_set(single_all="all")
        self.__date = cfg.date

    def display_set(self, single_all="all"):
        """
        Display options for single or all tests
            single: all display options activated
            all: no options activated
        """
        self.display.figure_save = True
        self.display.figure = True
        if single_all == "single":
            self.display.text = True
            self.display.figure_close = True
        else:
            self.display.text = False
            self.display.figure_close = True

    def folder_results(self, folder_name):
        """
        Location and creation of results folder
            ROOT_DIRECTORY_RESULTS / "test" / folder_name
        """
        directory = result_subdirectory(ROOT_DIRECTORY_RESULTS, "test")
        directory = result_subdirectory(directory, folder_name)
        self.display.directory = result_subdirectory(directory, timestamp_name())

    def check_lpms(self, single_all="all", single_name=""):
        """
        Checks lpms
            Successive "GENERATE", "CONVOLUTION" and "REACHABLE CONCENTRATIONS"
                testing enables the modulation of the order of functionality tested
            Method with single lpm is used typically when a new lpm is developed

        Arguments
        ---------
        single_all: str
            "single": test for a single lpm
            "all": test for all lpms
        single_name: str
            Name of LPM tested
        """

        # Nature of the test
        if single_all == "single":
            lpm_list = [single_name]
        else:
            lpm_list = self.LPM_all

        self.display_set(single_all)
        self.folder_results("integration_LPMs")

        print("\nGENERATE AND DISPLAY LPM")
        for t in lpm_list:
            run_model_diagnostic(t, display_options=self.display)

    def check_calibration(self, single_all="all", single_name=""):
        """
        Checks calibration
            All calibration methods checked

        Arguments
        ---------
        single_all: str
            "single": test for a single lpm
            "all": all calibrated models
        single_name: str
            Name of lpm
        """

        # Nature of the test
        if single_all == "single":
            lpm_list = [single_name]
        else:
            lpm_list = self.LPM_calib

        self.display_set(single_all)
        self.folder_results("integration_calibration")

        tracer_names = ["cfc11", "Li"]
        # date for each of the tracers
        date = [1990, 2010]

        print("\nCALIBRATION ON SYNTETIC CASES: METROPOLIS-HASTINGS")
        for lpm in lpm_list:
            mh_config = MHConfig(
                nstep=2000,
                prior_option=True,
                prior_type="parametric",
                likelihood=True,
                monitor=False,
            )
            calib_mh = MetropolisHastings(config=mh_config)
            calib = SyntheticRecoveryWorkflow(
                calib_strategy=calib_mh,
                ncase=2,
                error=0.03,
                tracer_names=tracer_names,
                date=date,
                lpm_type=lpm,
                display_options=self.display,
                sample_count=500,
            )
            calib.perform_ncase()

        print("\nCALIBRATION ON SYNTETIC CASES: SIMPLEX_INIT_MULTIPLES")
        lpm_list_simplex = [
            lpm for lpm in lpm_list if lpm not in ("ig_shifted", "uniform")
        ]
        for lpm in lpm_list_simplex:
            calib_simplex = Simplex("Simplex_multi_start", init_multiples_n=10)
            calib = SyntheticRecoveryWorkflow(
                calib_strategy=calib_simplex,
                ncase=2,
                error=0.001,
                tracer_names=tracer_names,
                date=date,
                lpm_type=lpm,
                display_options=self.display,
                sample_count=10,
            )
            calib.perform_ncase()

        print("\nCALIBRATION ON SYNTETIC CASES: SIMPLEX")
        # Does not work for ig_shifted (3 parameters) and for uniform
        for lpm in lpm_list_simplex:
            calib_simplex = Simplex("Simplex")
            calib = SyntheticRecoveryWorkflow(
                calib_strategy=calib_simplex,
                ncase=2,
                error=0.01,
                tracer_names=tracer_names,
                date=date,
                lpm_type=lpm,
                display_options=self.display,
                sample_count=10,
            )
            calib.perform_ncase()

        print("\nCALIBRATION ON SYNTETIC CASES: FORWARD UNCERTAINTY QUANTIFICATION")
        for lpm in lpm_list:
            calib_simplex = Simplex(
                "forward_uncertainty_quantification", init_multiples_n=2, fuq_n=2
            )
            calib = SyntheticRecoveryWorkflow(
                calib_strategy=calib_simplex,
                ncase=2,
                error=0.04,
                tracer_names=tracer_names,
                date=date,
                lpm_type=lpm,
                display_options=self.display,
            )
            calib.perform_ncase()

        # Prior-only MH validation is covered by the pytest suite.


# ----------------------------------------------
# ----------------- LAUNNCHERS -----------------
# ----------------------------------------------


def _load_config(path: Optional[Path]) -> SystemCheckConfig:
    """
    Load optional YAML configuration for the integration test script.
    """
    if path is None:
        return SystemCheckConfig()
    data = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    try:
        return SystemCheckConfig.model_validate(data)
    except ValidationError as exc:
        raise ValueError(f"Invalid system check config:\n{exc}") from exc


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run PyAges integration checks.")
    parser.add_argument(
        "--params",
        type=Path,
        default=None,
        help="Optional YAML file to override integration test settings.",
    )
    return parser.parse_args()


def test_integration(config: Optional[SystemCheckConfig] = None):
    # Simple test functions: exhaustive tracer or lpm
    ti = TestIntegration(config=config)
    ti.check_lpms(single_all="all")

    # Simple test functions: single tracer or lpm
    ti = TestIntegration(config=config)
    ti.check_lpms(single_all="single", single_name="dirac_double_1_set")

    # Checks calibration
    ti = TestIntegration(config=config)
    ti.check_calibration(single_all="all")


if __name__ == "__main__":
    args = _parse_args()
    cfg = _load_config(args.params)
    test_integration(config=cfg)
