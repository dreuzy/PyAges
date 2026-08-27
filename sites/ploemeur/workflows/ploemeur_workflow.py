# -*- coding: utf-8 -*-
# Copyright (c) 2021-2026 Centre national de la recherche scientifique (CNRS)
# Contributor: Jean-Raynald de Dreuzy
# SPDX-License-Identifier: CECILL-2.1

"""
Ploemeur workflow orchestration.

Coordinates the loading of observation data, construction of calibration jobs,
and execution of Metropolis-Hastings calibrations for the Ploemeur site.

"""

from __future__ import annotations

import copy
import multiprocessing as mp
import tempfile
from pathlib import Path
from typing import Any

import yaml

from pyages.calibration.methods.metropolis_hastings import MetropolisHastings, MHConfig
from pyages.calibration.problem import CalibrationProblem
from pyages.concentrations import Concentrations
from pyages.concentrations.concentrations_time import display_concentration_chronicles
from pyages.concentrations.schema import ERROR_COLUMN
from pyages.config.paths import (
    ROOT_DIRECTORY,
    ROOT_DIRECTORY_RESULTS,
    result_subdirectory,
)
from pyages.config.runtime import DisplayOptions
from pyages.lpm.plotting.sample_diagnostics import plot_prior_comparison
from sites.ploemeur.config.models import (
    ObservationMetadataConfig,
    PloemeurWorkflowConfig,
    PriorPipelinePresets,
    WellDateConfig,
)
from sites.ploemeur.observations.ploemeur import observation_path
from sites.ploemeur.workflows.job_builder import build_jobs
from sites.ploemeur.workflows.path_helpers import (
    calibrated_prior_name,
    data_file_path,
    data_selection_filename,
    prior_file_path,
    results_dir_for_case,
    results_folder,
    workflow_temp_folder,
)

TIME_SPAN_AND_PRIOR_MODES = {
    "cumulative",
    "successive",
    "span_full",
    "successive_with_prior",
    "span_with_prior",
}


def load_yaml_file(path: Path) -> dict[str, Any]:
    """Load a required YAML mapping."""
    yaml_path = Path(path)
    if not yaml_path.is_file():
        raise FileNotFoundError(f"YAML file not found: {yaml_path}")
    with yaml_path.open("r", encoding="utf-8") as handle:
        payload = yaml.safe_load(handle)
    if not isinstance(payload, dict):
        raise ValueError(f"Expected a YAML mapping in {yaml_path}")
    return payload


def resolve_lpm_directory(path_str: str | Path) -> Path:
    """Resolve an LPM parameter directory, allowing repo-relative paths."""
    path = Path(path_str)
    if not path.is_absolute():
        path = ROOT_DIRECTORY / path
    return path.resolve()


def resolve_results_directory(path_str: str | Path) -> Path:
    """Resolve a results directory, allowing repo-relative paths."""
    path = Path(path_str)
    if not path.is_absolute():
        path = ROOT_DIRECTORY / path
    return path.resolve()


def validate_time_span_and_prior_mode(mode: str) -> None:
    """Validate that a time-span mode is recognized."""
    if mode not in TIME_SPAN_AND_PRIOR_MODES:
        allowed = ", ".join(sorted(TIME_SPAN_AND_PRIOR_MODES))
        raise ValueError(
            f"Unknown time_span_and_prior mode '{mode}'. Allowed: {allowed}."
        )


def load_concentrations(
    file_path: str | Path,
    error_concentrations: float,
    display,
    output_dir: str | Path,
) -> Concentrations:
    """Load concentrations, apply relative errors, display, and write outputs."""
    cdata = Concentrations.from_file(file_path)
    if cdata.cv[ERROR_COLUMN].min() == 0:
        cdata.error_affect_from_value(error_concentrations)
    cdata.display(display)
    cdata.cv.to_csv(
        data_file_path(output_dir, "concentrations.txt"), sep="\t", index=False
    )
    return cdata


