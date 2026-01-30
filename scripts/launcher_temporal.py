# -*- coding: utf-8 -*-
"""
Temporal Metropolis-Hastings launcher (didactic entrypoint).

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
------------------------------------------------------
1) Bootstrap execution (repo-direct vs installed)
   - We attempt to import `pyage` normally.
   - If that fails, we add the repo root to `sys.path`.
   - This makes the script runnable both after `pip install -e .`
     and directly from the repository.

2) Pydantic configuration validation (strict + explicit)
   - YAML is parsed into a typed schema (DatasetCfg, CalibrationCfg, ...).
   - This gives early, clear errors for missing fields, wrong types, and bounds.
   - It prevents silent defaults from masking misconfigurations.

3) Structured I/O + reproducibility
   - All paths are resolved relative to the repo root (if not absolute).
   - Results are written under a stable folder tree for regression testing.

Copyright (c) 2025 Jean-Raynald de Dreuzy, CNRS
Author: Jean-Raynald de Dreuzy
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path
from typing import Dict

# YAML parsing for config files (raw load before validation).
import yaml

# Bootstrap: allow "repo-direct" execution without installation.
# If pyage isn't importable, add the repo root to sys.path, then retry.
try:
    from pyage.config.bootstrap import ensure_repo_imports
except ModuleNotFoundError:
    repo_root = Path(__file__).resolve().parents[1]
    sys.path.insert(0, str(repo_root))
    from pyage.config.bootstrap import ensure_repo_imports

# Repo root used to resolve relative paths in YAML (dataset, results, etc.).
_bootstrap_root = ensure_repo_imports()
repo_root = _bootstrap_root or Path(__file__).resolve().parents[1]

# Core library imports (use pyage.* consistently to avoid duplicate modules).
import pyage.global_parameters as gp
import pyage.concentrations.concentrations as co
from pyage.concentrations import concentrations_time as ct
import pyage.calibration.utils.calibration_core as calbas
import pyage.calibration.methods.metropolis_hastings as cMH

from pydantic import ValidationError

# Shared Pydantic schemas live in pyage.config.models to keep launchers consistent.
from pyage.config.models import (
    TemporalCalibrationCfg,
    TemporalDatasetCfg,
    TemporalFiguresCfg,
    TemporalLpmModelsCfg,
    TemporalParams,
    TemporalResultsCfg,
    TemporalWorkflowCfg,
    TEMPORAL_VALID_MODES,
)


DEFAULT_LPMS = ["exp_shifted", "ig", "ig_shifted"]
VALID_MODES = TEMPORAL_VALID_MODES

def _load_yaml(path: Path) -> Dict:
    """
    Load a YAML file and return its contents as a dict.

    Parameters
    ----------
    path : Path
        Path to the YAML configuration file.

    Returns
    -------
    dict
        Parsed YAML content.

    Raises
    ------
    FileNotFoundError
        If the YAML file does not exist.
    """
    if not path or not path.exists():
        raise FileNotFoundError(f"Missing params file: {path}")
    with path.open("r", encoding="utf-8") as handle:
        return yaml.safe_load(handle) or {}


def _load_params_validated(path: Path) -> TemporalParams:
    """
    Load params and validate with Pydantic.
    """
    data = _load_yaml(path)
    # Pydantic raises a structured ValidationError that we convert to ValueError
    # for a cleaner CLI error message.
    try:
        return TemporalParams.model_validate(data)
    except ValidationError as exc:
        raise ValueError(f"Invalid launcher_temporal config:\n{exc}") from exc


def _resolve_path(path_str: str) -> Path:
    """
    Resolve repo-relative or absolute paths into an absolute Path.

    Parameters
    ----------
    path_str : str
        Absolute path or repo-relative path.

    Returns
    -------
    Path
        Absolute path resolved against the repository root if needed.
    """
    path = Path(path_str)
    if not path.is_absolute():
        path = repo_root / path
    return path


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


def _results_root(results_cfg: TemporalResultsCfg) -> Path:
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
        return Path(gp.ROOT_DIRECTORY_RESULTS)
    directory = results_cfg.directory
    if not directory:
        raise ValueError("results.directory must be set when use_default is false.")
    results_path = _resolve_path(directory)
    results_path.mkdir(parents=True, exist_ok=True)
    return results_path


def _prepare_display(output_dir: Path, figures_cfg: TemporalFiguresCfg) -> gp.display_options:
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
    display_options
        Configured display options instance.
    """
    display = gp.display_options()
    display.text = False
    display.figure = bool(figures_cfg.temporal or figures_cfg.distributions)
    display.figure_save = True
    display.figure_close = True
    display.directory = str(output_dir)
    return display


