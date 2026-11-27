# -*- coding: utf-8 -*-
# Copyright (c) 2021-2026 Centre national de la recherche scientifique (CNRS)
# Contributor: Jean-Raynald de Dreuzy
# SPDX-License-Identifier: CECILL-2.1

"""
Comparison script for FUQ (Simplex) vs Metropolis-Hastings on synthetic cases.

Purpose
-------
Run synthetic calibrations across multiple LPM types and tracers, compare
FUQ and MH outputs, and write figures + summary files for inspection.

"""

import os
from collections.abc import Iterable

from pyages.calibration.methods.mh import MetropolisHastings, MHConfig
from pyages.calibration.methods.protocols import CalibrationAlgorithm
from pyages.calibration.methods.simplex import Simplex
from pyages.concentrations import Concentrations
from pyages.config.paths import (
    ROOT_DIRECTORY_RESULTS,
    result_subdirectory,
    timestamp_name,
)
from pyages.config.runtime import DisplayOptions, SimulationTimer
from pyages.lpm.core.lpm_base import LpmBase
from pyages.lpm.plotting.sample_diagnostics import (
    plot_concentration_diagnostics,
    plot_parameter_diagnostics,
)
from pyages.lpm.samples.table import LpmSampleTable
from pyages.qualification import SyntheticRecoveryExperiment


