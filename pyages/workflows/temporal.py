# Copyright (c) 2021-2026 Centre national de la recherche scientifique (CNRS)
# Contributor: Jean-Raynald de Dreuzy
# SPDX-License-Identifier: CECILL-2.1

"""
Reusable temporal Metropolis-Hastings workflow.

What this workflow does
-----------------------
This module runs a Metropolis-Hastings calibration on a multi-date concentration
file (ori_*.txt) and writes:
- calibrated parameters and stats,
- concentration chronicle plots,
- optional parameter/concentration distributions.

Workflow modes
--------------
- span: single calibration over the full time span.
- successive: one calibration per observation date.

Code architecture choices (why it is written this way)
-------------------------------------------------------
1) Pydantic configuration validation (strict + explicit)
   - YAML is parsed into a typed schema (DatasetCfg, CalibrationCfg, ...).
   - This gives early, clear errors for missing fields, wrong types, and bounds.
   - It prevents silent defaults from masking misconfigurations.

2) Structured I/O + reproducibility
   - Relative paths use the repository root for repository configurations and
     the configuration directory for standalone projects.
   - Results are written under a stable folder tree for regression testing.

"""

from __future__ import annotations

import secrets
from dataclasses import dataclass
from pathlib import Path
from typing import cast

# Core library imports (use pyages.* consistently to avoid duplicate modules).
from pyages.calibration.methods.mh import MetropolisHastings, MHConfig
from pyages.calibration.problem import CalibrationProblem, resolve_observation_errors
from pyages.concentrations import Concentrations
from pyages.concentrations.schema import ERROR_COLUMN
from pyages.config.loading import resolve_from, validate_yaml_model

# Shared Pydantic schemas live in pyages.config.models to keep launchers consistent.
from pyages.config.models import (
    TemporalCalibrationCfg,
    TemporalDatasetCfg,
    TemporalFiguresCfg,
    TemporalLpmModelsCfg,
    TemporalParams,
    TemporalResultsCfg,
)
from pyages.config.paths import (
    DIRECTORY_LPM_DATA,
    DIRECTORY_TRACER_DATA,
    ROOT_DIRECTORY_RESULTS,
    result_subdirectory,
)
from pyages.config.runtime import DisplayOptions
from pyages.lpm.plotting.sample_diagnostics import plot_concentration_diagnostics
from pyages.workflows.concentration_exports import export_calibrated_chronicles
from pyages.workflows.plots import (
    plot_observations_overview,
    plot_parameter_summary,
)
from pyages.workflows.result_manifest import begin_result_run, write_result_manifest
from pyages.workflows.single_date_paths import configuration_root

DEFAULT_LPMS = ["exp_shifted", "ig", "ig_shifted"]


@dataclass(frozen=True)
class TemporalContext:
    """Resolved configuration and inputs for one temporal workflow."""

    config_path: Path
    configuration_directory: Path
    params: TemporalParams
    dataset_path: Path
    mode: str
    models: list[str]
    lpm_directory: Path
    observations: Concentrations
    output_directory: Path


def _load_params_validated(path: Path) -> TemporalParams:
    """Load and validate a temporal workflow configuration."""
    return cast(
        TemporalParams,
        validate_yaml_model(
            path,
            TemporalParams,
            label="temporal workflow configuration",
        ),
    )


def _format_date_label(date_value: float) -> str:
    """
    Build a safe folder name for a float date (e.g., 2005.43 -> 2005_43).

    Parameters
    ----------
    date_value : float
        Decimal year to encode.

    Returns
    -------
    str
        Sanitized label suitable for folder names.
    """
    label = repr(float(date_value))
    if label.endswith(".0"):
        label = label[:-2]
    return label.replace(".", "_")