def load_observations_well_dates(
    params: dict[str, Any],
) -> dict[str, dict[str, int]]:
    """Load well date ranges from params or the shared observations YAML."""
    observations = params.get("observations", {})
    well_dates = observations.get("well_dates") or {}
    if well_dates:
        return {
            well: WellDateConfig.model_validate(date_range).model_dump()
            for well, date_range in well_dates.items()
        }
    observations_path = (
        ROOT_DIRECTORY / "sites" / "ploemeur" / "params" / "ploemeur_observations.yaml"
    )
    metadata = ObservationMetadataConfig.model_validate(
        load_yaml_file(observations_path)
    )
    return {
        well: date_range.model_dump()
        for well, date_range in metadata.well_dates.items()
    }


def load_prior_pipeline_presets():
    """Load shared prior pipeline presets from YAML."""
    presets_path = (
        ROOT_DIRECTORY / "sites" / "ploemeur" / "params" / "prior_pipeline_presets.yaml"
    )
    return PriorPipelinePresets.model_validate(load_yaml_file(presets_path)).root


def validate_well_dates(
    wells: list[str], well_dates: dict[str, dict[str, int]]
) -> None:
    """Validate that well_dates cover wells and point to existing data files."""
    if not wells:
        return
    if not well_dates:
        raise ValueError(
            "observations.well_dates must be provided when observations.wells is set."
        )
    missing_dates = [well for well in wells if well not in well_dates]
    if missing_dates:
        raise ValueError(f"Missing well_dates entries for wells: {missing_dates}")
    missing_files = []
    for well in wells:
        date_range = well_dates.get(well, {})
        start = date_range.get("start")
        end = date_range.get("end")
        if start is None or end is None:
            raise ValueError(
                f"observations.well_dates.{well} must define start and end years."
            )
        dates = f"{start}_{end}"
        file_path = observation_path(well, dates)
        if not file_path.exists():
            missing_files.append(str(file_path))
    if missing_files:
        raise ValueError(
            "Missing observation files:\n"
            + "\n".join(f"- {path}" for path in missing_files)
        )


# Proxy function for parallel simulation
def _perform_pod(pod):
    """Execute one calibration job in a worker process."""
    pod.perform()