class comparison_MH_fuq:
    """
    Series of tested parameters
    """

    def __init__(self):
        self.models_calib = [
            "ig",
            "dirac",
            "exp",
            "exp_shifted",
            "ig_shifted",
            "dirac_double",
            "gamma",
            "uniform",
        ]
        self.display = DisplayOptions()
        self.display.text = False
        self.display.figure = True
        self.display.figure_close = True
        self.display.figure_save = True
        self.fuq_n = 5  # 50
        self.init_multiples_n = 1  # 5
        self.MH_n = 2500
        directory = result_subdirectory(ROOT_DIRECTORY_RESULTS, "test_calib_comp")
        self.directory_root = result_subdirectory(directory, timestamp_name())

    def perform(
        self,
        stime: SimulationTimer,
        ncase: int = 3,
        error: float = 0.04,
        tracer_names: Iterable[str] | None = None,
        lpm_random: bool = True,
        lpm_target: LpmBase | None = None,
        resolution: int = 1000,
    ) -> tuple[
        LpmBase,
        list[LpmSampleTable],
        Concentrations,
        list[CalibrationAlgorithm],
    ]:
        """
        Checks tracers and lpms
        """
        tracer_names = (
            list(tracer_names) if tracer_names is not None else ["kr85", "Li"]
        )
        stime.initialize(len(self.models_calib))
        # OUTPUT File and Directory
        self.display.directory = result_subdirectory(
            self.directory_root, "prec_" + str(error)
        )
        name = ""
        for tracer_name in tracer_names:
            name = name + "_" + tracer_name
        self.display.directory = result_subdirectory(self.display.directory, name)
        date = 2010

        print(
            "\\COMPARISON: FORWARD UNCERTAINTY QUANTIFICATION AND METROPOLIS HASTINGS"
        )
        last_output: (
            tuple[
                LpmBase,
                list[LpmSampleTable],
                Concentrations,
                list[CalibrationAlgorithm],
            ]
            | None
        ) = None
        for lpm in self.models_calib:
            # ---------------- FORWARD UNCERTAINTY QUANTIFICATION -----------------------------
            calib_simplex = Simplex(
                "forward_uncertainty_quantification",
                init_multiples_n=self.init_multiples_n,
                fuq_n=self.fuq_n,
            )
            simplex_experiment = SyntheticRecoveryExperiment(
                calib_strategy=calib_simplex,
                ncase=ncase,
                error=error,
                sample_count=resolution,
                tracer_names=tracer_names,
                date=date,
                lpm_type=lpm,
                display_options=self.display,
            )

            # ---------------- METROPOLIS HASTINGS --------------------
            # Method and Parameters
            mh_config = MHConfig(
                nsteps=self.MH_n,
                prior_option=False,
                likelihood=True,
                record_trajectory=True,
                display_traj=True,
                componentwise_source="model",
            )
            calib_mh = MetropolisHastings(config=mh_config)
            mh_experiment = SyntheticRecoveryExperiment(
                calib_strategy=calib_mh,
                ncase=ncase,
                error=error,
                tracer_names=tracer_names,
                date=date,
                lpm_type=lpm,
                sample_count=resolution,
                display_options=self.display,
            )

            experiments = (simplex_experiment, mh_experiment)

            # Loop on the ncases cases
            for i in range(ncase):
                case_outputs: list[
                    tuple[
                        LpmBase,
                        CalibrationAlgorithm,
                        Concentrations,
                        LpmSampleTable,
                        float,
                    ]
                ] = []
                target_for_case = lpm_target
                for experiment in experiments:
                    result = experiment.perform_one_case(
                        i, lpm_random=lpm_random, lpm_target=target_for_case
                    )
                    target_for_case = result[0]
                    case_outputs.append(result)

                simplex_target, simplex_calibration, _, simplex_results, _ = (
                    case_outputs[0]
                )
                (
                    case_target,
                    mh_calibration,
                    concentration_sampled,
                    mh_results,
                    _,
                ) = case_outputs[1]
                if simplex_target.name != case_target.name or (
                    simplex_target.p != case_target.p
                ):
                    raise RuntimeError(
                        "Simplex and MH must calibrate the same synthetic target"
                    )
                calibrations = [simplex_calibration, mh_calibration]
                results = [simplex_results, mh_results]
                # Outputs and Displays results
                directory_common = result_subdirectory(self.display.directory, lpm)
                directory_common = result_subdirectory(directory_common, str(i))
                plot_parameter_diagnostics(
                    results[0],
                    self_method=calibrations[0].method,
                    lpm_reference=case_target,
                    lpm_2nd=results[1],
                    lpm_2nd_method=calibrations[1].method,
                    directory=directory_common,
                )
                plot_concentration_diagnostics(
                    results[0],
                    self_method=calibrations[0].method,
                    concentrations_reference=concentration_sampled,
                    lpm_2nd=results[1],
                    lpm_2nd_method=calibrations[1].method,
                    directory=directory_common,
                )
                # Analysis of calibration problem
                calibrations[1].problem.analyze()
                # Writes agregated parameters and results
                for experiment, calibration in zip(
                    experiments, calibrations, strict=True
                ):
                    calibration.write_parameters(
                        os.path.join(
                            experiment.get_directory(), "parameters_calibration.txt"
                        )
                    )
                    calibration.write_results(
                        os.path.join(
                            experiment.get_directory(), "results_calibration.txt"
                        )
                    )
                    experiment.write_parameters_test()
                    experiment.write_results()
                # Actualization of simulation time
                stime.actualize()
                last_output = (
                    case_target,
                    results,
                    concentration_sampled,
                    calibrations,
                )

        if last_output is None:
            raise ValueError("At least one LPM and one case are required")
        return last_output


# ----------------------------------------------
# ----------------- LAUNNCHERS -----------------
# ----------------------------------------------


def test_calibration_MH_fuq():
    comp = comparison_MH_fuq()
    stime = SimulationTimer(nsim=6)
    comp.perform(
        stime, ncase=2, error=0.04, tracer_names=["cfc11", "kr85"], resolution=10000
    )
    comp.perform(
        stime, ncase=5, error=0.04, tracer_names=["kr85", "Li"], resolution=10000
    )
    comp.perform(
        stime, ncase=5, error=0.001, tracer_names=["cfc11", "kr85"], resolution=10000
    )
    comp.perform(
        stime, ncase=5, error=0.001, tracer_names=["kr85", "Li"], resolution=10000
    )
    comp.perform(
        stime, ncase=5, error=0.04, tracer_names=["cfc11", "Li"], resolution=10000
    )
    comp.perform(
        stime, ncase=5, error=0.001, tracer_names=["cfc11", "Li"], resolution=10000
    )


if __name__ == "__main__":
    # execute only if run as a script
    test_calibration_MH_fuq()
