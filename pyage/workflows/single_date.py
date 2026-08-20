# -*- coding: utf-8 -*-
"""
Created on Wed Mar 24 20:35:54 2021

@author: Jean-Raynald de Dreuzy

Installable single-date calibration workflow.

This script exercises a full calibration workflow on a selected dataset:
- data loading and preview,
- reachable concentrations,
- calibration (simplex + Metropolis-Hastings),
- synthetic comparisons and objective-function exploration,
- output files and optional live plots.

Configuration is provided by the caller (YAML path passed to main()).
"""

import copy
from dataclasses import dataclass
from pathlib import Path

from pyage.calibration.methods.metropolis_hastings import MetropolisHastings, MHConfig
from pyage.calibration.methods.simplex import FORWARD_UNCERTAINTY, Simplex
from pyage.calibration.problem import CalibrationProblem
from pyage.calibration.utils.systematic_sampling import SystematicSampling
from pyage.concentrations import concentrations_time
from pyage.concentrations.concentrations import Concentrations
from pyage.config.paths import result_subdirectory
from pyage.config.runtime import DisplayOptions
from pyage.lpm.lpm_build import lpm_build
from pyage.workflows.plotting_runtime import (
    configure_backend,
    enable_interactive,
    show_figures,
)
from pyage.workflows.result_manifest import write_result_manifest
from pyage.workflows.single_date_config import LauncherParams, load_params
from pyage.workflows.single_date_paths import (
    configuration_root,
    dataset_results_directory,
)
from pyage.workflows.summary_plots import (
    plot_objective_summary,
    plot_parameter_summary,
    plot_single_date_model_space,
)

# Configure backend before importing pyplot.
IN_INTERACTIVE = False


def make_display(directory, save_figures):
    """
    Purpose
    -------
    Build a DisplayOptions instance for live or saved figures.

    Parameters
    ----------
    directory : str or None
        Output folder for figures; None disables saving.
    save_figures : bool
        Whether figures should be written to disk.
    """
    # Centralize display options for either live plots or saved figures.
    # - directory=None -> no saving, keep figures open
    # - directory set  -> save figures to disk
    display = DisplayOptions()
    display.text = True
    display.figure = True
    display.figure_save = save_figures
    display.figure_close = save_figures
    display.directory = directory  # None -> live only, Path -> save outputs.
    return display


def build_display_set(results_dir):
    """
    Purpose
    -------
    Build the pair of display settings used by the workflow.

    Parameters
    ----------
    results_dir : str
        Base directory for saved outputs.

    Returns
    -------
    tuple
        (display_live, display_save) configured for interactive and saved plots.
    """
    display_live = make_display(directory=None, save_figures=False)
    display_save = make_display(directory=results_dir, save_figures=True)
    return display_live, display_save


def build_calibration_problem(
    params: LauncherParams,
    observations: Concentrations,
    display_options: DisplayOptions,
) -> CalibrationProblem:
    """Build the prepared problem shared by one calibration method."""
    return CalibrationProblem(
        observations,
        params.lpm_model_name,
        display_options=display_options,
        lpm_directory=params.directory_lpm,
        tracer_data_directory=params.tracer_data_dir,
    ).prepare()


def build_show_figures(plt):
    """
    Purpose
    -------
    Return a helper that flushes figures in interactive mode.
    """

    def _show():
        show_figures(plt, IN_INTERACTIVE)

    return _show


def build_case_label(params: LauncherParams) -> str:
    """Return a short human-readable label for figure titles."""
    if params.dataset_label:
        return params.dataset_label
    return Path(params.dataset_name).stem.replace("_", " ")


@dataclass
class WorkflowContext:
    """Context container for a configured example run."""

    root: Path
    params: LauncherParams
    display_live: object
    display_save: object
    concentration_sampled: object


def load_concentration_data(
    params: LauncherParams,
    display_live: DisplayOptions,
) -> Concentrations:
    """
    Purpose
    -------
    Load the selected concentration dataset and preview it.

    Parameters
    ----------
    params : LauncherParams
        Parsed parameters (expects dataset_name/dataset_data_dir).
    display_live : DisplayOptions
        Live display settings for plotting/preview.

    Returns
    -------
    Concentrations
        Loaded concentration data container.
    """
    filename = str(params.dataset_data_dir / params.dataset_name)
    if params.verbose:
        print("Data file location: ", filename)
    concentration_sampled = Concentrations(file_load=True, file_name=filename)
    concentration_sampled.display(display_live)  # Quick visual check of input data.
    return concentration_sampled


