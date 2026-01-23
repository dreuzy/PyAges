import sys
import os
import copy
from pathlib import Path

import matplotlib

try:
    from IPython import get_ipython
    ipy = get_ipython()
    if ipy is not None:
        ipy.run_line_magic("matplotlib", "inline")
        try:
            import matplotlib.pyplot as plt
            plt.switch_backend("module://matplotlib_inline.backend_inline")
        except Exception:
            pass
    else:
        matplotlib.use("TkAgg")
except Exception:
    matplotlib.use("TkAgg")

IN_INTERACTIVE = "ipy" in globals() and ipy is not None


def setup_repo_path():
    root = Path.cwd()
    if not (root / "sources").exists():
        for parent in root.parents:
            if (parent / "sources").exists():
                root = parent
                break
    sys.path.insert(0, str(root))
    sys.path.insert(0, str(root / "sources"))
    return root


def make_display(gp, directory, save_figures):
    display = gp.display_options()
    display.text = True
    display.figure = True
    display.figure_save = save_figures
    display.figure_close = save_figures
    display.directory = directory
    return display


def main():
    root = setup_repo_path()
    print("CWD:", os.getcwd())
    print("ROOT:", root)
    print("Has sources:", (root / "sources").exists())
    print("Has concentrations:", (root / "sources" / "concentrations").exists())

    import matplotlib.pyplot as plt
    plt.ion()

    def show_figures():
        if IN_INTERACTIVE:
            plt.show()

    import concentrations.concentrations as co
    from concentrations import concentrations_time as ct
    import global_parameters as gp
    import LPM.LPM_generate as LPM_generate
    import calibration.utils.systematic_sampling as calibration_exploration
    import calibration.utils.calibration_core as calbas
    import calibration.methods.simplex as csimp
    import calibration.methods.metropolis_hastings as cMH

    # ---------------- CONCENTRATIONS DATA ------------------
    file = "ploemeur_F09_2010"
    date = 2010
    verbose = True

    # ---------------- OUTPUT DIRECTORY ----------------------
    directory_results = gp.results_directory(gp.ROOT_DIRECTORY_RESULTS, "test_cases")
    directory_results = gp.results_directory(directory_results, file)

    # ---- DISPLAY OPTIONS + ROOT OUTPUT DIRECTORY ------------
    display_live = make_display(gp, directory=None, save_figures=False)
    display_save = make_display(gp, directory=directory_results, save_figures=True)

    # Data Loading
    data_dir = Path(gp.ROOT_DIRECTORY) / "examples" / "ploemeur" / "data"
    if not data_dir.exists():
        data_dir = Path(gp.ROOT_DIRECTORY) / "sites" / "ploemeur" / "data"
    filename = str(data_dir / file)
    if verbose:
        print("Data file location: ", filename)
    concentration_sampled = co.Concentrations(file_load=True, file_name=filename)
    concentration_sampled.display(display_live)
    concentration_sampled.cv.to_csv(
        os.path.join(display_save.directory, "concentrations.txt"), sep="\t"
    )

    # LPM parameters
    lpm_type = "dirac_double"
    directory_lpm = os.path.join(gp.ROOT_DIRECTORY, "core_data", "LPM_data")
    print("parameters for the calibration are in directory:\n\t", directory_lpm)

    # ---------------- REACHABLE CONCENTRATIONS -------------
    resolution_reach = 5000
    display_cr_save = copy.deepcopy(display_save)
    display_cr_save.directory_results = gp.results_directory(
        display_save.directory, "reachable_concentrations"
    )
    cr = calibration_exploration.SystematicSampling(
        lpm_type,
        concentration_sampled.names(),
        date=concentration_sampled.cv["date"],
        nmodels=resolution_reach,
        display_options=display_cr_save,
    )
    cr.compute_concentrations()
    cr.output()
    cr.display = display_live
    cr.display_concentrations_with_data()
    show_figures()
    cr.display = display_cr_save
    cr.display_concentrations_with_data()
    show_figures()

    # ---------------- CALIBRATION PARAMETERS ----------------
    calstrat = [None] * 2
    calstrat[0] = csimp.Simplex(
        "forward_uncertainty_quantification", init_multiples_n=3, fuq_n=30
    )
    calstrat[1] = cMH.MetropolisHastings(
        nstep=5000,
        prior_option=False,
        likelyhood=True,
        monitor=False,
        display_traj=False,
    )
    calstrat[1].MH_step.define_by_value()

    # ---------------- CALIBRATION -------------
    lpm_results = [None] * 2
    for i in range(len(calstrat)):
        directory_calibration = gp.results_directory(
            display_save.directory, calstrat[i].method
        )
        display_run = copy.deepcopy(display_save)
        display_run.directory = directory_calibration
        calib_basis = calbas.CalibrationCore(
            concentration_sampled,
            lpm_type,
            display_options=display_run,
            directory_lpm=directory_lpm,
        )
        calib_basis.prepare()
        calstrat[i].update_calibbasis(calib_basis)
        lpm_results[i] = calstrat[i].perform()
        calstrat[i].write_calibrated_lpm(lpm_results[i])

    # ---------------- SYNTHETIC FIGURES --------------------
    lpm_results[0].display_parameters_dist(
        self_method=calstrat[0].method,
        lpm_reference=None,
        lpm_2nd=lpm_results[1],
        lpm_2nd_method=calstrat[1].method,
        directory=None,
    )
    show_figures()
    lpm_results[0].display_parameters_dist(
        self_method=calstrat[0].method,
        lpm_reference=None,
        lpm_2nd=lpm_results[1],
        lpm_2nd_method=calstrat[1].method,
        directory=display_save.directory,
    )
    lpm_results[0].display_concentrations_dist(
        self_method=calstrat[0].method,
        concentrations_reference=concentration_sampled,
        lpm_2nd=lpm_results[1],
        lpm_2nd_method=calstrat[1].method,
        directory=None,
    )
    show_figures()
    lpm_results[0].display_concentrations_dist(
        self_method=calstrat[0].method,
        concentrations_reference=concentration_sampled,
        lpm_2nd=lpm_results[1],
        lpm_2nd_method=calstrat[1].method,
        directory=display_save.directory,
    )

    # ------- OBJECTIVE FUNCTION -------------------------------
    resolution_obj = 10000
    ss = calibration_exploration.SystematicSampling(
        lpm_type,
        concentration_sampled.names(),
        date=concentration_sampled.cv["date"],
        cdata=concentration_sampled,
        nmodels=resolution_obj,
        display_options=display_live,
        objfunc=True,
        reachconc=False,
    )
    ss.compute_concentrations()
    ss.objective_function_build()
    ss.objective_function_display()
    show_figures()
    ss.display = display_save
    ss.objective_function_display()

    # ------------- CONCENTRATION OUTPUTS ----------------------
    lpm = LPM_generate.LPM_generate(lpm_type, directory_lpm=directory_lpm)
    ct.display_concentration_times([display_save.directory], lpm, display_save)

    print(display_save.directory)
    if not IN_INTERACTIVE:
        plt.show(block=True)


if __name__ == "__main__":
    main()