def _results_root(
    results_cfg: TemporalResultsCfg,
    configuration_directory: Path,
) -> Path:
    """
    Resolve the results root based on YAML options.

    Parameters
    ----------
    results_cfg : TemporalResultsCfg
        Validated results section with fields:
        - use_default : bool
        - directory : str
        - study_name : str

    Returns
    -------
    Path
        Root directory for results.

    Raises
    ------
    ValueError
        If use_default is false and directory is not provided.
    """
    if results_cfg.use_default:
        return ROOT_DIRECTORY_RESULTS
    directory = results_cfg.directory
    if not directory:
        raise ValueError("results.directory must be set when use_default is false.")
    results_path = resolve_from(configuration_directory, directory)
    results_path.mkdir(parents=True, exist_ok=True)
    return results_path


def _prepare_display(
    output_dir: Path, figures_cfg: TemporalFiguresCfg
) -> DisplayOptions:
    """
    Create display options for a single calibration run.

    Parameters
    ----------
    output_dir : Path
        Directory where figures and files are written.
    figures_cfg : TemporalFiguresCfg
        Validated figure options:
        - temporal : bool
        - distributions : bool
        - concentrations_2d : bool

    Returns
    -------
    DisplayOptions
        Configured display options instance.
    """
    display = DisplayOptions()
    display.text = False
    display.figure = bool(figures_cfg.temporal or figures_cfg.distributions)
    display.figure_save = True
    display.figure_close = True
    display.directory = str(output_dir)
    return display


def _build_mh_config(cal_cfg: TemporalCalibrationCfg) -> MHConfig:
    """
    Build a Metropolis-Hastings configuration from YAML settings.

    Parameters
    ----------
    cal_cfg : TemporalCalibrationCfg
        Validated temporal calibration settings.
    Returns
    -------
    MHConfig
        Metropolis-Hastings configuration object ready for calibration runs.
    """
    # Disabled fixed seeding means a fresh, explicit seed for each chain. The
    # resolved value is persisted by the MH result writer.
    seed_value = cal_cfg.seed if cal_cfg.seed_enabled else secrets.randbits(63)
    if seed_value is None:
        raise ValueError("calibration.seed is required when seed_enabled is true")
    return MHConfig(
        nstep=int(cal_cfg.mh_nsteps),
        burn_in=float(cal_cfg.burn_in),
        nskip=int(cal_cfg.nskip),
        prior_option=True,
        prior_type="parametric",
        likelihood=True,
        monitor=False,
        display_traj=False,
        display_text=False,
        componentwise_source="model",
        seed=seed_value,
    )


def _run_calibration(
    observations: Concentrations,
    lpm_type: str,
    output_dir: Path,
    lpm_directory: Path,
    cal_cfg: TemporalCalibrationCfg,
    figures_cfg: TemporalFiguresCfg,
):
    """
    Run one MH calibration for a given dataset, LPM, and mode.

    Parameters
    ----------
    observations : Concentrations
        Concentration data (single-date or multi-date subset).
    lpm_type : str
        LPM name to calibrate (e.g., exp_shifted).
    output_dir : Path
        Output folder for this calibration.
    lpm_directory : Path
        Directory holding LPM parameter files (params.yaml).
    cal_cfg : TemporalCalibrationCfg
        Calibration parameters (mh_nsteps, burn_in, nskip, lpm_number, seed...).
    figures_cfg : TemporalFiguresCfg
        Figure options (temporal, distributions, and concentrations_2d).
    Notes
    -----
    This function performs the full MH workflow:
    1) build calibration core
    2) run MH
    3) write outputs
    4) render figures (if enabled)
    """
    # Display and output configuration for this run.
    display = _prepare_display(output_dir, figures_cfg)
    # Calibration resolution and sampling controls.
    explo_res = int(cal_cfg.explo_res)
    mh_nsteps = int(cal_cfg.mh_nsteps)
    lpm_number = int(cal_cfg.lpm_number)
    if lpm_number <= 0:
        lpm_number = max(min(int(mh_nsteps / 50), 5000), 10)

    # Core calibration setup (data, model, solver options).
    problem = CalibrationProblem(
        observations,
        lpm_type,
        display_options=display,
        lpm_directory=lpm_directory,
        sample_count=explo_res,
        explore_reachable=False,
    ).prepare()

    # Metropolis-Hastings setup and execution.
    mh_config = _build_mh_config(cal_cfg)
    calstrat = MetropolisHastings(config=mh_config)
    lpm_results = calstrat.run(problem)
    # Persist calibrated distributions/statistics.
    calstrat.write_calibrated_lpm(lpm_results)

    # Temporal figures (chronicles) if enabled.
    if figures_cfg.temporal:
        export_calibrated_chronicles(
            observations,
            lpm_results,
            calstrat.method,
            display,
            lpm_number=lpm_number,
        )

    # Distribution figures if enabled.
    if figures_cfg.distributions:
        fig = plot_parameter_summary(
            {calstrat.method: lpm_results},
            param_names=lpm_results.get_param_names(),
            filename=Path(display.directory) / "parameter_summary.png",
            title=f"{lpm_type}: calibrated parameter distributions",
        )
        import matplotlib.pyplot as plt

        plt.close(fig)
        if figures_cfg.concentrations_2d:
            plot_concentration_diagnostics(
                lpm_results,
                self_method=calstrat.method,
                concentrations_reference=observations,
                directory=display.directory,
            )


