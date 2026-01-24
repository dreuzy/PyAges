# -*- coding: utf-8 -*-
"""
Created on Wed Mar 24 20:35:54 2021

@author: Jean-Raynald de Dreuzy

Launcher script for a case study workflow.

This script exercises a full calibration workflow on a selected dataset:
- data loading and preview,
- reachable concentrations,
- calibration (simplex + Metropolis-Hastings),
- synthetic comparisons and objective-function exploration,
- output files and optional live plots.

Configuration is provided by the caller (YAML path passed to main()).
"""

import sys
import os
import copy
import argparse
import subprocess
from dataclasses import dataclass
from pathlib import Path

# This script runs a full example workflow:
# 1) load concentration data,
# 2) explore reachable concentrations,
# 3) run two calibration strategies,
# 4) compare synthetic figures and objective function,
# 5) save outputs and optionally show live figures.

from common.launcher_paths import results_directory
from common.launcher_params import LauncherParams, load_params
from common.plotting_helpers import configure_backend, enable_interactive, show_figures

# Configure backend before importing pyplot.
IN_INTERACTIVE = False


def setup_repo_path():
    """
    Return repo root and ensure it is on sys.path.

    Enables running the script from any working directory while keeping imports
    stable (e.g., `concentrations`, `calibration`, `LPM`).
    """
    # Repository root is one level up from scripts/
    root = Path(__file__).resolve().parent.parent
    sys.path.insert(0, str(root))
    sys.path.insert(0, str(root / "sources"))
    return root


def make_display(gp, directory, save_figures):
    """
    Purpose
    -------
    Build a display_options instance for live or saved figures.

    Parameters
    ----------
    gp : module
        global_parameters module with display_options.
    directory : str or None
        Output folder for figures; None disables saving.
    save_figures : bool
        Whether figures should be written to disk.
    """
    # Centralize display options for either live plots or saved figures.
    # - directory=None -> no saving, keep figures open
    # - directory set  -> save figures to disk
    display = gp.display_options()
    display.text = True
    display.figure = True
    display.figure_save = save_figures
    display.figure_close = save_figures
    display.directory = directory  # None -> live only, Path -> save outputs.
    return display


def build_display_set(gp, results_dir):
    """
    Purpose
    -------
    Build the pair of display settings used by the workflow.

    Parameters
    ----------
    gp : module
        global_parameters module.
    results_dir : str
        Base directory for saved outputs.

    Returns
    -------
    tuple
        (display_live, display_save) configured for interactive and saved plots.
    """
    display_live = make_display(gp, directory=None, save_figures=False)
    display_save = make_display(gp, directory=results_dir, save_figures=True)
    return display_live, display_save


def build_calibration_core(params, concentration_sampled, calbas, display_run):
    """
    Purpose
    -------
    Construct and prepare a CalibrationCore instance.

    Parameters
    ----------
    params : LauncherParams
        Parsed parameters (expects LPM settings).
    concentration_sampled : Concentrations
        Observed concentrations used for calibration.
    calbas : module
        calibration.utils.calibration_core module.
    display_run : display_options
        Display options for outputs.

    Returns
    -------
    CalibrationCore
        Prepared calibration core ready for strategies.
    """
    calib_basis = calbas.CalibrationCore(
        concentration_sampled,
        params.lpm_model_name,
        display_options=display_run,
        directory_lpm=str(params.directory_lpm),
    )
    calib_basis.prepare()  # Build tracers, LPM structure, and sampling tools.
    return calib_basis


def build_show_figures(plt):
    """
    Purpose
    -------
    Return a helper that flushes figures in interactive mode.
    """
    def _show():
        show_figures(plt, IN_INTERACTIVE)
    return _show


@dataclass
class WorkflowContext:
    """Context container for a configured example run."""

    root: Path
    params: LauncherParams
    display_live: object
    display_save: object
    concentration_sampled: object


def load_concentration_data(params: LauncherParams, co, display_live):
    """
    Purpose
    -------
    Load the selected concentration dataset and preview it.

    Parameters
    ----------
    params : LauncherParams
        Parsed parameters (expects dataset_name/dataset_data_dir).
    co : module
        concentrations.concentrations module (data container + loader).
    display_live : display_options
        Live display settings for plotting/preview.

    Returns
    -------
    Concentrations
        Loaded concentration data container.
    """
    filename = str(params.dataset_data_dir / params.dataset_name)
    if params.verbose:
        print("Data file location: ", filename)
    concentration_sampled = co.Concentrations(file_load=True, file_name=filename)
    concentration_sampled.display(display_live)  # Quick visual check of input data.
    return concentration_sampled


