# -*- coding: utf-8 -*-
# Copyright (c) 2021-2026 Centre national de la recherche scientifique (CNRS)
# Contributor: Jean-Raynald de Dreuzy
# SPDX-License-Identifier: CECILL-2.1

"""Synthetic recovery workflow for end-to-end calibration checks.

Each case draws or accepts a target LPM, generates internally consistent tracer
observations, attaches the configured relative uncertainty, and calibrates the
same model family. The workflow persists both scientific inputs and recovery
summaries so differences can be attributed to calibration rather than hidden
data preparation.

The workflow is reusable; the automated assertions that qualify it live under
``tests/``.
"""

import copy
import math
import os
from numbers import Real

import numpy as np
import pandas as pd

from pyages.calibration.problem import CalibrationProblem
from pyages.config.paths import result_subdirectory
from pyages.convolution import ConvolutionTracers
from pyages.data_io.lpm_results import write_lpm
from pyages.lpm.factory import build_random_lpm
from pyages.workflows.concentration_exports import export_calibrated_chronicles


class SyntheticRecoveryWorkflow:
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
        sample_count=10000,
        display_options=None,
    ):
        """Configure reproducible synthetic cases and their output location.

        Parameters
        ----------
        calib_strategy
            Prepared calibration method reused across cases. Its ``run`` method
            binds a fresh :class:`CalibrationProblem` for each case.
        ncase : int
            Number of independently generated target cases.
        error : float
            Relative one-sigma observation uncertainty.
        lpm_type : str
            LPM family generated and recovered.
        tracer_names : iterable of str or None
            Ordered tracer identifiers; defaults to CFC-11 and krypton-85.
        date : float or iterable of float
            Sampling date or dates passed to the tracer convolutions.
        sample_count : int
            Target size for optional systematic parameter exploration.
        display_options : DisplayOptions or None
            Output and rendering policy copied before case-specific paths are
            assigned.

        Notes
        -----
        The target-LPM generator uses a fixed random stream. Calibration methods
        retain their own documented seeds.
        """
        method_name = getattr(calib_strategy, "method", None)
        if not isinstance(method_name, str) or not method_name.strip():
            raise ValueError("calib_strategy must provide a non-empty method name")
        if isinstance(ncase, bool) or not isinstance(ncase, int) or ncase < 1:
            raise ValueError("ncase must be a positive integer")
        if (
            isinstance(sample_count, bool)
            or not isinstance(sample_count, int)
            or sample_count < 1
        ):
            raise ValueError("sample_count must be a positive integer")
        if (
            isinstance(error, bool)
            or not isinstance(error, Real)
            or not math.isfinite(error)
            or error < 0.0
        ):
            raise ValueError("error must be finite and non-negative")
        if not isinstance(lpm_type, str) or not lpm_type.strip():
            raise ValueError("lpm_type must be a non-empty string")
        resolved_tracers = (
            list(tracer_names) if tracer_names is not None else ["cfc11", "kr85"]
        )
        if not resolved_tracers or any(
            not isinstance(tracer, str) or not tracer.strip()
            for tracer in resolved_tracers
        ):
            raise ValueError("tracer_names must contain non-empty strings")
        if (
            display_options is None
            or getattr(display_options, "directory", None) is None
        ):
            raise ValueError("display_options.directory must be configured")

        # Values below define the scientific experiment and remain identical
        # across cases except for the randomly generated target parameters.
        self.__lpm_type = lpm_type.strip()
        self.__tracer_names = [tracer.strip() for tracer in resolved_tracers]
        self.__ncase = ncase
        self.__error = error
        self.__date = date
        self.__seed_rng = 1234
        self.__calib_strategy = calib_strategy
        self._sample_count = sample_count

        # Copy display options so this workflow can derive subdirectories
        # without mutating configuration owned by its caller.
        self.__display_options = copy.deepcopy(display_options)
        self.__display_options.directory = result_subdirectory(
            self.__display_options.directory,
            self.__calib_strategy.method + "_" + self.__lpm_type,
        )
        # One generator makes the sequence of synthetic targets reproducible.
        self.rng = np.random.default_rng(self.__seed_rng)
        # Tracer histories are shared because tracer identities and dates do
        # not change between synthetic cases.
        self.tracers = ConvolutionTracers(names=self.__tracer_names, date=self.__date)

        # Aggregate recovery metrics are accumulated in a stable tabular schema.
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
        """Append target-versus-estimate summaries for one synthetic case."""
        data = {"case": i}
        lpm_calib.append_target_statistics(lpm_target, data)
        # The first case establishes dtypes; later cases preserve that schema.
        if i == 0:
            self.store = pd.DataFrame(data)
        else:
            self.store = pd.concat([self.store, pd.DataFrame(data)])

    def get_directory(self):
        """Return the directory where this synthetic workflow writes outputs."""
        return self.__display_options.directory

    def write_results(self):
        """Write per-case recovery metrics and their descriptive statistics."""
        self.store.to_csv(
            os.path.join(self.__display_options.directory, "results.txt"), sep="\t"
        )
        self.store.describe().to_csv(
            os.path.join(self.__display_options.directory, "results_stats.txt"),
            sep="\t",
        )

    def write_parameters_test(self):
        """Write the synthetic experiment controls as tab-separated metadata.

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
            if lpm_target is None:
                raise ValueError("lpm_target is required when lpm_random is false")
            target_name = getattr(lpm_target, "name", None)
            if target_name != self.__lpm_type:
                raise ValueError(
                    "lpm_target model does not match the configured lpm_type: "
                    f"{target_name!r} != {self.__lpm_type!r}"
                )

        # 2. Convolve the tracers at the configured date to obtain synthetic data.
        observations = self.tracers.convolve(
            lpm_target,
            return_type="concentrations",
        )
        # Assign uncertainty magnitudes; this step does not perturb the central
        # synthetic concentration values.
        observations.set_relative_errors(self.__error)

        # 3. Prepare a same-family LPM calibration from the synthetic data.
        problem = CalibrationProblem(
            observations,
            self.__lpm_type,
            display_options=display_options_case,
            sample_count=self._sample_count,
        ).prepare()
        # 4. Calibrate and analyse the reachable concentrations and objective.
        lpm_results = self.__calib_strategy.run(problem)
        self.__calib_strategy.analysis_calibration(lpm_results)

        # 5. Display and persist the target and calibrated LPMs.
        self.__calib_strategy.display_lpms(
            display_options_case, lpm_results, lpm_reference=lpm_target
        )
        write_lpm(
            lpm_target,
            os.path.join(display_options_case.directory, "lpm_target.txt"),
        )
        self.__calib_strategy.write_calibrated_lpm(lpm_results)
        observations.frame.to_csv(
            os.path.join(display_options_case.directory, "concentrations.txt"),
            sep="\t",
            index=False,
        )
        # Export the tracer histories and calibrated predictions for inspection.
        export_calibrated_chronicles(
            observations,
            lpm_results,
            str(i),
            self.__display_options,
            lpm_number=10,
        )
        # Store per-case recovery summaries before returning detailed objects.
        self.__storage_one_case(lpm_target, lpm_results, i)
        # Compare target parameters with the calibrated distribution mean.
        stats = lpm_results.statistics()
        keys = list(lpm_target.p.keys())
        target_vals = np.array([lpm_target.p[k] for k in keys], dtype=float)
        estim_vals = np.array([stats.loc["mean"][k] for k in keys], dtype=float)
        distance = float(np.linalg.norm(estim_vals - target_vals))
        return lpm_target, self.__calib_strategy, observations, lpm_results, distance

    def perform_ncase(self):
        """Run every configured case and return mean parameter-space distance.

        The Euclidean distance is a compact recovery smoke metric in native
        parameter units. Per-parameter estimates and uncertainties remain the
        scientifically interpretable outputs written by :meth:`write_results`.
        """
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


__all__ = ["SyntheticRecoveryWorkflow"]
