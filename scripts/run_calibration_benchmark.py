# -*- coding: utf-8 -*-
"""
Comparison script for FUQ (Simplex) vs Metropolis-Hastings on synthetic cases.

Purpose
-------
Run synthetic calibrations across multiple LPM types and tracers, compare
FUQ and MH outputs, and write figures + summary files for inspection.

Author
------
Jean-Raynald de Dreuzy
"""

import os

import pyage.calibration.methods.metropolis_hastings as cMH
import pyage.calibration.methods.simplex as csimp
import pyage.calibration.workflows.synthetic_test as cst
from pyage.config.paths import (
    ROOT_DIRECTORY_RESULTS,
    result_subdirectory,
    timestamp_name,
)
from pyage.config.runtime import DisplayOptions, SimulationTimer
from pyage.lpm.distribution_plotting import (
    display_concentration_distributions,
    display_parameter_distributions,
)


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
        stime,
        ncase=3,
        error=0.04,
        tracer_names=None,
        lpm_random=True,
        lpm_target=None,
        resolution=1000,
    ):
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
        for lpm in self.models_calib:
            calstrat = [None] * 2
            # ---------------- FORWARD UNCERTAINTY QUANTIFICATION -----------------------------
            calib_simplex = csimp.Simplex(
                "forward_uncertainty_quantification",
                init_multiples_n=self.init_multiples_n,
                fuq_n=self.fuq_n,
            )
            calstrat[0] = cst.CalibrationSyntheticTest(
                calib_strategy=calib_simplex,
                ncase=ncase,
                error=error,
                nmodels=resolution,
                tracer_names=tracer_names,
                date=date,
                lpm_type=lpm,
                display_options=self.display,
            )

            # ---------------- METROPOLIS HASTINGS --------------------
            # Method and Parameters
            mh_config = cMH.MHConfig(
                nstep=self.MH_n,
                prior_option=False,
                likelihood=True,
                monitor=True,
                display_traj=True,
                componentwise_source="model",
            )
            calib_MH = cMH.MetropolisHastings(config=mh_config)  # JR: 250000
            calstrat[1] = cst.CalibrationSyntheticTest(
                calib_strategy=calib_MH,
                ncase=ncase,
                error=error,
                tracer_names=tracer_names,
                date=date,
                lpm_type=lpm,
                nmodels=resolution,
                display_options=self.display,
            )

            # Loop on the ncases cases
            for i in range(ncase):
                lpm_calibration = [None] * 2
                lpm_results = [None] * 2
                # Performs calibration
                for j in range(len(calstrat)):
                    [
                        lpm_target,
                        lpm_calibration[j],
                        concentration_sampled,
                        lpm_results[j],
                        _,
                    ] = calstrat[j].perform_one_case(
                        i, lpm_random=lpm_random, lpm_target=lpm_target
                    )
                # Outputs and Displays results
                directory_common = result_subdirectory(self.display.directory, lpm)
                directory_common = result_subdirectory(directory_common, str(i))
                display_parameter_distributions(
                    lpm_results[0],
                    self_method=lpm_calibration[0].method,
                    lpm_reference=lpm_target,
                    lpm_2nd=lpm_results[1],
                    lpm_2nd_method=lpm_calibration[1].method,
                    directory=directory_common,
                )
                display_concentration_distributions(
                    lpm_results[0],
                    self_method=lpm_calibration[0].method,
                    concentrations_reference=concentration_sampled,
                    lpm_2nd=lpm_results[1],
                    lpm_2nd_method=lpm_calibration[1].method,
                    directory=directory_common,
                )
                # Analysis of calibration problem
                lpm_calibration[1].analysis_calibration()
                # Writes agregated parameters and results
                for k in range(len(lpm_calibration)):
                    lpm_calibration[k].write_parameters(
                        os.path.join(
                            calstrat[k].get_directory(), "parameters_calibration.txt"
                        )
                    )
                    lpm_calibration[k].write_results(
                        os.path.join(
                            calstrat[k].get_directory(), "results_calibration.txt"
                        )
                    )
                    calstrat[k].write_parameters_test()
                    calstrat[k].write_results()
                # Actualization of simulation time
                stime.actualize()

        return [lpm_target, lpm_results, concentration_sampled, lpm_calibration]


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
