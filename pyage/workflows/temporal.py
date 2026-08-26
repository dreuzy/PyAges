# -*- coding: utf-8 -*-
"""
Reusable temporal Metropolis-Hastings workflow.

What this example does
----------------------
This script runs a Metropolis-Hastings calibration on a multi-date concentration
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
   - All paths are resolved relative to the repo root (if not absolute).
   - Results are written under a stable folder tree for regression testing.

Copyright (c) 2025 Jean-Raynald de Dreuzy, CNRS
Author: Jean-Raynald de Dreuzy
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import cast

import pyage.calibration.methods.metropolis_hastings as cMH

# Core library imports (use pyage.* consistently to avoid duplicate modules).
import pyage.concentrations.concentrations as co
from pyage.calibration.problem import CalibrationProblem
from pyage.concentrations import concentrations_time as ct
from pyage.concentrations.schema import ERROR_COLUMN
from pyage.config.loading import resolve_from, validate_yaml_model

# Shared Pydantic schemas live in pyage.config.models to keep launchers consistent.
from pyage.config.models import (
    TemporalCalibrationCfg,
    TemporalDatasetCfg,
    TemporalFiguresCfg,
    TemporalLpmModelsCfg,
    TemporalParams,
    TemporalResultsCfg,
)
from pyage.config.paths import (
    DIRECTORY_LPM_DATA,
    ROOT_DIRECTORY_RESULTS,
    result_subdirectory,
)
from pyage.config.runtime import DisplayOptions
from pyage.lpm.distribution_plotting import display_concentration_distributions
from pyage.workflows.plots import (
    plot_observations_overview,
    plot_parameter_summary,
)
from pyage.workflows.result_manifest import write_result_manifest
from pyage.workflows.single_date_paths import configuration_root

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
    observations: co.Concentrations
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
    return f"{date_value:.6f}".rstrip("0").rstrip(".").replace(".", "_")


def _results_root(
    results_cfg: TemporalResultsCfg,
    configuration_directory: Path,
) -> Path:
    """
    Resolve the results root based on YAML options.

    Parameters
    ----------
    results_cfg : dict
        YAML results section with keys:
        - use_default : bool
        - directory : str

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
    figures_cfg : dict
        YAML figures section with keys:
        - temporal : bool
        - distributions : bool

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


def _build_mh_config(cal_cfg: TemporalCalibrationCfg) -> cMH.MHConfig:
    """
    Build a Metropolis-Hastings configuration from YAML settings.

    Parameters
    ----------
    cal_cfg : dict
        YAML calibration section.
    Returns
    -------
    MHConfig
        Metropolis-Hastings configuration object ready for calibration runs.
    """
    # Optional reproducibility: only attach a seed when enabled.
    seed_enabled = cal_cfg.seed_enabled
    seed_value = cal_cfg.seed if seed_enabled else None
    mh_kwargs = {}
    if seed_enabled:
        mh_kwargs["seed"] = seed_value
    return cMH.MHConfig(
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
        **mh_kwargs,
    )


