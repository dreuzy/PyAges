# -*- coding: utf-8 -*-
# Copyright (c) 2021-2026 Centre national de la recherche scientifique (CNRS)
# Contributor: Jean-Raynald de Dreuzy
# SPDX-License-Identifier: CECILL-2.1

"""
Created on Tue May 18 21:14:24 2021
"""

import copy
import os

import numpy as np
import pandas as pd

import pyages.convolution.convolution_tracers as convolution_tracers
from pyages.calibration.problem import CalibrationProblem
from pyages.concentrations.concentrations_time import display_concentration_chronicles
from pyages.config.paths import result_subdirectory
from pyages.config.runtime import DisplayOptions
from pyages.data_io.lpm_results import write_lpm
from pyages.lpm.factory import build_random_lpm


class CalibrationSyntheticTest:
    """Exercise a calibration strategy against generated synthetic cases.

    Each case generates or accepts a target LPM, convolves it with the chosen
    tracers, calibrates the same model family, and stores comparison metrics.
    """

    def __init__(
        self,
        calib_strategy=None,
        ncase=10,
        error=1.0,
        lpm_type="exp",
        tracer_names=None,
        date=2010,
        nmodels=10000,
        display_options=None,
    ):
        """
        Constructor
            Attribute affectations
            Initialization of rng, tracers, storage structure

        Parameters
        ----------
        lpm_type: str
            Type of lpm, active only when lpm_option == "random"
        tracer_names: array of str
            Name of tracers with which the test will be performed
        """
        # Attribute affectations
        self.__lpm_type = lpm_type
        self.__tracer_names = (
            list(tracer_names) if tracer_names is not None else ["cfc11", "kr85"]
        )
        self.__ncase = ncase
        self.__error = error
        self.__date = date
        self.__seed_rng = 1234
        self.__calib_strategy = calib_strategy
        self.__nmodels = nmodels

        # Storage of test results
        self.__display_options = copy.deepcopy(display_options or DisplayOptions())
        # Storage directory
        self.__display_options.directory = result_subdirectory(
            self.__display_options.directory,
            self.__calib_strategy.method + "_" + self.__lpm_type,
        )
        # Initialization of random number generator
        self.rng = np.random.default_rng(self.__seed_rng)
        # Initialization of tracers
        self.tracers = convolution_tracers.ConvolutionTracers(
            names=self.__tracer_names, date=self.__date
        )

        # Initialization of test storage sructure
        self.store = pd.DataFrame(
            columns=[
                "case",
                "error_concentration_%",
                "objective_mean",
                "objective_std",
                "parameter_name",
                "target",
                "estim_mean",
                "estim_std",
                "estim_min",
                "estim_max",
            ]
        )

    def __storage_one_case(self, lpm_target, lpm_calib, i):
        """
        Storage of results in dataframe
        """
        # Statistics on results of parameters
        data = {"case": i}
        lpm_calib.append_target_statistics(lpm_target, data)
        # Adds new line
        if i == 0:
            self.store = pd.DataFrame(data)
        else:
            self.store = pd.concat([self.store, pd.DataFrame(data)])

    def get_directory(self):
        """Return the directory where this synthetic workflow writes outputs."""
        return self.__display_options.directory

    def write_results(self):
        """Write per-case results and descriptive statistics as TSV files."""
        self.store.to_csv(
            os.path.join(self.__display_options.directory, "results.txt"), sep="\t"
        )
        self.store.describe().to_csv(
            os.path.join(self.__display_options.directory, "results_stats.txt"),
            sep="\t",
        )

    def write_parameters_test(self):
        """
        Write tracer names, calibration methods, and calibration parameters.

        File example::

            error	       0.01
            date	       [1990, 2010]
            calibration_method	Simplex
            lpm_type	   ig
            tracer_0	   cfc11
            tracer_1	   Li
        """
        data = {}
        data["error"] = self.__error
        data["date"] = self.__date
        data["calibration_method"] = self.__calib_strategy.method
        data["lpm_type"] = self.__lpm_type
        comp = 0
        for t in self.__tracer_names:
            data["tracer_" + str(comp)] = t
            comp = comp + 1
        path = os.path.join(self.__display_options.directory, "parameters.txt")
        with open(path, "w", encoding="utf-8") as file:
            for key, val in data.items():
                file.write(key + "\t" + str(val) + "\n")

    def perform_one_case(self, i, lpm_random=True, lpm_target=None):
        """Perform one test case with a supplied or randomly generated LPM.

        Parameters
        ----------
        i : int
            Test-case label.
        lpm_random : bool
            Generate an LPM when true; otherwise use ``lpm_target``.
        lpm_target : LpmBase or None
            Target LPM used when ``lpm_random`` is false.

        Returns
        -------
        tuple
            Target LPM, calibration strategy, synthetic concentrations,
            calibrated :class:`~pyages.lpm.samples.table.LpmSampleTable`, and
            Euclidean
            distance between the target parameters and their estimated means.
        """
        # Isolate each case's output directory without mutating shared options.
        display_options_case = copy.deepcopy(self.__display_options)
        display_options_case.directory = result_subdirectory(
            display_options_case.directory, str(i)
        )

        # 1. Generate or validate the target LPM.
        if lpm_random:
            lpm_target = build_random_lpm(self.__lpm_type, rng=self.rng)
        else:
            if lpm_target.name != self.__lpm_type:
                print("Inconsistency between lpm_target and lpm_type, replacement")
                self.__lpm_type = lpm_target.name

        # 2. Convolve the tracers at the configured date to obtain synthetic data.
        cdata = self.tracers.convolve(
            lpm_target,
            return_type="concentrations",
        )
        # Apply the configured uncertainty using the instance's reproducible RNG.
        cdata.error_affect_from_value(self.__error)

        # 3. Prepare a same-family LPM calibration from the synthetic data.
        problem = CalibrationProblem(
            cdata,
            self.__lpm_type,
            display_options=display_options_case,
            sample_count=self.__nmodels,
        ).prepare()
        # 4. Calibrate and analyse the reachable concentrations and objective.
        lpm_results = self.__calib_strategy.run(problem)
        self.__calib_strategy.analysis_calibration(lpm_results)

        # 5. Display and persist the target and calibrated LPMs.
        self.__calib_strategy.display_lpms(
            self.__display_options, lpm_results, lpm_reference=lpm_target
        )
        write_lpm(
            lpm_target,
            os.path.join(display_options_case.directory, "lpm_target.txt"),
        )
        self.__calib_strategy.write_calibrated_lpm(lpm_results)
        cdata.cv.to_csv(
            os.path.join(display_options_case.directory, "concentrations.txt"), sep="\t"
        )
        # Display the concentration histories.
        display_concentration_chronicles(
            cdata,
            lpm_results,
            str(i),
            self.__display_options,
            lpm_number=10,
        )
        # Store per-case summary statistics.
        self.__storage_one_case(lpm_target, lpm_results, i)
        # Compare target parameters with the calibrated distribution mean.
        stats = lpm_results.statistics()
        keys = list(lpm_target.p.keys())
        target_vals = np.array([lpm_target.p[k] for k in keys], dtype=float)
        estim_vals = np.array([stats.loc["mean"][k] for k in keys], dtype=float)
        distance = float(np.linalg.norm(estim_vals - target_vals))
        return lpm_target, self.__calib_strategy, cdata, lpm_results, distance

    def perform_ncase(self):
        """Perform all cases, write their results, and return the mean distance."""
        distances = []
        for i in range(self.__ncase):
            [_, lpm_calibration, _, _, distance] = self.perform_one_case(i)
            distances.append(distance)
        # Write the calibration parameters and aggregate synthetic results.
        lpm_calibration.write_parameters(
            os.path.join(self.__display_options.directory, "parameters_calibration.txt")
        )
        self.write_parameters_test()
        self.write_results()
        if distances:
            return float(np.nanmean(distances))
        return float("nan")