def run_reachable_concentration_analysis(
    params,
    concentration_sampled,
    calibration_exploration,
    display_live,
    display_save,
    show_figures,
    gp,
):
    """
    Purpose
    -------
    Compute reachable concentrations and render/save figures.

    Parameters
    ----------
    params : LauncherParams
        Parsed parameters (expects model name and nmodels).
    concentration_sampled : Concentrations
        Observed concentrations to compare against.
    calibration_exploration : module
        calibration.utils.systematic_sampling module.
    display_live : display_options
        Live display settings.
    display_save : display_options
        Saving display settings.
    show_figures : callable
        Helper to flush figures in interactive mode.
    gp : module
        global_parameters module (for results_directory).

    Notes
    -----
    The analysis runs once with live display enabled (for quick feedback) and
    again with saving enabled to capture results on disk.
    """
    display_reach_save = copy.deepcopy(display_save)
    display_reach_save.directory_results = gp.results_directory(
        display_save.directory, "reachable_concentrations"
    )
    cr = calibration_exploration.SystematicSampling(
        params.lpm_model_name,
        concentration_sampled.names(),
        date=concentration_sampled.cv["date"],
        nmodels=params.reachable_concentration_nmodels,
        display_options=display_reach_save,
    )
    cr.compute_concentrations()
    cr.output()
    # Live preview
    cr.display = display_live
    cr.display_concentrations_with_data()
    show_figures()
    # Saved figures
    cr.display = display_reach_save
    cr.display_concentrations_with_data()
    show_figures()


def run_calibration_simplex(
    params,
    concentration_sampled,
    display_save,
    calbas,
    csimp,
    gp,
):
    """
    Purpose
    -------
    Run the Simplex calibration strategy and persist outputs.

    Parameters
    ----------
    params : LauncherParams
        Parsed parameters (expects simplex_* and LPM settings).
    concentration_sampled : Concentrations
        Observed concentrations used for calibration.
    display_save : display_options
        Saving display settings.
    calbas : module
        calibration.utils.calibration_core module.
    csimp : module
        calibration.methods.simplex module.

    Returns
    -------
    tuple
        (strategy, lpm_results) for subsequent comparisons.
    """
    strategy = csimp.Simplex(
        "forward_uncertainty_quantification",
        init_multiples_n=params.simplex_init_multiples_n,
        fuq_n=params.simplex_fuq_n,
    )
    directory_calibration = gp.results_directory(
        display_save.directory, strategy.method
    )
    display_run = copy.deepcopy(display_save)
    display_run.directory = directory_calibration
    calib_basis = build_calibration_core(
        params,
        concentration_sampled,
        calbas,
        display_run,
    )
    strategy.update_calibbasis(calib_basis)
    lpm_results = strategy.perform()
    strategy.write_calibrated_lpm(lpm_results)  # Persist calibrated distributions.
    return strategy, lpm_results


def run_calibration_metropolis_hastings(
    params,
    concentration_sampled,
    display_save,
    calbas,
    cMH,
    gp,
):
    """
    Purpose
    -------
    Run the Metropolis-Hastings calibration strategy and persist outputs.

    Parameters
    ----------
    params : LauncherParams
        Parsed parameters (expects MH_* and LPM settings).
    concentration_sampled : Concentrations
        Observed concentrations used for calibration.
    display_save : display_options
        Saving display settings.
    calbas : module
        calibration.utils.calibration_core module.
    cMH : module
        calibration.methods.metropolis_hastings module.

    Returns
    -------
    tuple
        (strategy, lpm_results) for subsequent comparisons.
    """
    strategy = cMH.MetropolisHastings(
        nstep=params.mh_nstep,
        prior_option=params.mh_prior_option,
        likelyhood=params.mh_likelyhood,
        monitor=params.mh_monitor,
        display_traj=params.mh_display_traj,
    )
    strategy.MH_step.define_by_value()  # Use default proposal steps.
    directory_calibration = gp.results_directory(
        display_save.directory, strategy.method
    )
    display_run = copy.deepcopy(display_save)
    display_run.directory = directory_calibration
    calib_basis = build_calibration_core(
        params,
        concentration_sampled,
        calbas,
        display_run,
    )
    strategy.update_calibbasis(calib_basis)
    lpm_results = strategy.perform()
    strategy.write_calibrated_lpm(lpm_results)  # Persist calibrated distributions.
    return strategy, lpm_results


