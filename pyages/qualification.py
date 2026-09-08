# Copyright (c) 2021-2026 Centre national de la recherche scientifique (CNRS)
# Contributor: Jean-Raynald de Dreuzy
# SPDX-License-Identifier: CECILL-2.1
# This file checks a complete calibration workflow with synthetic observations
# generated from known model parameters. It recalibrates each case and writes
# the recovered parameters and errors so scientific regressions can be detected.

"""Synthetic recovery qualification for end-to-end calibration checks.

Each case draws or accepts a target LPM, generates internally consistent tracer
observations, attaches the configured relative uncertainty, and calibrates the
same model family. The experiment persists both scientific inputs and recovery
summaries so differences can be attributed to calibration rather than hidden
data preparation.

The experiment is reusable; the automated assertions that qualify it live under
``tests/``.
"""

from __future__ import annotations

import copy
import math
from collections.abc import Iterable
from numbers import Real
from pathlib import Path

import numpy as np
import pandas as pd

from pyages.calibration.methods.protocols import CalibrationAlgorithm
from pyages.calibration.outputs import (
    display_calibrated_models,
    write_calibrated_result,
)
from pyages.calibration.problem import CalibrationProblem
from pyages.concentrations import Concentrations
from pyages.config.paths import result_subdirectory
from pyages.config.runtime import DisplayOptions
from pyages.convolution import ConvolutionTracers
from pyages.data_io.concentrations import save_concentrations_table
from pyages.data_io.lpm_results import write_lpm
from pyages.lpm.core.lpm_base import LpmBase
from pyages.lpm.factory import build_random_lpm
from pyages.lpm.samples.table import LpmSampleTable
from pyages.reporting.chronicles import export_calibrated_chronicles


class SyntheticRecoveryExperiment:
    """Exercise a calibration strategy against generated synthetic cases.

    Each case generates or accepts a target LPM, convolves it with the chosen
    tracers, calibrates the same model family, and stores comparison metrics.
    """

    def __init__(
        self,
        calib_strategy: CalibrationAlgorithm | None = None,
        ncase: int = 10,
        error: float = 1.0,
        lpm_type: str = "exp",
        tracer_names: Iterable[str] | None = None,
        date: float | Iterable[float] = 2010,
        sample_count: int = 10000,
        display_options: DisplayOptions | None = None,
    ) -> None:
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
        if calib_strategy is None:
            raise ValueError("calib_strategy must provide a non-empty method name")
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
        if display_options is None or display_options.directory is None:
            raise ValueError("display_options.directory must be configured")
        display_directory = display_options.directory

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

        # Copy display options so this experiment can derive subdirectories
        # without mutating configuration owned by its caller.
        self.__display_options = copy.deepcopy(display_options)
        self.__directory = result_subdirectory(
            display_directory,
            method_name + "_" + self.__lpm_type,
        )
        self.__display_options.directory = self.__directory
        # One generator makes the sequence of synthetic targets reproducible.
        self.rng = np.random.default_rng(self.__seed_rng)
        # Tracer histories are shared because tracer identities and dates do
        # not change between synthetic cases.
        self.tracers = ConvolutionTracers(names=self.__tracer_names, date=self.__date)

        # Aggregate recovery metrics are accumulated in a stable tabular schema.
        self.store = pd.DataFrame(
            columns=pd.Index(
                [
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
        )

    def __storage_one_case(
        self,
        lpm_target: LpmBase,
        lpm_calib: LpmSampleTable,
        i: int,
    ) -> None:
        """Append target-versus-estimate summaries for one synthetic case."""
        data = {"case": i}
        lpm_calib.append_target_statistics(lpm_target, data)
        # The first case establishes dtypes; later cases preserve that schema.
        if i == 0:
            self.store = pd.DataFrame(data)
        else:
            self.store = pd.concat([self.store, pd.DataFrame(data)])

    def get_directory(self) -> Path:
        """Return the directory where this synthetic experiment writes outputs."""
        return self.__directory

    def write_results(self) -> None:
        """Write per-case recovery metrics and their descriptive statistics."""
        self.store.to_csv(self.__directory / "results.txt", sep="\t")
        self.store.describe().to_csv(
            self.__directory / "results_stats.txt",
            sep="\t",
        )

    def write_parameters_test(self) -> None:
        """Write the synthetic experiment controls as tab-separated metadata.

        File example::

            error	       0.01
            date	       [1990, 2010]
            calibration_method	Simplex
            lpm_type	   ig
            tracer_0	   cfc11
            tracer_1	   Li
        """
        data: dict[str, object] = {}
        data["error"] = self.__error
        data["date"] = self.__date
        data["calibration_method"] = self.__calib_strategy.method
        data["lpm_type"] = self.__lpm_type
        comp = 0
        for t in self.__tracer_names:
            data["tracer_" + str(comp)] = t
            comp = comp + 1
        path = self.__directory / "parameters.txt"
        with open(path, "w", encoding="utf-8") as file:
            for key, val in data.items():
                file.write(key + "\t" + str(val) + "\n")

    def perform_one_case(
        self,
        i: int,
        lpm_random: bool = True,
        lpm_target: LpmBase | None = None,
    ) -> tuple[
        LpmBase,
        CalibrationAlgorithm,
        Concentrations,
        LpmSampleTable,
        float,
    ]:
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
        case_directory = result_subdirectory(self.__directory, str(i))
        display_options_case.directory = case_directory

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
        problem.analyze(lpm_results)

        # 5. Display and persist the target and calibrated LPMs.
        display_calibrated_models(
            self.__calib_strategy,
            problem,
            lpm_results,
            display_options_case,
            reference=lpm_target,
        )
        write_lpm(
            lpm_target,
            case_directory / "lpm_target.txt",
        )
        write_calibrated_result(self.__calib_strategy, problem, lpm_results)
        save_concentrations_table(
            observations.frame,
            case_directory / "concentrations.txt",
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

    def perform_ncase(self) -> float:
        """Run every configured case and return mean parameter-space distance.

        The Euclidean distance is a compact recovery smoke metric in native
        parameter units. Per-parameter estimates and uncertainties remain the
        scientifically interpretable outputs written by :meth:`write_results`.
        """
        distances = []
        for i in range(self.__ncase):
            [_, _, _, _, distance] = self.perform_one_case(i)
            distances.append(distance)
        # Write the calibration parameters and aggregate synthetic results.
        self.__calib_strategy.write_parameters(
            self.__directory / "parameters_calibration.txt"
        )
        self.write_parameters_test()
        self.write_results()
        if distances:
            return float(np.nanmean(distances))
        return float("nan")


__all__ = ["SyntheticRecoveryExperiment"]