def _run_calibration(
    cdata: co.Concentrations,
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
    cdata : Concentrations
        Concentration data (single-date or multi-date subset).
    lpm_type : str
        LPM name to calibrate (e.g., exp_shifted).
    output_dir : Path
        Output folder for this calibration.
    lpm_directory : Path
        Directory holding LPM parameter files (params.yaml).
    cal_cfg : dict
        Calibration parameters (mh_nsteps, burn_in, nskip, lpm_number, seed...).
    figures_cfg : dict
        Figure options (temporal/distributions).
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
        cdata,
        lpm_type,
        display_options=display,
        lpm_directory=lpm_directory,
        sample_count=explo_res,
        explore_reachable=False,
    ).prepare()

    # Metropolis-Hastings setup and execution.
    mh_config = _build_mh_config(cal_cfg)
    calstrat = cMH.MetropolisHastings(config=mh_config)
    lpm_results = calstrat.run(problem)
    # Persist calibrated distributions/statistics.
    calstrat.write_calibrated_lpm(lpm_results)

    # Temporal figures (chronicles) if enabled.
    if figures_cfg.temporal:
        ct.display_concentration_chronicles(
            cdata,
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
            display_concentration_distributions(
                lpm_results,
                self_method=calstrat.method,
                concentrations_reference=cdata,
                directory=display.directory,
            )


def _resolve_dataset(
    dataset_cfg: TemporalDatasetCfg,
    configuration_directory: Path,
) -> Path:
    """Resolve and validate the temporal observation file."""
    dataset_path = resolve_from(configuration_directory, dataset_cfg.file)
    if not dataset_path.exists():
        raise FileNotFoundError(f"Dataset file not found: {dataset_path}")
    return dataset_path


def _resolve_lpms(
    lpm_cfg: TemporalLpmModelsCfg,
    configuration_directory: Path,
) -> tuple[list[str], Path]:
    """Resolve the requested models and their parameter directory."""
    models = lpm_cfg.list or DEFAULT_LPMS
    if not models:
        raise ValueError("lpm_models.list must be a non-empty list.")
    directory = resolve_from(
        configuration_directory,
        lpm_cfg.directory or DIRECTORY_LPM_DATA,
    )
    if not directory.exists():
        raise ValueError(f"lpm_models.directory does not exist: {directory}")
    return models, directory


def _load_concentrations(
    dataset_path: Path,
    error_rel: float | None,
) -> co.Concentrations:
    """Load observations and fill missing relative errors when requested."""
    concentrations = co.Concentrations.from_file(dataset_path)
    if error_rel is not None and concentrations.cv[ERROR_COLUMN].min() == 0:
        concentrations.error_affect_from_value(float(error_rel))
    return concentrations


def _case_frames(cdata: co.Concentrations, mode: str):
    """Return the observation subsets required by one workflow mode."""
    if mode == "span":
        return [("span_full", cdata.cv)]
    return [
        (
            f"date_{_format_date_label(date)}",
            cdata.cv[cdata.cv["date"] == date],
        )
        for date in sorted(cdata.cv["date"].unique())
    ]


def _run_temporal_cases(
    cdata: co.Concentrations,
    mode_root: Path,
    mode: str,
    models: list[str],
    lpm_directory: Path,
    cal_cfg: TemporalCalibrationCfg,
    figures_cfg: TemporalFiguresCfg,
) -> list[Path]:
    """Execute every observation-subset and LPM combination."""
    written_case_dirs = []
    for date_label, frame in _case_frames(cdata, mode):
        case_data = co.Concentrations.from_dataframe(frame)
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
                cdata=case_data,
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
    observations = _load_concentrations(dataset_path, params.dataset.error_rel)
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
          span_full/ or date_<yyyy_xxxxxx>/
            <lpm_type>/
              parameters_calibration.txt
              results_calibration.txt
              lpm_stats_calibrated.txt
              Metropolis_Hastings/
                concentration_times.png
                concentrations_all_models.txt
                distributions.txt
                distributions_stats.txt

    Required YAML sections:
    - dataset.file
    - workflow.mode (span or successive)
    - calibration (mh_nsteps, burn_in, nskip, lpm_number, seed...)
    - results (use_default, directory)

    Optional sections:
    - dataset.error_rel
    - lpm_models.list, lpm_models.directory
    - figures.temporal, figures.distributions
    """
    context = _prepare_context(params_path)
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
        input_paths=[context.dataset_path],
        details={
            "dataset": context.dataset_path.name,
            "mode": context.mode,
            "lpms": context.models,
            "case_directories": [
                path.relative_to(context.output_directory).as_posix()
                for path in written_case_dirs
            ],
        },
    )

    if len(written_case_dirs) == 1:
        return written_case_dirs[0]
    return context.output_directory