def compare_synthetic_figures(
    strategy_a,
    strategy_b,
    lpm_results_a,
    lpm_results_b,
    concentration_sampled,
    display_save,
    show_figures,
):
    """
    Purpose
    -------
    Render parameter and concentration comparisons between two strategies.

    Parameters
    ----------
    strategy_a : object
        First calibration strategy (reference).
    strategy_b : object
        Second calibration strategy (comparison).
    lpm_results_a : LPMDist
        Calibrated LPM distribution for strategy_a.
    lpm_results_b : LPMDist
        Calibrated LPM distribution for strategy_b.
    concentration_sampled : Concentrations
        Observed concentrations for overlay.
    display_save : display_options
        Saving display settings.
    show_figures : callable
        Helper to flush figures in interactive mode.

    Notes
    -----
    Generates live plots (directory=None) and saved plots to the results folder.
    """
    lpm_results_a.display_parameters_dist(
        self_method=strategy_a.method,
        lpm_reference=None,
        lpm_2nd=lpm_results_b,
        lpm_2nd_method=strategy_b.method,
        directory=None,
    )
    show_figures()
    lpm_results_a.display_parameters_dist(
        self_method=strategy_a.method,
        lpm_reference=None,
        lpm_2nd=lpm_results_b,
        lpm_2nd_method=strategy_b.method,
        directory=display_save.directory,
    )
    lpm_results_a.display_concentrations_dist(
        self_method=strategy_a.method,
        concentrations_reference=concentration_sampled,
        lpm_2nd=lpm_results_b,
        lpm_2nd_method=strategy_b.method,
        directory=None,
    )
    show_figures()
    lpm_results_a.display_concentrations_dist(
        self_method=strategy_a.method,
        concentrations_reference=concentration_sampled,
        lpm_2nd=lpm_results_b,
        lpm_2nd_method=strategy_b.method,
        directory=display_save.directory,
    )