class SimulationStrategy:
    """
    Ploemeur workflow configuration and execution engine.

    Reads parameters from YAML, expands the selected prior pipeline presets into
    per-step options, builds jobs, and runs the calibration workflow.
    """

    def __init__(self, prior_pipeline=None, params=None):
        """Initialize a workflow strategy for a given prior pipeline preset."""
        if prior_pipeline is None:
            raise ValueError("prior_pipeline must be provided.")
        if params is None:
            raise ValueError("params must be provided.")

        config = validate_workflow_params(params)
        self.prior_pipeline = prior_pipeline
        self._apply_prior_pipeline_preset(prior_pipeline)

        self.observations_cfg = config.observations
        self.workflow_cfg = config.workflows
        self.execution_cfg = config.execution
        self.results_cfg = config.results
        lpm_number = config.calibration.lpm_number or max(
            min(config.calibration.mh_nsteps // 50, 5000), 10
        )
        self.calibration_cfg = config.calibration.model_copy(
            update={"lpm_number": lpm_number}
        )
        self.lpm_types_default = config.lpm_models.default
        self.lpm_types_by_well = config.lpm_models.by_well
        self.lpm_directory = str(resolve_lpm_directory(config.lpm_models.directory))
        if config.results.use_default:
            self.results_root = str(ROOT_DIRECTORY_RESULTS)
        else:
            results_path = resolve_results_directory(config.results.directory)
            results_path.mkdir(parents=True, exist_ok=True)
            self.results_root = str(results_path)

    def _apply_prior_pipeline_preset(self, prior_pipeline):
        """Apply one strictly validated prior-pipeline preset."""
        presets = load_prior_pipeline_presets()
        if prior_pipeline in presets:
            preset = presets[prior_pipeline]
            self.time_span_and_prior = [
                step.time_span_and_prior for step in preset.steps
            ]
            self.prior = [step.prior for step in preset.steps]
            self.likelihood = [step.likelihood for step in preset.steps]
            self.prior_folder = [step.prior_folder for step in preset.steps]
            self.folder = preset.folder
            return
        available = ", ".join(sorted(presets))
        raise ValueError(
            f"Unknown prior_pipeline preset '{prior_pipeline}'. "
            f"Available presets: {available}"
        )

    def execute(self):
        """
        Execute the workflow across all requested wells, modes, and errors.
        """
        jobs = build_jobs(
            self.observations_cfg.conc_error_rel,
            self.time_span_and_prior,
            self.prior,
            self.likelihood,
            self.prior_folder,
            self.observations_cfg.wells,
            self.observations_cfg.well_dates,
            self.lpm_types_default,
            self.lpm_types_by_well,
            self.folder,
        )
        total_jobs = len(jobs)
        with tempfile.TemporaryDirectory(prefix="pyages-ploemeur-") as temp_directory:
            for idx, job in enumerate(jobs, start=1):
                self._execute_job(
                    *job,
                    run_index=idx,
                    run_total=total_jobs,
                    observation_directory=temp_directory,
                )

    def _execute_job(
        self,
        well,
        dates,
        lpm_types,
        file_root,
        time_span_and_prior_mode,
        conc_error_rel,
        prior,
        likelihood,
        prior_folder,
        run_index: int,
        run_total: int,
        observation_directory: str,
    ):
        """
        Prepare and execute all date/LPM cases in one workflow job.
        """
        self._print_run_summary(
            well=well,
            dates=dates,
            lpm_types=lpm_types,
            time_span_and_prior_mode=time_span_and_prior_mode,
            conc_error_rel=conc_error_rel,
            prior=prior,
            likelihood=likelihood,
            prior_folder=prior_folder,
            run_index=run_index,
            run_total=run_total,
        )
        pods = self._prepare_run(
            well,
            dates,
            lpm_types,
            file_root,
            time_span_and_prior_mode,
            conc_error_rel,
            prior,
            likelihood,
            prior_folder,
            observation_directory,
        )
        self._run_pods(pods)

    def _print_run_summary(
        self,
        well: str,
        dates: str,
        lpm_types: list[str],
        time_span_and_prior_mode: str,
        conc_error_rel: float,
        prior: bool,
        likelihood: bool,
        prior_folder: str,
        run_index: int,
        run_total: int,
    ) -> None:
        """Print a concise summary of the run being executed."""
        lpm_display = ", ".join(lpm_types) if lpm_types else "none"
        print(
            "[Ploemeur] "
            f"{run_index}/{run_total} "
            f"well={well} "
            f"years={dates} "
            f"mode={time_span_and_prior_mode} "
            f"error={conc_error_rel} "
            f"prior={prior}({prior_folder or 'none'}) "
            f"likelihood={likelihood} "
            f"lpm={lpm_display}"
        )

    def _prepare_run(
        self,
        well,
        dates,
        lpm_types,
        file_root,
        time_span_and_prior_mode,
        conc_error_rel,
        prior,
        likelihood,
        prior_folder,
        observation_directory,
    ):
        """Prepare inputs and pods for a single (well, mode) run."""
        files = _observation_files(
            well,
            dates,
            time_span_and_prior_mode,
            self.workflow_cfg.breakups,
            directory=observation_directory,
        )
        if self._mode_requires_prior(time_span_and_prior_mode):
            prior_corresp = _build_prior_correspondence(
                well,
                dates,
                time_span_and_prior_mode,
                self.workflow_cfg.breakups,
                directory=observation_directory,
            )
        else:
            prior_corresp = None

        dir_out, _, _ = results_folder(file_root, self.results_root)

        pods = []
        for lpm in lpm_types:
            for well_date in files:
                if prior_corresp is not None:
                    prior_file = prior_file_path(
                        dir_out,
                        prior_corresp,
                        well_date,
                        conc_error_rel,
                        lpm,
                        prior_folder,
                    )
                else:
                    prior_file = ""
                pod = PloemeurSingleRun(
                    dir_out,
                    well_date,
                    conc_error_rel,
                    lpm,
                    self.calibration_cfg.explo_res,
                    self.calibration_cfg.mh_nsteps,
                    prior,
                    likelihood,
                    self.calibration_cfg.lpm_number,
                    self.calibration_cfg.seed_enabled,
                    self.calibration_cfg.seed,
                    directory_lpm=self.lpm_directory,
                    observation_directory=observation_directory,
                    prior_file=prior_file,
                    time_span_and_prior_mode=time_span_and_prior_mode,
                    initial_params=self.calibration_cfg.initial_params,
                )
                pods.append(pod)

        return pods

    @staticmethod
    def _mode_requires_prior(time_span_and_prior_mode):
        """Return True when the workflow mode relies on a prior file."""
        return time_span_and_prior_mode in ("successive_with_prior", "span_with_prior")

    def _run_pods(self, pods):
        """Run prepared pods either in parallel or sequentially."""
        if self.execution_cfg.parallel:
            proc_nb = (
                int(mp.cpu_count())
                if self.execution_cfg.auto_proc_nb
                else self.execution_cfg.proc_nb
            )
            with mp.Pool(proc_nb) as pool:
                pool.map(_perform_pod, pods)
        else:
            for pod in pods:
                pod.perform()


def _write_observation_selection(well, dates, start, end, directory=None):
    """
    Selection of concentrations by year
        + Stores selected data in another file
        + Returns output file (same directory)

    Parameters
    ----------
    well: str
        well name, ef F09
    dates: str
        Min_Max years in the format: 2005_2020
    start, end: int
        Go by pairs
        start: 2015
        end:   2018

    Returns
    -------
    file_out: str
        File name of the output file
        eg 'F09_2005_2005'

    """

    directory = directory or workflow_temp_folder()
    # Loads concentrations
    cdata = Concentrations.from_file(observation_path(well, dates))
    df = cdata.cv
    # Selects concentrations within the given age range
    dfselec = df.loc[(df["date"] >= start) & (df["date"] <= (end + 1))]
    # Writes data in a file
    file_out = data_selection_filename(well, start, max(dfselec["date"]))
    dfselec.to_csv(data_file_path(directory, file_out), sep="\t", index=False)
    return file_out


def _periods_years(well, dates, time_span_and_prior_mode, breakups=()):
    """
    Sampling years available for this well
    # years: array of int, List of years
    #        ex. [2005, 2006, 2007, 2010, 2013, 2014, 2015, 2016, 2017, 2018, 2019, 2020]

    time_span_and_prior_mode must be one of:
        cumulative, successive, span_full, successive_with_prior, span_with_prior.
    """
    validate_time_span_and_prior_mode(time_span_and_prior_mode)
    cdata = Concentrations.from_file(observation_path(well, dates))
    sampling_years = sorted({int(value) for value in cdata.cv["date"]})

    start = []
    end = []
    if (
        time_span_and_prior_mode == "span_full"
        or time_span_and_prior_mode == "span_with_prior"
    ):
        # One full span, optionally supplemented by spans split at break years.
        if time_span_and_prior_mode == "span_full":
            start.append(sampling_years[0])
            end.append(sampling_years[-1])
        for breakyear in breakups:
            if breakyear > sampling_years[0] and breakyear < sampling_years[-1]:
                start = start + [sampling_years[0], breakyear]
                end = end + [breakyear, sampling_years[-1]]
        if len(start) == 0:
            start.append(sampling_years[0])
            end.append(sampling_years[-1])
    else:
        for i in range(len(sampling_years) - 1):
            if (
                time_span_and_prior_mode == "successive"
                or time_span_and_prior_mode == "successive_with_prior"
            ):
                # Adjacent pairs of sampling years.
                start.append(sampling_years[i])
                end.append(sampling_years[i + 1])
            elif time_span_and_prior_mode == "cumulative":
                # Every interval starts at the first sampling year.
                start.append(sampling_years[0])
                end.append(sampling_years[i + 1])
            else:
                raise ValueError(
                    f"Unsupported time_span_and_prior_mode '{time_span_and_prior_mode}'."
                )

    return start, end, sampling_years


def _observation_files(
    well, dates, time_span_and_prior_mode, breakups=(), directory=None
):
    """
    Creates and Returns list of files according to time_span_and_prior_mode "cumulative" or "successive"

    Parameters
    ----------
    time_span_and_prior_mode: str
        cumulative: all years from start to end of dates
        successive: one year independently of the other years
        span_full: only the span of years between ending and intermediary years
        successive_with_prior: successive with a prior from a span stage
        span_with_prior: span_full with a prior from a previous stage
    breakups: list of int
        years of breakup at which hydrological regimes have changed (objectivally), eg. drastic changes of pumping rates

    Returns
    -------
    files: array of str
        List of corresponding file names, eg:
        ['F09_2005_2005', 'F09_2005_2006', 'F09_2005_2007', 'F09_2005_2010', 'F09_2005_2013', 'F09_2005_2014', 'F09_2005_2015', 'F09_2005_2016', 'F09_2005_2017', 'F09_2005_2018', 'F09_2005_2019']

    """
    validate_time_span_and_prior_mode(time_span_and_prior_mode)

    start, end = _periods_years(well, dates, time_span_and_prior_mode, breakups)[0:2]
    return [
        _write_observation_selection(
            well, dates, first_year, last_year, directory=directory
        )
        for first_year, last_year in zip(start, end, strict=False)
    ]


def _build_prior_correspondence(
    well, dates, time_span_and_prior_mode, breakups=(), directory=None
):
    """
    Correspondance matrix between
        - single years
        - multiple years that should give the a priori for the single years
    At most one hydrological breakup is supported.
    Valid for modes: successive_with_prior, span_with_prior.
    Returns
    -------
    dataframe such as :
            file_current     file_prior
        0  F09_2005_2005  F09_2005_2010
        0  F09_2006_2006  F09_2005_2010
        0  F09_2007_2007  F09_2005_2010
        0  F09_2010_2010  F09_2005_2010
        0  F09_2013_2013  F09_2012_2020
        0  F09_2014_2014  F09_2012_2020
        0  F09_2015_2015  F09_2012_2020
        0  F09_2016_2016  F09_2012_2020
        0  F09_2017_2017  F09_2012_2020
        0  F09_2018_2018  F09_2012_2020
        0  F09_2019_2019  F09_2012_2020
        0  F09_2020_2020  F09_2012_2020
    """
    # Successive years start, end and files
    if len(breakups) > 1:
        raise ValueError("At most one hydrological breakup is supported.")
    if time_span_and_prior_mode == "span_with_prior":
        start_suc, end_suc, _ = _periods_years(well, dates, "span_with_prior", breakups)
        files_suc = _observation_files(
            well, dates, "span_with_prior", breakups, directory=directory
        )
    elif time_span_and_prior_mode == "successive_with_prior":
        start_suc, end_suc, _ = _periods_years(well, dates, "successive", breakups)
        files_suc = _observation_files(
            well, dates, "successive", breakups, directory=directory
        )
    else:
        raise ValueError(
            "Prior correspondence requires successive_with_prior or span_with_prior."
        )
    files_prior = _observation_files(
        well, dates, "span_full", breakups, directory=directory
    )
    correspondence = {}
    for filename, start, _ in zip(files_suc, start_suc, end_suc, strict=False):
        if time_span_and_prior_mode == "span_with_prior":
            temp = files_prior[0]
        elif time_span_and_prior_mode == "successive_with_prior":
            if len(files_prior) != 3:
                temp = files_prior[0]
            else:
                if start < breakups[0]:
                    temp = files_prior[1]
                else:
                    temp = files_prior[2]
        correspondence[filename] = temp

    return correspondence


class PloemeurSingleRun:
    """
    Run a single calibration case for one well and one date range.

    Parameters
    ----------
    directory_results: str
        Base output directory for results.
    well_date: str
        Well/date identifier (e.g. "F09_2005_2024").
    error_concentrations: float
        Relative concentration error to apply when missing.
    lpm_type: str
        LPM model name for the calibration.
    explo_res: int
        Number of models used for exploration/forward uncertainty.
    mh_nsteps: int
        Number of MH steps for the Metropolis-Hastings run.
    prior: bool
        Whether to include a prior in the calibration.
    likelihood: bool
        Whether to include likelihood in the calibration.
    lpm_number: int
        Number of LPM samples kept for output distributions.
    prior_file: str
        Optional prior file path for prior-informed runs.
    time_span_and_prior_mode: str
        Mode describing the time span and prior usage for this run.

    """

    def __init__(
        self,
        directory_results,
        well_date,
        error_concentrations,
        lpm_type,
        explo_res,
        mh_nsteps,
        prior,
        likelihood,
        lpm_number,
        seed_enabled,
        seed,
        directory_lpm,
        observation_directory=None,
        prior_file="",
        time_span_and_prior_mode="",
        initial_params=None,
    ):
        """Initialize the single-case workflow runner."""
        validate_time_span_and_prior_mode(time_span_and_prior_mode)
        self.time_span_and_prior_mode = time_span_and_prior_mode
        # ---------------- CONCENTRATIONS DATA ------------------
        # Concentration data
        observation_directory = observation_directory or workflow_temp_folder()
        self.file_ploemeur = data_file_path(observation_directory, well_date)
        self.file_stem = Path(self.file_ploemeur).name
        self.error_concentrations = error_concentrations

        # ---------------- LPM MODEL -----------------------------
        self.lpm_type = lpm_type
        self.directory_lpm = directory_lpm

        # ---------------- METROPOLIS HASTINGS --------------------
        # Method and Parameters
        mh_kwargs = {}
        if seed_enabled:
            mh_kwargs["seed"] = seed
        mh_config = MHConfig(
            nstep=mh_nsteps,
            prior_option=prior,
            likelihood=likelihood,
            monitor=True,
            display_traj=True,
            prior_type="empirical",
            prior_file=prior_file,
            initial_params=initial_params,
            componentwise_source="model",
            **mh_kwargs,
        )
        self.calibration_strategy = MetropolisHastings(config=mh_config)
        self.nmodels = explo_res
        self.lpm_number = lpm_number

        self.display = DisplayOptions()
        self.display.text = False
        self.display.figure = True
        self.display.figure_close = True
        self.display.figure_save = True
        self.display.directory = results_dir_for_case(
            directory_results, self.file_stem, lpm_type
        )

    def concentration_preparation(self):
        """
        Load and prepare concentration data for a single case.

        Applies a relative error when missing, displays data, and writes the
        normalized file into the results directory.
        """
        file_path = self.file_ploemeur
        return load_concentrations(
            file_path=file_path,
            error_concentrations=self.error_concentrations,
            display=self.display,
            output_dir=self.display.directory,
        )

    def calibrate(self, cdata):
        """Run the configured Metropolis-Hastings calibration."""
        strategy = self.calibration_strategy

        # Prepare case-specific display options.
        display_options_case = copy.deepcopy(self.display)
        display_options_case.directory = result_subdirectory(
            self.display.directory, strategy.method
        )

        # Calibration
        problem = CalibrationProblem(
            cdata,
            self.lpm_type,
            display_options=display_options_case,
            lpm_directory=self.directory_lpm,
            sample_count=self.nmodels,
            explore_reachable=False,
        ).prepare()
        lpm_results = strategy.run(problem)
        strategy.write_calibrated_lpm(
            lpm_results,
            file_prior=calibrated_prior_name(
                self.file_stem, self.error_concentrations, self.lpm_type
            ),
            folder_prior=self.time_span_and_prior_mode,
        )
        strategy.analysis_calibration(lpm_results)

        # Tracers + distributions
        display_concentration_chronicles(
            cdata,
            lpm_results,
            strategy.method,
            self.display,
            lpm_number=self.lpm_number,
        )
        if strategy.prior.option:
            plot_prior_comparison(
                lpm_results,
                directory=display_options_case.directory,
                prior=strategy.prior,
            )

        return lpm_results

    def perform(self):
        """Run a single Metropolis-Hastings calibration."""
        cdata = self.concentration_preparation()
        self.calibrate(cdata)


# ----------------------------------------------
# ----------------- LAUNCHERS ------------------
# ----------------------------------------------


def load_workflow_params(params_path: Path) -> dict[str, Any]:
    """
    Load workflow parameters from YAML.

    Parameters
    ----------
    params_path: Path
        Path to the workflow YAML file.

    Returns
    -------
    dict
        Parsed YAML content.
    """
    if params_path is None:
        raise ValueError("params_path is required")
    config = PloemeurWorkflowConfig.model_validate(load_yaml_file(Path(params_path)))
    return config.model_dump(mode="python")


def validate_workflow_params(
    params: dict[str, Any] | PloemeurWorkflowConfig,
) -> PloemeurWorkflowConfig:
    """
    Validate the complete workflow configuration and referenced files.

    Checks that wells and date ranges are defined, presets exist, and data files
    referenced by the observations are available on disk.
    """
    config = PloemeurWorkflowConfig.model_validate(params)
    raw_params = config.model_dump(mode="python")
    well_dates = load_observations_well_dates(raw_params)
    observations = config.observations.model_copy(
        update={
            "well_dates": {
                well: WellDateConfig.model_validate(date_range)
                for well, date_range in well_dates.items()
            }
        }
    )
    config = config.model_copy(update={"observations": observations})
    validate_well_dates(
        observations.wells,
        {
            well: date_range.model_dump()
            for well, date_range in observations.well_dates.items()
        },
    )

    presets = load_prior_pipeline_presets()
    unknown = [name for name in config.workflows.prior_pipeline if name not in presets]
    if unknown:
        raise ValueError(f"Unknown prior_pipeline presets: {unknown}")

    lpm_path = resolve_lpm_directory(config.lpm_models.directory)
    if not lpm_path.is_dir():
        raise ValueError(f"lpm_models.directory does not exist: {lpm_path}")
    missing_lpm_configs = [
        model
        for model in sorted(
            set(config.lpm_models.default).union(
                *map(set, config.lpm_models.by_well.values())
            )
        )
        if not (lpm_path / model / "params.yaml").is_file()
    ]
    if missing_lpm_configs:
        raise ValueError(
            f"Missing params.yaml for configured LPMs: {missing_lpm_configs}"
        )
    return config


def run_workflow(params_path: Path) -> None:
    """
    Run the Ploemeur workflow using the provided YAML parameters.

    Parameters
    ----------
    params_path: Path
        Path to the workflow YAML file.
    """
    mp.freeze_support()
    params = load_workflow_params(params_path)
    config = validate_workflow_params(params)
    for pipeline in config.workflows.prior_pipeline:
        SimulationStrategy(prior_pipeline=pipeline, params=config).execute()
