# -*- coding: utf-8 -*-
"""
Temporal Metropolis-Hastings launcher.

Runs MH calibration on a multi-date concentration file (ori_*.txt) and
produces temporal plots plus parameter/concentration distributions.

Modes
-----
- span: single calibration over the full time span
- successive: one calibration per observation date

Copyright (c) 2025 Jean-Raynald de Dreuzy, CNRS
Author: Jean-Raynald de Dreuzy
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path
from typing import Dict, Iterable, List

import yaml

repo_root = Path(__file__).resolve().parents[1]
for p in (repo_root, repo_root / "sources"):
    if str(p) not in sys.path:
        sys.path.insert(0, str(p))

import global_parameters as gp
import concentrations.concentrations as co
from concentrations import concentrations_time as ct
import calibration.utils.calibration_core as calbas
import calibration.methods.metropolis_hastings as cMH


DEFAULT_LPMS = ["exp_shifted", "ig", "ig_shifted"]
VALID_MODES = {"span", "successive"}


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


def _results_root(results_cfg: Dict) -> Path:
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
    use_default = results_cfg.get("use_default", True)
    if use_default:
        return Path(gp.ROOT_DIRECTORY_RESULTS)
    directory = results_cfg.get("directory", "")
    if not directory:
        raise ValueError("results.directory must be set when use_default is false.")
    results_path = _resolve_path(directory)
    results_path.mkdir(parents=True, exist_ok=True)
    return results_path


def _prepare_display(output_dir: Path, figures_cfg: Dict) -> gp.display_options:
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
    display.figure = bool(figures_cfg.get("temporal") or figures_cfg.get("distributions"))
    display.figure_save = True
    display.figure_close = True
    display.directory = str(output_dir)
    return display


def _build_mh_config(cal_cfg: Dict, lpm_number: int) -> cMH.MHConfig:
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
    seed_enabled = bool(cal_cfg.get("seed_enabled", False))
    seed_value = cal_cfg.get("seed") if seed_enabled else None
    mh_kwargs = {}
    if seed_enabled:
        mh_kwargs["seed"] = seed_value
    return cMH.MHConfig(
        nstep=int(cal_cfg.get("mh_nsteps", 1000)),
        burn_in=float(cal_cfg.get("burn_in", 0.2)),
        nskip=int(cal_cfg.get("nskip", 10)),
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
    cal_cfg: Dict,
    figures_cfg: Dict,
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
    explo_res = int(cal_cfg.get("explo_res", 20))
    mh_nsteps = int(cal_cfg.get("mh_nsteps", 1000))
    lpm_number = int(cal_cfg.get("lpm_number", 0))
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
    if figures_cfg.get("temporal", False):
        ct.display_concentration_chronicles(
            cdata,
            lpm_results,
            calstrat.method,
            display,
            span_or_suc=mode,
            lpm_number=lpm_number,
        )

    # Distribution figures if enabled.
    if figures_cfg.get("distributions", False):
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
          directory: data_core/data_LPM
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
    params = _load_yaml(params_path)
    dataset_cfg = params.get("dataset", {})
    cal_cfg = params.get("calibration", {})
    figures_cfg = params.get("figures", {})
    workflow_cfg = params.get("workflow", {})
    lpm_cfg = params.get("lpm_models", {})
    results_cfg = params.get("results", {})

    dataset_file = dataset_cfg.get("file")
    if not dataset_file:
        raise ValueError("dataset.file is required.")
    dataset_path = _resolve_path(dataset_file)
    if not dataset_path.exists():
        raise FileNotFoundError(f"Dataset file not found: {dataset_path}")

    mode = workflow_cfg.get("mode", "span")
    if mode not in VALID_MODES:
        raise ValueError(f"workflow.mode must be one of {sorted(VALID_MODES)}.")

    # --- LPM model selection ---
    lpm_list = lpm_cfg.get("list") or DEFAULT_LPMS
    if not isinstance(lpm_list, list) or not lpm_list:
        raise ValueError("lpm_models.list must be a non-empty list.")

    lpm_directory = lpm_cfg.get("directory") or str(gp.DIRECTORY_LPM_DATA)
    lpm_directory_path = _resolve_path(lpm_directory)
    if not lpm_directory_path.exists():
        raise ValueError(f"lpm_models.directory does not exist: {lpm_directory_path}")

    # --- Load concentrations and apply errors if needed ---
    cdata = co.Concentrations(file_load=True, file_name=str(dataset_path))
    error_rel = dataset_cfg.get("error_rel")
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