def run_objective_function_analysis(
    params,
    concentration_sampled,
    calibration_exploration,
    display_live,
    display_save,
    show_figures,
):
    """
    Purpose
    -------
    Evaluate objective function on a grid and render/save plots.

    Parameters
    ----------
    params : LauncherParams
        Parsed parameters (expects objective_function_nmodels).
    concentration_sampled : Concentrations
        Observed concentrations for objective function evaluation.
    calibration_exploration : module
        calibration.utils.systematic_sampling module.
    display_live : display_options
        Live display settings.
    display_save : display_options
        Saving display settings.
    show_figures : callable
        Helper to flush figures in interactive mode.

    Notes
    -----
    The objective function is computed on a sampling grid, then displayed
    both live and saved to disk for traceability.
    """
    ss = calibration_exploration.SystematicSampling(
        params.lpm_model_name,
        concentration_sampled.names(),
        date=concentration_sampled.cv["date"],
        cdata=concentration_sampled,
        nmodels=params.objective_function_nmodels,
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


def run_concentration_outputs(params, LPM_generate, ct, display_save):
    """
    Purpose
    -------
    Write concentration time series outputs to disk.

    Parameters
    ----------
    params : LauncherParams
        Parsed parameters (expects lpm_model_name and directory_lpm).
    LPM_generate : module
        LPM.LPM_generate module.
    ct : module
        concentrations.concentrations_time module.
    display_save : display_options
        Saving display settings for output directory.
    """
    lpm = LPM_generate.LPM_generate(
        params.lpm_model_name,
        directory_lpm=str(params.directory_lpm),
    )
    ct.display_concentration_times([display_save.directory], lpm, display_save)


def run_workflow(params_path, force_inline=False):
    """
    Purpose
    -------
    Orchestrate the full example workflow.

    Notes
    -----
    The workflow is organized into independent steps controlled by the run_*
    flags loaded from the YAML parameters.
    """
    # ------------------ PATHS & SETUP ------------------
    root = setup_repo_path()
    print("CWD:", os.getcwd())
    print("ROOT:", root)
    print("Has sources:", (root / "sources").exists())
    print("Has concentrations:", (root / "sources" / "concentrations").exists())

    global IN_INTERACTIVE
    IN_INTERACTIVE = configure_backend(force_inline=force_inline)
    import matplotlib.pyplot as plt
    enable_interactive(plt)
    show_fig = build_show_figures(plt)

    import concentrations.concentrations as co
    from concentrations import concentrations_time as ct
    import global_parameters as gp
    import LPM.LPM_generate as LPM_generate
    import calibration.utils.systematic_sampling as calibration_exploration
    import calibration.utils.calibration_core as calbas
    import calibration.methods.simplex as csimp
    import calibration.methods.metropolis_hastings as cMH

    # Load parameters from the YAML file provided to main().
    if params_path is None:
        raise ValueError("params_path is required for the launcher.")
    params_path = Path(params_path)
    if not params_path.is_absolute():
        params_path = root / params_path
    params = load_params(root, params_path)

    # ---------------- OUTPUT DIRECTORY ----------------------
    # Results are stored under results/test_cases/<dataset_name>/...
    directory_results = results_directory(gp, params.dataset_name)

    # ---- DISPLAY OPTIONS + ROOT OUTPUT DIRECTORY ------------
    # display_live: show plots on screen
    # display_save: save plots to disk
    display_live, display_save = build_display_set(gp, directory_results)

    # ---------------- CONCENTRATIONS DATA ------------------
    concentration_sampled = load_concentration_data(params, co, display_live)
    concentration_sampled.cv.to_csv(
        os.path.join(display_save.directory, "concentrations.txt"), sep="\t"
    )
    print("parameters for the calibration are in directory:\n\t", params.directory_lpm)

    # ---------------- REACHABLE CONCENTRATIONS -------------
    context = WorkflowContext(
        root=root,
        params=params,
        display_live=display_live,
        display_save=display_save,
        concentration_sampled=concentration_sampled,
    )

    if context.params.run_reachable_concentrations:
        run_reachable_concentration_analysis(
            context.params,
            context.concentration_sampled,
            calibration_exploration,
            context.display_live,
            context.display_save,
            show_fig,
            gp,
        )

    # ---------------- CALIBRATION ----------------
    strategy_simplex = None
    results_simplex = None
    strategy_mh = None
    results_mh = None

    if context.params.run_calibration_simplex:
        strategy_simplex, results_simplex = run_calibration_simplex(
            context.params,
            context.concentration_sampled,
            context.display_save,
            calbas,
            csimp,
            gp,
        )
    if context.params.run_calibration_metropolis_hastings:
        strategy_mh, results_mh = run_calibration_metropolis_hastings(
            context.params,
            context.concentration_sampled,
            context.display_save,
            calbas,
            cMH,
            gp,
        )

    if strategy_simplex and strategy_mh:
        compare_synthetic_figures(
            strategy_simplex,
            strategy_mh,
            results_simplex,
            results_mh,
            context.concentration_sampled,
            context.display_save,
            show_fig,
        )

    # ------- OBJECTIVE FUNCTION -------------------------------
    if context.params.run_objective_function:
        run_objective_function_analysis(
            context.params,
            context.concentration_sampled,
            calibration_exploration,
            context.display_live,
            context.display_save,
            show_fig,
        )

    # ------------- CONCENTRATION OUTPUTS ----------------------
    run_concentration_outputs(context.params, LPM_generate, ct, context.display_save)

    print(display_save.directory)
    if not IN_INTERACTIVE:
        plt.show(block=True)


def main(params_path, force_inline=False):
    """CLI wrapper for run_workflow."""
    run_workflow(params_path, force_inline=force_inline)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Run the example workflow.")
    parser.add_argument(
        "params_path",
        help="Path to the YAML parameters file.",
    )
    parser.add_argument(
        "--inline",
        action="store_true",
        help="Force inline backend (useful when launching from an interactive window).",
    )
    parser.add_argument(
        "--set-results-dir",
        nargs="?",
        const="__ASK__",
        default=None,
        help="Persist PYAGE_RESULTS_DIR for the user (prompts if no path provided).",
    )
    args = parser.parse_args()
    if args.set_results_dir is not None:
        default_dir = Path.home() / "results" / "PyAge"
        if args.set_results_dir == "__ASK__":
            prompt = f"PYAGE_RESULTS_DIR [{default_dir}]: "
            user_value = input(prompt).strip()
            results_dir = user_value or str(default_dir)
        else:
            results_dir = args.set_results_dir
        os.environ["PYAGE_RESULTS_DIR"] = results_dir
        if os.name == "nt":
            subprocess.run(["setx", "PYAGE_RESULTS_DIR", results_dir], check=True)
        else:
            print("PYAGE_RESULTS_DIR set for current process only (non-Windows).")
    main(args.params_path, force_inline=args.inline)