def _resolve_dataset(
    dataset_cfg: TemporalDatasetCfg,
    configuration_directory: Path,
) -> Path:
    """Resolve and validate the temporal observation file."""
    dataset_path = resolve_from(configuration_directory, dataset_cfg.file)
    if not dataset_path.is_file():
        raise FileNotFoundError(f"Dataset file not found: {dataset_path}")
    return dataset_path


def _resolve_lpms(
    lpm_cfg: TemporalLpmModelsCfg,
    configuration_directory: Path,
) -> tuple[list[str], Path]:
    """Resolve the requested models and their parameter directory."""
    models = DEFAULT_LPMS.copy() if lpm_cfg.list is None else list(lpm_cfg.list)
    if not models:
        raise ValueError("lpm_models.list must be a non-empty list.")
    directory = resolve_from(
        configuration_directory,
        lpm_cfg.directory or DIRECTORY_LPM_DATA,
    )
    if not directory.is_dir():
        raise ValueError(f"lpm_models.directory is not a directory: {directory}")
    return models, directory


def _load_concentrations(
    dataset_path: Path,
    error_rel: float | None,
    missing_error_rel: float = 0.01,
) -> Concentrations:
    """Load observations and fill missing relative errors when requested."""
    concentrations = Concentrations.from_file(dataset_path)
    if error_rel is not None and concentrations.frame[ERROR_COLUMN].min() == 0:
        concentrations.set_relative_errors(float(error_rel))
    resolve_observation_errors(
        concentrations,
        missing_error_relative_fraction=missing_error_rel,
    )
    return concentrations


def _case_frames(observations: Concentrations, mode: str):
    """Return the observation subsets required by one workflow mode."""
    if mode == "span":
        return [("span_full", observations.frame)]
    cases = [
        (
            f"date_{_format_date_label(date)}",
            observations.frame[observations.frame["date"] == date],
        )
        for date in sorted(observations.frame["date"].unique())
    ]
    labels = [label for label, _frame in cases]
    if len(labels) != len(set(labels)):
        raise ValueError("Distinct observation dates produce colliding case labels")
    return cases


def _run_temporal_cases(
    observations: Concentrations,
    mode_root: Path,
    mode: str,
    models: list[str],
    lpm_directory: Path,
    cal_cfg: TemporalCalibrationCfg,
    figures_cfg: TemporalFiguresCfg,
) -> list[Path]:
    """Execute every observation-subset and LPM combination."""
    written_case_dirs = []
    for date_label, frame in _case_frames(observations, mode):
        case_data = Concentrations.from_dataframe(frame)
        case_dir = result_subdirectory(mode_root, date_label)
        written_case_dirs.append(case_dir)
        if figures_cfg.temporal or figures_cfg.distributions:
            figure = plot_observations_overview(
                case_data,
                filename=case_dir / "00_observations_overview.png",
                title="Observed concentrations before calibration",
            )
            import matplotlib.pyplot as plt

            plt.close(figure)
        for lpm_type in models:
            _run_calibration(
                observations=case_data,
                lpm_type=lpm_type,
                output_dir=result_subdirectory(case_dir, lpm_type),
                lpm_directory=lpm_directory,
                cal_cfg=cal_cfg,
                figures_cfg=figures_cfg,
            )
    return written_case_dirs