def _build_mh_config(cal_cfg: TemporalCalibrationCfg, lpm_number: int) -> cMH.MHConfig:
    """
    Build a Metropolis-Hastings configuration from YAML settings.

    Parameters
    ----------
    cal_cfg : dict
        YAML calibration section.
    lpm_number : int
        Number of samples to keep for output distributions.

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
        lpm_number=lpm_number,
        **mh_kwargs,
    )


def _run_calibration(
    cdata: co.Concentrations,
    lpm_type: str,
    output_dir: Path,
    lpm_directory: Path,
    cal_cfg: TemporalCalibrationCfg,
    figures_cfg: TemporalFiguresCfg,
    mode: str,
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
    mode : str
        Workflow mode: span or successive.
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
    calib_basis = calbas.CalibrationCore(
        cdata,
        lpm_type,
        display_options=display,
        directory_lpm=str(lpm_directory),
        nmodels=explo_res,
        reachconc=False,
    )
    calib_basis.prepare()

    # Metropolis-Hastings setup and execution.
    mh_config = _build_mh_config(cal_cfg, lpm_number)
    calstrat = cMH.MetropolisHastings(config=mh_config)
    calstrat.MH_step.define_by_value()
    calstrat.update_calibbasis(calib_basis)
    lpm_results = calstrat.perform()
    # Persist calibrated distributions/statistics.
    calstrat.write_calibrated_lpm(lpm_results)

    # Temporal figures (chronicles) if enabled.
    if figures_cfg.temporal:
        ct.display_concentration_chronicles(
            cdata,
            lpm_results,
            calstrat.method,
            display,
            time_span_mode=mode,
            lpm_number=lpm_number,
        )

    # Distribution figures if enabled.
    if figures_cfg.distributions:
        lpm_results.display_parameters_dist(
            self_method=calstrat.method,
            directory=display.directory,
        )
        lpm_results.display_concentrations_dist(
            self_method=calstrat.method,
            concentrations_reference=cdata,
            directory=display.directory,
        )


def run_temporal(params_path: Path) -> None:
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
          file: examples/ploemeur_temporal/data/ori_ploemeur_F09_2005_2024.txt
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
          directory: ""

    Output layout::

        <results_root>/ploemeur_temporal/<dataset_stem>/<mode>/
          span_full/ or date_<yyyy_xxxxxx>/
            <lpm_type>/
              parameters_calibration.txt
              results_calibration.txt
              lpm_stats_calibrated.txt
              lpm_param_dist_calibrated.txt
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
    # --- Load and validate configuration ---
    params = _load_params_validated(params_path)
    dataset_cfg: TemporalDatasetCfg = params.dataset
    cal_cfg: TemporalCalibrationCfg = params.calibration
    figures_cfg: TemporalFiguresCfg = params.figures
    workflow_cfg: TemporalWorkflowCfg = params.workflow
    lpm_cfg: TemporalLpmModelsCfg = params.lpm_models
    results_cfg: TemporalResultsCfg = params.results

    dataset_file = dataset_cfg.file
    if not dataset_file:
        raise ValueError("dataset.file is required.")
    dataset_path = _resolve_path(dataset_file)
    if not dataset_path.exists():
        raise FileNotFoundError(f"Dataset file not found: {dataset_path}")

    mode = workflow_cfg.mode
    if mode not in VALID_MODES:
        raise ValueError(f"workflow.mode must be one of {sorted(VALID_MODES)}.")

    # --- LPM model selection ---
    lpm_list = lpm_cfg.list or DEFAULT_LPMS
    if not isinstance(lpm_list, list) or not lpm_list:
        raise ValueError("lpm_models.list must be a non-empty list.")

    lpm_directory = lpm_cfg.directory or str(gp.DIRECTORY_LPM_DATA)
    lpm_directory_path = _resolve_path(lpm_directory)
    if not lpm_directory_path.exists():
        raise ValueError(f"lpm_models.directory does not exist: {lpm_directory_path}")

    # --- Load concentrations and apply errors if needed ---
    cdata = co.Concentrations(file_load=True, file_name=str(dataset_path))
    error_rel = dataset_cfg.error_rel
    if error_rel is not None and min(cdata.cv.iloc[:, gp.ERROR]) == 0:
        cdata.error_affect_from_value(float(error_rel))

    # --- Build results tree ---
    results_root = _results_root(results_cfg)
    base_root = gp.results_directory(str(results_root), "ploemeur_temporal")
    file_root = gp.results_directory(base_root, dataset_path.stem)
    mode_root = gp.results_directory(file_root, mode)

    # --- Decide which data subsets to calibrate ---
    if mode == "span":
        date_sets = [("span_full", cdata.cv)]
    else:
        dates = sorted(cdata.cv["date"].unique())
        date_sets = [
            (f"date_{_format_date_label(date)}", cdata.cv[cdata.cv["date"] == date])
            for date in dates
        ]

    # --- Run calibrations (each subset × each LPM) ---
    for date_label, df in date_sets:
        ccase = co.Concentrations(dataframe_load=True, dataframe_concentration=df.copy())
        case_dir = gp.results_directory(mode_root, date_label)
        for lpm_type in lpm_list:
            lpm_dir = gp.results_directory(case_dir, lpm_type)
            _run_calibration(
                cdata=ccase,
                lpm_type=lpm_type,
                output_dir=Path(lpm_dir),
                lpm_directory=lpm_directory_path,
                cal_cfg=cal_cfg,
                figures_cfg=figures_cfg,
                mode=mode,
            )


def _parse_args() -> argparse.Namespace:
    """
    Parse CLI arguments for the temporal launcher.

    Returns
    -------
    argparse.Namespace
        Parsed arguments with a required --params field.
    """
    parser = argparse.ArgumentParser(description="Temporal MH launcher (multi-date concentrations).")
    parser.add_argument("--params", required=True, help="Path to the YAML configuration file.")
    return parser.parse_args()


if __name__ == "__main__":
    args = _parse_args()
    run_temporal(Path(args.params))