def run_reachable_concentration_analysis(
    params,
    concentration_sampled,
    display_live,
    display_save,
    show_figures,
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
    display_live : DisplayOptions
        Live display settings.
    display_save : DisplayOptions
        Saving display settings.
    show_figures : callable
        Helper to flush figures in interactive mode.
    Notes
    -----
    The analysis stores the systematic sampling results used later for the
    didactic summary figure.
    """
    display_reach_save = copy.deepcopy(display_save)
    display_reach_save.directory = result_subdirectory(
        display_save.directory, "reachable_concentrations"
    )
    cr = SystematicSampling(
        params.lpm_model_name,
        concentration_sampled.names(),
        date=concentration_sampled.cv["date"],
        nmodels=params.reachable_concentration_nmodels,
        display_options=display_reach_save,
        directory_lpm=str(params.directory_lpm),
        tracer_data_dir=str(params.tracer_data_dir) if params.tracer_data_dir else None,
    )
    cr.compute_concentrations()
    cr.output()
    return cr


def run_calibration_simplex(
    params,
    concentration_sampled,
    display_save,
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
    display_save : DisplayOptions
        Saving display settings.
    Returns
    -------
    tuple
        (strategy, lpm_results) for subsequent comparisons.
    """
    strategy = Simplex(
        FORWARD_UNCERTAINTY,
        init_multiples_n=params.simplex_init_multiples_n,
        fuq_n=params.simplex_fuq_n,
    )
    directory_calibration = result_subdirectory(display_save.directory, strategy.method)
    display_run = copy.deepcopy(display_save)
    display_run.directory = directory_calibration
    problem = build_calibration_problem(
        params,
        concentration_sampled,
        display_run,
    )
    lpm_results = strategy.run(problem)
    strategy.write_calibrated_lpm(lpm_results)  # Persist calibrated distributions.
    return strategy, lpm_results


def run_calibration_metropolis_hastings(
    params,
    concentration_sampled,
    display_save,
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
    display_save : DisplayOptions
        Saving display settings.
    Returns
    -------
    tuple
        (strategy, lpm_results) for subsequent comparisons.
    """
    mh_config = MHConfig(
        nstep=params.mh_nstep,
        prior_option=params.mh_prior_option,
        likelihood=params.mh_likelihood,
        monitor=params.mh_monitor,
        display_traj=params.mh_display_traj,
    )
    strategy = MetropolisHastings(config=mh_config)
    strategy.MH_step.define_by_value()  # Use default proposal steps.
    directory_calibration = result_subdirectory(display_save.directory, strategy.method)
    display_run = copy.deepcopy(display_save)
    display_run.directory = directory_calibration
    problem = build_calibration_problem(
        params,
        concentration_sampled,
        display_run,
    )
    lpm_results = strategy.run(problem)
    strategy.write_calibrated_lpm(lpm_results)  # Persist calibrated distributions.
    return strategy, lpm_results


def render_summary_figures(
    concentration_sampled,
    display_save,
    show_figures,
    reachable_frame,
    posterior_results,
    case_label,
):
    """
    Purpose
    -------
    Render summary figures for a single-date calibration run.

    Parameters
    ----------
    concentration_sampled : Concentrations
        Observed concentrations for overlay.
    display_save : DisplayOptions
        Saving display settings.
    show_figures : callable
        Helper to flush figures in interactive mode.

    posterior_results : dict[str, object]
        Mapping from method name to calibrated parameter distributions.
    case_label : str
        Short title prefix for the generated figures.
    """
    import matplotlib.pyplot as plt

    if not posterior_results:
        return
    first_result = next(iter(posterior_results.values()))
    param_names = first_result.get_param_names()

    if reachable_frame is not None:
        fig = plot_single_date_model_space(
            concentration_sampled,
            reachable_frame=reachable_frame,
            posterior_results=posterior_results,
            filename=None,
            title=f"{case_label}: observations, reachable space and calibrated models",
        )
        show_figures()
        plt.close(fig)

        fig = plot_single_date_model_space(
            concentration_sampled,
            reachable_frame=reachable_frame,
            posterior_results=posterior_results,
            filename=Path(display_save.directory) / "01_data_model_space.png",
            title=f"{case_label}: observations, reachable space and calibrated models",
        )
        plt.close(fig)

    fig = plot_parameter_summary(
        posterior_results,
        param_names=param_names,
        filename=None,
        title=f"{case_label}: parameter distributions",
    )
    show_figures()
    plt.close(fig)

    fig = plot_parameter_summary(
        posterior_results,
        param_names=param_names,
        filename=Path(display_save.directory) / "02_parameter_summary.png",
        title=f"{case_label}: parameter distributions",
    )
    plt.close(fig)


def run_objective_function_analysis(
    params,
    concentration_sampled,
    display_live,
    display_save,
    show_figures,
    posterior_results,
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
    display_live : DisplayOptions
        Live display settings.
    display_save : DisplayOptions
        Saving display settings.
    show_figures : callable
        Helper to flush figures in interactive mode.

    Notes
    -----
    The objective function is computed on a sampling grid and summarized with
    the calibrated parameter clouds overlaid on top of the sampled landscape.
    """
    import matplotlib.pyplot as plt

    ss = SystematicSampling(
        params.lpm_model_name,
        concentration_sampled.names(),
        date=concentration_sampled.cv["date"],
        cdata=concentration_sampled,
        nmodels=params.objective_function_nmodels,
        display_options=display_live,
        objfunc=True,
        reachconc=False,
        directory_lpm=str(params.directory_lpm),
        tracer_data_dir=str(params.tracer_data_dir) if params.tracer_data_dir else None,
    )
    ss.compute_concentrations()
    ss.objective_function_build()
    objective_frame = ss.objective_function_frame()
    objective_frame.to_csv(
        Path(display_save.directory) / "objective_function_grid.txt",
        sep="\t",
        index=False,
    )
    param_names = ss.parameter_names()

    fig = plot_objective_summary(
        objective_frame=objective_frame,
        posterior_results=posterior_results,
        param_names=param_names,
        filename=None,
        title=f"{build_case_label(params)}: objective landscape and estimated parameters",
    )
    show_figures()
    plt.close(fig)

    fig = plot_objective_summary(
        objective_frame=objective_frame,
        posterior_results=posterior_results,
        param_names=param_names,
        filename=Path(display_save.directory) / "03_objective_summary.png",
        title=f"{build_case_label(params)}: objective landscape and estimated parameters",
    )
    plt.close(fig)


def run_concentration_outputs(params, display_save):
    """
    Purpose
    -------
    Write concentration time series outputs to disk.

    Parameters
    ----------
    params : LauncherParams
        Parsed parameters (expects lpm_model_name and directory_lpm).
    display_save : DisplayOptions
        Saving display settings for output directory.
    """
    lpm = lpm_build(
        params.lpm_model_name,
        directory_lpm=str(params.directory_lpm),
    )
    concentrations_time.display_concentration_times(
        [display_save.directory], lpm, display_save
    )


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
    global IN_INTERACTIVE
    IN_INTERACTIVE = configure_backend(force_inline=force_inline)
    import matplotlib.pyplot as plt

    enable_interactive(plt)
    show_fig = build_show_figures(plt)

    # Load parameters from the YAML file provided to main().
    if params_path is None:
        raise ValueError("params_path is required for the launcher.")
    params_path = Path(params_path).resolve()
    root = configuration_root(params_path)
    params = load_params(root, params_path)

    # ---------------- OUTPUT DIRECTORY ----------------------
    # Results are stored under results/test_cases/<dataset_name>/...
    directory_results = dataset_results_directory(params.dataset_name)

    # ---- DISPLAY OPTIONS + ROOT OUTPUT DIRECTORY ------------
    # display_live: show plots on screen
    # display_save: save plots to disk
    display_live, display_save = build_display_set(directory_results)
    write_result_manifest(
        display_save.directory,
        workflow="single_date",
        config_name=params_path.name,
        details={
            "dataset": params.dataset_name,
            "lpm": params.lpm_model_name,
        },
    )

    # ---------------- CONCENTRATIONS DATA ------------------
    concentration_sampled = load_concentration_data(params, display_live)
    concentration_sampled.cv.to_csv(
        Path(display_save.directory) / "concentrations.txt", sep="\t"
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

    reachable_sampler = None
    if context.params.run_reachable_concentrations:
        reachable_sampler = run_reachable_concentration_analysis(
            context.params,
            context.concentration_sampled,
            context.display_live,
            context.display_save,
            show_fig,
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
        )
    if context.params.run_calibration_metropolis_hastings:
        strategy_mh, results_mh = run_calibration_metropolis_hastings(
            context.params,
            context.concentration_sampled,
            context.display_save,
        )

    posterior_results = {}
    if strategy_simplex and results_simplex:
        posterior_results[strategy_simplex.method] = results_simplex
    if strategy_mh and results_mh:
        posterior_results[strategy_mh.method] = results_mh

    if posterior_results:
        render_summary_figures(
            context.concentration_sampled,
            context.display_save,
            show_fig,
            reachable_frame=reachable_sampler.concentrations_frame()
            if reachable_sampler
            else None,
            posterior_results=posterior_results,
            case_label=build_case_label(context.params),
        )

    # ------- OBJECTIVE FUNCTION -------------------------------
    if context.params.run_objective_function:
        run_objective_function_analysis(
            context.params,
            context.concentration_sampled,
            context.display_live,
            context.display_save,
            show_fig,
            posterior_results,
        )

    # ------------- CONCENTRATION OUTPUTS ----------------------
    run_concentration_outputs(context.params, context.display_save)

    if not IN_INTERACTIVE:
        plt.show(block=True)
    return Path(display_save.directory)


def run_single_date(params_path, force_inline: bool = False) -> Path:
    """Run the supported single-date workflow from one YAML configuration."""
    return run_workflow(params_path, force_inline=force_inline)


__all__ = ["run_single_date", "run_workflow"]