def _prepare_context(params_path: str | Path) -> TemporalContext:
    """Resolve a temporal configuration into immutable runtime context."""
    config_path = Path(params_path).resolve()
    configuration_directory = configuration_root(config_path)
    params = _load_params_validated(config_path)
    dataset_path = _resolve_dataset(params.dataset, configuration_directory)
    models, lpm_directory = _resolve_lpms(
        params.lpm_models,
        configuration_directory,
    )
    observations = _load_concentrations(
        dataset_path,
        params.dataset.error_rel,
        params.dataset.missing_error_rel,
    )
    results_root = _results_root(params.results, configuration_directory)
    output_directory = result_subdirectory(
        result_subdirectory(
            result_subdirectory(results_root, params.results.study_name),
            dataset_path.stem,
        ),
        params.workflow.mode,
    )
    return TemporalContext(
        config_path=config_path,
        configuration_directory=configuration_directory,
        params=params,
        dataset_path=dataset_path,
        mode=params.workflow.mode,
        models=models,
        lpm_directory=lpm_directory,
        observations=observations,
        output_directory=output_directory,
    )


def _scientific_input_paths(context: TemporalContext) -> list[Path]:
    """Return every observation, model, and tracer resource used by the run."""
    return [
        context.dataset_path,
        *(context.lpm_directory / model for model in context.models),
        *(
            DIRECTORY_TRACER_DATA / tracer
            for tracer in context.observations.observation_tracer_names()
        ),
    ]


def run_temporal(params_path: Path) -> Path:
    """
    Execute temporal MH calibration based on a YAML configuration.

    Parameters
    ----------
    params_path : Path
        Path to the YAML configuration file.

    Notes
    -----
    Minimal YAML example::

        dataset:
          file: examples/natural/ploemeur_temporal/data/ori_ploemeur_F09_2005_2024.txt
          error_rel: 0.2
        lpm_models:
          list: ["exp_shifted", "ig", "ig_shifted"]
          directory: data_core/data_lpm
        workflow:
          mode: span
        calibration:
          mh_nsteps: 1000
          burn_in: 0.2
          nskip: 10
          lpm_number: 0
          seed_enabled: true
          seed: 12345
        figures:
          temporal: true
          distributions: true
        results:
          use_default: true
          study_name: temporal
          directory: ""

    Output layout::

        <results_root>/<study_name>/<dataset_stem>/<mode>/
          concentrations.txt
          span_full/ or date_<decimal_year>/
            <lpm_type>/
              parameters_calibration.txt
              results_calibration.txt
              lpm_stats_calibrated.txt
              Metropolis_Hastings/
                concentration_times.png
                concentrations_all_models.txt
                distributions.txt
                distributions_stats.txt

    Only ``dataset.file`` is required. Workflow mode, calibration controls,
    result location, LPM selection, and figure options all have validated
    defaults; see the configuration reference for their exact values.
    """
    context = _prepare_context(params_path)
    begin_result_run(context.output_directory)
    context.observations.frame.to_csv(
        context.output_directory / "concentrations.txt",
        sep="\t",
        index=False,
    )
    written_case_dirs = _run_temporal_cases(
        context.observations,
        context.output_directory,
        context.mode,
        context.models,
        context.lpm_directory,
        context.params.calibration,
        context.params.figures,
    )
    write_result_manifest(
        context.output_directory,
        workflow="temporal",
        config_path=context.config_path,
        input_paths=_scientific_input_paths(context),
        details={
            "dataset": context.dataset_path.name,
            "mode": context.mode,
            "lpms": context.models,
            "observation_error_policy": {
                "error_rel": context.params.dataset.error_rel,
                "missing_error_rel": context.params.dataset.missing_error_rel,
                "transformations": context.observations.error_provenance,
            },
            "case_directories": [
                path.relative_to(context.output_directory).as_posix()
                for path in written_case_dirs
            ],
        },
    )

    if len(written_case_dirs) == 1:
        return written_case_dirs[0]
    return context.output_directory
