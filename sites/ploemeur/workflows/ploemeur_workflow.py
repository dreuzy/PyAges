# -*- coding: utf-8 -*-
"""
Ploemeur workflow orchestration.

Coordinates the loading of observation data, construction of calibration jobs,
execution of Metropolis-Hastings/Simplex strategies, and postprocessing of
results for the Ploemeur site.

Copyright (c) 2025 Jean-Raynald de Dreuzy, CNRS
Author: Jean-Raynald de Dreuzy
"""

import sys
from pathlib import Path

repo_root = Path(__file__).resolve().parents[3]
for p in (repo_root, repo_root / "sources"):
    if str(p) not in sys.path:
        sys.path.insert(0, str(p))

import copy
import functools
import multiprocessing as mp
from dataclasses import dataclass
from typing import Any, Dict, List, Optional

import yaml
import global_parameters as gp
import concentrations.concentrations as co
from concentrations import concentrations_time as ct

import calibration.utils.calibration_core as calbas
import calibration.methods.simplex as csimp
import calibration.methods.metropolis_hastings as cMH

from sites.ploemeur.observations import ploemeur as ploemeur_obs
from sites.ploemeur.postprocessing import appli_ploemeur_results_comparison as aprc
from sites.ploemeur.workflows.job_builder import build_jobs
from observations.loader import (
    build_observation_path,
    load_observation_concentrations,
)
from sites.ploemeur.workflows.path_helpers import (
    calibrated_prior_name,
    data_file_path,
    data_selection_filename,
    prior_file_path,
    results_dir_for_case,
    results_folder,
    workflow_temp_folder,
    workflow_temp_file_path,
)

TIME_SPAN_AND_PRIOR_MODES = {
    "cumulative",
    "successive",
    "span_full",
    "successive_with_prior",
    "span_with_prior",
}


def load_yaml_file(path: Path) -> Dict[str, Any]:
    """Load a YAML file if it exists, returning a dict."""
    if not path or not Path(path).exists():
        return {}
    with Path(path).open("r", encoding="utf-8") as handle:
        return yaml.safe_load(handle) or {}


def resolve_lpm_directory(path_str: str) -> Path:
    """Resolve an LPM parameter directory, allowing repo-relative paths."""
    path = Path(path_str)
    if not path.is_absolute():
        path = repo_root / path
    return path


def resolve_results_directory(path_str: str) -> Path:
    """Resolve a results directory, allowing repo-relative paths."""
    path = Path(path_str)
    if not path.is_absolute():
        path = repo_root / path
    return path


def validate_time_span_and_prior_mode(mode: str) -> None:
    """Validate that a time-span mode is recognized."""
    if mode not in TIME_SPAN_AND_PRIOR_MODES:
        allowed = ", ".join(sorted(TIME_SPAN_AND_PRIOR_MODES))
        raise ValueError(f"Unknown time_span_and_prior mode '{mode}'. Allowed: {allowed}.")


def load_concentrations(
    file_path: str,
    error_concentrations: float,
    display,
    output_dir: str,
) -> co.Concentrations:
    """Load concentrations, apply relative errors, display, and write outputs."""
    cdata = co.Concentrations(file_load=True, file_name=file_path)
    if min(cdata.cv.iloc[:, gp.ERROR]) == 0:
        cdata.error_affect_from_value(error_concentrations)
    cdata.display(display)
    cdata.cv.to_csv(data_file_path(output_dir, "concentrations.txt"), sep="\t", index=False)
    return cdata


def load_observations_well_dates(params: Dict[str, Any]) -> Dict[str, Dict[str, int]]:
    """Load well date ranges from params or the shared observations YAML."""
    observations = params.get("observations", {})
    well_dates = observations.get("well_dates") or {}
    if not well_dates:
        observations_path = repo_root / "sites" / "ploemeur" / "params" / "ploemeur_observations.yaml"
        observations_data = load_yaml_file(observations_path)
        if observations_path.exists() and not observations_data:
            raise ValueError(f"Failed to load observations from {observations_path}")
        well_dates = observations_data.get("well_dates", {})
    return well_dates


def load_prior_pipeline_presets() -> Dict[str, Any]:
    """Load shared prior pipeline presets from YAML."""
    presets_path = repo_root / "sites" / "ploemeur" / "params" / "prior_pipeline_presets.yaml"
    presets = load_yaml_file(presets_path)
    if presets_path.exists() and not presets:
        raise ValueError(f"Failed to load presets from {presets_path}")
    return presets


def validate_well_dates(wells: List[str], well_dates: Dict[str, Dict[str, int]]) -> None:
    """Validate that well_dates cover wells and point to existing data files."""
    if not wells:
        return
    if not well_dates:
        raise ValueError("observations.well_dates must be provided when observations.wells is set.")
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
        file_path = build_observation_path(
            ploemeur_obs.ploemeur_ori_folder(),
            "ori_ploemeur_",
            well,
            dates,
        )
        if not file_path.exists():
            missing_files.append(str(file_path))
    if missing_files:
        raise ValueError(
            "Missing observation files:\n"
            + "\n".join(f"- {path}" for path in missing_files)
        )


@dataclass
class ObservationsConfig:
    """Observation settings loaded from YAML."""
    conc_error_rel: Optional[List[float]] = None
    wells: Optional[List[str]] = None
    well_dates: Optional[Dict[str, Dict[str, int]]] = None

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "ObservationsConfig":
        return cls(
            conc_error_rel=data.get("conc_error_rel"),
            wells=data.get("wells"),
            well_dates=data.get("well_dates"),
        )


@dataclass
class WorkflowConfig:
    """Workflow-level configuration settings."""
    breakups: Optional[List[int]] = None
    prior_pipeline: Optional[List[str]] = None

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "WorkflowConfig":
        return cls(
            breakups=data.get("breakups"),
            prior_pipeline=data.get("prior_pipeline"),
        )


@dataclass
class ExecutionConfig:
    """Execution settings (parallelization, worker selection)."""
    parallel: Optional[bool] = None
    auto_proc_nb: Optional[bool] = None
    proc_nb: Optional[int] = None

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "ExecutionConfig":
        return cls(
            parallel=data.get("parallel"),
            auto_proc_nb=data.get("auto_proc_nb"),
            proc_nb=data.get("proc_nb"),
        )


@dataclass
class ResultsConfig:
    """Results output configuration."""
    use_default: Optional[bool] = None
    directory: Optional[str] = None

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "ResultsConfig":
        return cls(
            use_default=data.get("use_default"),
            directory=data.get("directory"),
        )


@dataclass
class CalibrationConfig:
    """Calibration settings used by Metropolis-Hastings and FUQ."""
    explo_res: Optional[int] = None
    mh_nsteps: Optional[int] = None
    lpm_number: Optional[int] = None
    seed_enabled: Optional[bool] = None
    seed: Optional[int] = None

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "CalibrationConfig":
        return cls(
            explo_res=data.get("explo_res"),
            mh_nsteps=data.get("mh_nsteps"),
            lpm_number=data.get("lpm_number"),
            seed_enabled=data.get("seed_enabled"),
            seed=data.get("seed"),
        )


# Proxy function for parallel simulation 
def perform(pod,i): 
    pod[i].perform()


class SimulationStrategy: 
    """
    Ploemeur workflow configuration and execution engine.

    Reads parameters from YAML, expands the selected prior pipeline presets into
    per-step options, builds jobs, and runs the calibration workflow.
    """
    
    def __init__(self, prior_pipeline = None, params=None):
        """Initialize a workflow strategy for a given prior pipeline preset."""
        if prior_pipeline is None:
            raise ValueError("prior_pipeline must be provided.")

        self.prior_pipeline = prior_pipeline
        self.__apply_prior_pipeline_preset(prior_pipeline, params)

        self.observations_cfg = ObservationsConfig()
        self.workflow_cfg = WorkflowConfig()
        self.execution_cfg = ExecutionConfig()
        self.results_cfg = ResultsConfig()
        self.calibration_cfg = CalibrationConfig()
        self.lpm_types_default = []
        self.lpm_types_by_well = {}
        self.results_root = str(gp.ROOT_DIRECTORY_RESULTS)

        if params:
            self.__apply_params(params)


    def __apply_params(self, params):
        """Apply YAML parameters to the workflow configuration."""
        sim = params.get("observations", {})
        calibration = params.get("calibration", {})
        execution = params.get("execution", {})
        results = params.get("results", {})
        lpm_models = params.get("lpm_models", {})
        workflow_cfg = params.get("workflows", {})

        obs_cfg = ObservationsConfig.from_dict(sim)
        cal_cfg = CalibrationConfig.from_dict(calibration)
        exec_cfg = ExecutionConfig.from_dict(execution)
        res_cfg = ResultsConfig.from_dict(results)
        wf_cfg = WorkflowConfig.from_dict(workflow_cfg)

        well_dates = obs_cfg.well_dates or load_observations_well_dates(params)
        if not well_dates:
            raise ValueError(
                "observations.well_dates must be provided in the YAML configuration or "
            "sites/ploemeur/params/ploemeur_observations.yaml."
            )
        if not obs_cfg.conc_error_rel:
            raise ValueError("observations.conc_error_rel must be provided in the YAML configuration.")
        if not obs_cfg.wells:
            raise ValueError("observations.wells must be provided in the YAML configuration.")
        if not wf_cfg.prior_pipeline:
            raise ValueError("workflows.prior_pipeline must be provided in the YAML configuration.")
        if cal_cfg.lpm_number:
            lpm_number = cal_cfg.lpm_number
        elif cal_cfg.mh_nsteps:
            lpm_number = max(min(int(cal_cfg.mh_nsteps/50),5000),10)
        else:
            lpm_number = 0

        if cal_cfg.explo_res is None or cal_cfg.explo_res <= 0:
            raise ValueError("calibration.explo_res must be provided in the YAML configuration.")
        if cal_cfg.mh_nsteps is None or cal_cfg.mh_nsteps <= 0:
            raise ValueError("calibration.mh_nsteps must be provided in the YAML configuration.")
        if lpm_number <= 0:
            raise ValueError(
                "calibration.lpm_number must be provided (>0) or inferred from mh_nsteps."
            )
        seed_enabled = bool(cal_cfg.seed_enabled) if cal_cfg.seed_enabled is not None else False
        if seed_enabled and cal_cfg.seed is None:
            raise ValueError(
                "calibration.seed must be provided when calibration.seed_enabled is true."
            )
        seed_value = cal_cfg.seed if seed_enabled else None

        if "default" in lpm_models:
            self.lpm_types_default = lpm_models["default"]
        if "by_well" in lpm_models:
            self.lpm_types_by_well = lpm_models["by_well"]
        if not self.lpm_types_default:
            raise ValueError("lpm_models.default must be provided in the YAML configuration.")

        directory_lpm = lpm_models.get("directory") or str(gp.DIRECTORY_LPM_DATA)
        lpm_path = resolve_lpm_directory(directory_lpm)
        if not lpm_path.exists():
            raise ValueError(f"lpm_models.directory does not exist: {lpm_path}")

        self.observations_cfg = ObservationsConfig(
            conc_error_rel=obs_cfg.conc_error_rel,
            wells=obs_cfg.wells,
            well_dates=well_dates,
        )
        self.workflow_cfg = WorkflowConfig(
            breakups=wf_cfg.breakups,
            prior_pipeline=wf_cfg.prior_pipeline,
        )
        self.execution_cfg = ExecutionConfig(
            parallel=exec_cfg.parallel,
            auto_proc_nb=exec_cfg.auto_proc_nb,
            proc_nb=exec_cfg.proc_nb,
        )
        self.results_cfg = ResultsConfig(
            use_default=res_cfg.use_default,
            directory=res_cfg.directory,
        )
        self.calibration_cfg = CalibrationConfig(
            explo_res=cal_cfg.explo_res,
            mh_nsteps=cal_cfg.mh_nsteps,
            lpm_number=lpm_number,
            seed_enabled=seed_enabled,
            seed=seed_value,
        )
        self.lpm_directory = str(lpm_path)
        if res_cfg.use_default is None or res_cfg.use_default:
            self.results_root = str(gp.ROOT_DIRECTORY_RESULTS)
        else:
            if not res_cfg.directory:
                raise ValueError(
                    "results.directory must be provided when results.use_default is false."
                )
            results_path = resolve_results_directory(res_cfg.directory)
            results_path.mkdir(parents=True, exist_ok=True)
            self.results_root = str(results_path)


    def __apply_prior_pipeline_preset(self, prior_pipeline, params):
        """Apply prior pipeline presets from YAML if available, else fallback."""
        presets = load_prior_pipeline_presets()
        if prior_pipeline in presets:
            preset = presets[prior_pipeline]
            steps = preset.get("steps")
            if steps:
                self.time_span_and_prior = [step["time_span_and_prior"] for step in steps]
                self.prior = [step["prior"] for step in steps]
                self.likelihood = [step["likelihood"] for step in steps]
                self.prior_folder = [step["prior_folder"] for step in steps]
            else:
                self.time_span_and_prior = preset["time_span_and_prior"]
                self.prior = preset["prior"]
                self.likelihood = preset["likelihood"]
                self.prior_folder = preset["prior_folder"]
            self.folder = preset["folder"]
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
        for idx, job in enumerate(jobs, start=1):
            self.__execute_parallel(*job, run_index=idx, run_total=total_jobs)

    def __execute_parallel(
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
    ):
        """
        Parallelizable Execution over all combibations of 
            - dates 
            - lpms 
        """
        self.__print_run_summary(
            well=well,
            dates=dates,
            lpm_types=lpm_types,
            time_span_and_prior_mode=time_span_and_prior_mode,
            conc_error_rel=conc_error_rel,
            prior=prior,
            likelihood=likelihood,
            prior_folder=prior_folder,
            file_root=file_root,
            run_index=run_index,
            run_total=run_total,
        )
        run_ctx = self.__prepare_run(
            well,
            dates,
            lpm_types,
            file_root,
            time_span_and_prior_mode,
            conc_error_rel,
            prior,
            likelihood,
            prior_folder,
        )
        self.__run_pods(run_ctx["pods"])
        self.__postprocess(run_ctx["lpm_types"], run_ctx["date_file"], run_ctx["dir_root"])

    def __print_run_summary(
        self,
        well: str,
        dates: str,
        lpm_types: List[str],
        time_span_and_prior_mode: str,
        conc_error_rel: float,
        prior: bool,
        likelihood: bool,
        prior_folder: str,
        file_root: str,
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

    def __prepare_run(
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
    ):
        """Prepare inputs and pods for a single (well, mode) run."""
        files = files_years(well, dates, time_span_and_prior_mode, self.workflow_cfg.breakups)
        if self.__mode_requires_prior(time_span_and_prior_mode):
            prior_corresp = correspondance_matrix(
                well,
                dates,
                time_span_and_prior_mode,
                self.workflow_cfg.breakups,
            )
        else:
            prior_corresp = None

        dir_out, dir_root, date_file = results_folder(file_root, self.results_root)

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
                pod = ploemeur_one_date(
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
                    prior_file=prior_file,
                    time_span_and_prior_mode=time_span_and_prior_mode,
                )
                pods.append(pod)

        return {
            "pods": pods,
            "lpm_types": lpm_types,
            "dir_root": dir_root,
            "date_file": date_file,
        }

    @staticmethod
    def __mode_requires_prior(time_span_and_prior_mode):
        """Return True when the workflow mode relies on a prior file."""
        return time_span_and_prior_mode in ("successive_with_prior", "span_with_prior")

    def __run_pods(self, pods):
        """Run prepared pods either in parallel or sequentially."""
        if self.execution_cfg.parallel == True:
            proc_nb = (
                int(mp.cpu_count())
                if self.execution_cfg.auto_proc_nb
                else self.execution_cfg.proc_nb
            )
            pool = mp.Pool(proc_nb)
            for i in range(len(pods)):
                pool.apply_async(perform, args=(pods, i))
            pool.close()
            pool.join()
        else:
            for pod in pods:
                pod.perform()

    def __postprocess(self, lpm_types, date_file, dir_root):
        """Aggregate outputs and trigger postprocessing figures."""
        for lpm in lpm_types:
            aprc.load_and_display(date_file, lpm, dir_root)



def ploemeur_data_selection(well,dates,start,end):
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
    
    directory = workflow_temp_folder()
    # Loads concentrations 
    cdata=load_observation_concentrations(
        ploemeur_obs.ploemeur_ori_folder(),
        "ori_ploemeur_",
        well,
        dates,
    )
    df = cdata.cv
    # Selects concentrations within the given age range
    dfselec = df.loc[(df['date'] >= start) & (df['date'] <= (end+1))]
    # Writes data in a file 
    file_out = data_selection_filename(well, start, max(dfselec["date"]))
    dfselec.to_csv(data_file_path(directory, file_out), sep='\t', index=False)
    return file_out


def periods_years(well,dates,time_span_and_prior_mode,breakups=[]): 
    """
    Sampling years avialble for this well
    # years: array of int, List of years
    #        ex. [2005, 2006, 2007, 2010, 2013, 2014, 2015, 2016, 2017, 2018, 2019, 2020]

    time_span_and_prior_mode must be one of:
        cumulative, successive, span_full, successive_with_prior, span_with_prior.
    """
    validate_time_span_and_prior_mode(time_span_and_prior_mode)
    cdata=load_observation_concentrations(
        ploemeur_obs.ploemeur_ori_folder(),
        "ori_ploemeur_",
        well,
        dates,
    )
    sampling_years=sorted(functools.reduce(lambda l, x: l.append(int(x)) or l if int(x) not in l else l, cdata.cv['date'], []))
    
    start=[];end=[]
    if time_span_and_prior_mode == "span_full" or time_span_and_prior_mode =="span_with_prior": 
        # start: [2005,2005,2012]
        # end:   [2020,2012,2020]
        if time_span_and_prior_mode == "span_full" : 
            start.append(sampling_years[0])
            end.append(sampling_years[-1])
        for breakyear in breakups: 
            if breakyear > sampling_years[0] and breakyear < sampling_years[-1]: 
                start = start + [sampling_years[0],breakyear]
                end = end + [breakyear,sampling_years[-1]]    
        if len(start)==0:
            start.append(sampling_years[0])
            end.append(sampling_years[-1])
    else: 
        for i in range(len(sampling_years)-1):
            if time_span_and_prior_mode == "successive" or time_span_and_prior_mode == "successive_with_prior":
                # start: [2005, 2005, 2005, 2005, 2005, 2005, 2005, 2005, 2005, 2005, 2005]
                # end:   [2006, 2007, 2010, 2013, 2014, 2015, 2016, 2017, 2018, 2019, 2020]
                start.append(sampling_years[i])  
                end.append(sampling_years[i+1])   
            elif time_span_and_prior_mode == "cumulative":
                # start: [2005, 2005, 2005, 2005, 2005, 2005, 2005, 2005, 2005, 2005, 2005]
                # end:   [2006, 2007, 2010, 2013, 2014, 2015, 2016, 2017, 2018, 2019, 2020]
                start.append(sampling_years[0])  
                end.append(sampling_years[i+1])
            else:
                raise ValueError(f"Unsupported time_span_and_prior_mode '{time_span_and_prior_mode}'.")

    return start,end,sampling_years



def files_years(well,dates,time_span_and_prior_mode,breakups=[]): 
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

    start,end=periods_years(well,dates,time_span_and_prior_mode,breakups)[0:2]

    # Corresponding file names for each pair of years
    # cumulative: ['F09_2005_2005', 'F09_2005_2006', 'F09_2005_2007', 'F09_2005_2010', 'F09_2005_2013', 'F09_2005_2014', 'F09_2005_2015', 'F09_2005_2016', 'F09_2005_2017', 'F09_2005_2018', 'F09_2005_2019']
    # successive: ['F09_2005_2005', 'F09_2006_2006', 'F09_2007_2007', 'F09_2010_2010', 'F09_2013_2013', 'F09_2014_2014', 'F09_2015_2015', 'F09_2016_2016', 'F09_2017_2017', 'F09_2018_2018', 'F09_2019_2019']
    files = []
    for k in range(len(start)):
        files.append(ploemeur_data_selection(well,dates,start[k],end[k]))
    return files


def correspondance_matrix(well,dates,time_span_and_prior_mode,breakups=[]): 
    """
    Correspondance matrix between
        - single years
        - multiple years that should give the a priori for the single years
    Assumes that breakups is of size 1 and only 1!!!
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
    if time_span_and_prior_mode == "span_with_prior": 
        start_suc,end_suc,sampling_years_suc=periods_years(well,dates,"span_with_prior",breakups)
        files_suc = files_years(well,dates,"span_with_prior",breakups)
    else : 
        start_suc,end_suc,sampling_years_suc=periods_years(well,dates,"successive",breakups)
        files_suc = files_years(well,dates,"successive",breakups)
    # Prior year span start, end and files
    start_prior,end_prior,sampling_years_prior=periods_years(well,dates,"span_full",breakups)
    files_prior = files_years(well,dates,"span_full",breakups)
    # df: correspondance matrix 
    dic = {}
    for file, start, end in zip (files_suc, start_suc, end_suc):
        if time_span_and_prior_mode == "span_with_prior": 
            temp = files_prior[0]
        elif time_span_and_prior_mode == "successive_with_prior": 
            if len(files_prior) != 3: 
                temp=files_prior[0]
            else: 
                if start < breakups[0] : 
                    temp = files_prior[1]
                else : 
                    temp = files_prior[2]
        dic[file]=temp
        
    return dic

        
class ploemeur_one_date:
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
    MH_nsteps: int
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
        MH_nsteps,
        prior,
        likelihood,
        lpm_number,
        seed_enabled,
        seed,
        directory_lpm,
        prior_file="",
        time_span_and_prior_mode="",
    ):
        """Initialize the single-case workflow runner."""
        validate_time_span_and_prior_mode(time_span_and_prior_mode)
        self.time_span_and_prior_mode = time_span_and_prior_mode
        # ---------------- CONCENTRATIONS DATA ------------------
        # Concentration data 
        self.directory_ploemeur = ploemeur_obs.ploemeur_data_folder()
        self.file_ploemeur = data_file_path(workflow_temp_folder(), well_date)
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
        mh_config = cMH.MHConfig(
            nstep=MH_nsteps,
            prior_option=prior,
            likelihood=likelihood,
            lpm_number=lpm_number,
            monitor=True,
            display_traj=True,
            prior_type="empirical",
            prior_file=prior_file,
            **mh_kwargs,
        )
        self.calstrat_MH = cMH.MetropolisHastings(config=mh_config)  # JR: 250000
        # self.calstrat[1].MH_step.define_by_prop(0.005)
        self.calstrat_MH.MH_step.define_by_value()
        # self.calstrat_MH.set_nmodels(explo_res)

        
        # ---------------- FORWARD UNCERTAINTY QUANTIFICATION -----------------------------
        self.calstrat_FUQ = csimp.Simplex("forward_uncertainty_quantification",
                                                    init_multiples_n=2,fuq_n=2) #JR: 5,50
        
                
        # ---------------- CALIBRATION ANALYSIS --------------------
        self.__nmodels = explo_res
        
        # ---- DISPLAY OPTIONS + ROOT OUTPUT DIRECTORY ------------
        # Output options
        self.display = gp.display_options()
        self.display.text = False
        self.display.figure = True
        self.display.figure_close = True
        self.display.figure_save = True    
        self.display.directory = results_dir_for_case(directory_results, self.file_stem, lpm_type)
        self.display_reachconc = False


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
    
    
    def calibration(self, cdata, calstrat):
        """Run a calibration with the provided strategy (MH or FUQ)."""
    
        # Préparer display_options
        display_options_case = copy.deepcopy(self.display)
        display_options_case.directory = gp.results_directory(self.display.directory, calstrat.method)
    
        # Calibration
        calib_basis = calbas.CalibrationCore(
            cdata,
            self.lpm_type,
            display_options=display_options_case,
            directory_lpm=self.directory_lpm,
            nmodels=self.__nmodels,
            reachconc=self.display_reachconc,
        )
        calib_basis.prepare()
        calstrat.update_calibbasis(calib_basis)
        lpm_results = calstrat.perform()
        calstrat.write_calibrated_lpm(
            lpm_results,
            file_prior=calibrated_prior_name(
                self.file_stem, self.error_concentrations, self.lpm_type
            ),
            folder_prior=self.time_span_and_prior_mode,
        )
        calstrat.analysis_calibration(lpm_results)
    
        # Tracers + distributions
        ct.display_concentration_chronicles(
            cdata,
            lpm_results,
            calstrat.method,
            self.display,
            span_or_suc=self.time_span_and_prior_mode,
            lpm_number=self.calstrat_MH.config.lpm_number,
        )
        if self.display_reachconc: 
            lpm_results.display_parameters_dist(self_method=calstrat.method, directory=display_options_case.directory)
        if calstrat.method == "Metropolis_Hastings" and calstrat.prior.option: 
            lpm_results.display_parameters_dist_comp_apriori(directory=display_options_case.directory, prior=calstrat.prior)
        if self.display_reachconc: 
            lpm_results.display_concentrations_dist(self_method=calstrat.method, concentrations_reference=cdata, directory=display_options_case.directory)
    
        return lpm_results
        
        

    def perform(self): 
        """ 
        Run a single Metropolis-Hastings calibration.
        """
        # ---------------- CONCENTRATIONS------------------------
        cdata = self.concentration_preparation()
        # ---------------- CALIBRATION with MH -----------------
        self.calibration(cdata,self.calstrat_MH)


    def perform_method_comparison(self): 
        """ 
        Run MH + FUQ and compare their outputs.
        """
        
        # ---------------- CONCENTRATIONS------------------------
        cdata = self.concentration_preparation()
        
        # ---------------- CALIBRATION --------------------------
        lpm_results=[None]*2
        lpm_results[0]=self.calibration(cdata,self.calstrat_MH)
        lpm_results[1]=self.calibration(cdata,self.calstrat_FUQ)
        
        # ---------------- SYNTHETIC FIGURES --------------------
        lpm_results[0].display_parameters_dist(self_method=self.calstrat_MH.method,lpm_reference=None,lpm_2nd=lpm_results[1],lpm_2nd_method=self.calstrat_FUQ.method,directory=self.display.directory)
        lpm_results[0].display_concentrations_dist(self_method=self.calstrat_MH.method,concentrations_reference=cdata,lpm_2nd=lpm_results[1],lpm_2nd_method=self.calstrat_FUQ.method,directory=self.display.directory)
        

# ----------------------------------------------
# ----------------- LAUNCHERS ------------------
# ----------------------------------------------

def load_workflow_params(params_path: Path):
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
    if not params_path:
        return {}
    return load_yaml_file(Path(params_path))


def validate_workflow_params(params: Dict[str, Any]) -> None:
    """
    Validate minimal consistency of workflow parameters.

    Checks that wells and date ranges are defined, presets exist, and data files
    referenced by the observations are available on disk.
    """
    observations = params.get("observations", {})
    workflow_cfg = params.get("workflows", {})
    lpm_models = params.get("lpm_models", {})
    results_cfg = params.get("results", {})

    if "prior_pipeline_presets" in params:
        raise ValueError(
            "prior_pipeline_presets must be defined in "
            "sites/ploemeur/params/prior_pipeline_presets.yaml (no local override)."
        )

    wells = observations.get("wells", [])
    well_dates = observations.get("well_dates", {}) or load_observations_well_dates(params)
    validate_well_dates(wells, well_dates)

    prior_pipeline = workflow_cfg.get("prior_pipeline", [])
    if prior_pipeline:
        presets = load_prior_pipeline_presets()
        unknown = [name for name in prior_pipeline if name not in presets]
        if unknown:
            raise ValueError(f"Unknown prior_pipeline presets: {unknown}")
        for name in prior_pipeline:
            preset = presets.get(name, {})
            steps = preset.get("steps", [])
            for step in steps:
                mode = step.get("time_span_and_prior")
                if mode is not None:
                    validate_time_span_and_prior_mode(mode)

    by_well = lpm_models.get("by_well", {})
    if wells and by_well:
        extra = [well for well in by_well.keys() if well not in wells]
        if extra:
            raise ValueError(f"lpm_models.by_well has wells not listed in observations.wells: {extra}")

    if lpm_models.get("directory"):
        lpm_path = resolve_lpm_directory(lpm_models["directory"])
        if not lpm_path.exists():
            raise ValueError(f"lpm_models.directory does not exist: {lpm_path}")

    if results_cfg.get("use_default") is False:
        results_dir = results_cfg.get("directory")
        if not results_dir:
            raise ValueError(
                "results.directory must be provided when results.use_default is false."
            )


def run_workflow(params_path: Path = None):
    """
    Run the Ploemeur workflow using the provided YAML parameters.

    Parameters
    ----------
    params_path: Path
        Path to the workflow YAML file.
    """
    mp.freeze_support()
    params = load_workflow_params(params_path)
    validate_workflow_params(params)
    workflow_cfg = params.get("workflows", {})
    prior_pipeline = workflow_cfg.get("prior_pipeline")
    if not prior_pipeline:
        raise ValueError("workflows.prior_pipeline must be provided in the YAML configuration.")

    for pipeline in prior_pipeline:
        simulstart = SimulationStrategy(prior_pipeline=pipeline, params=params)
        # Execution de la simulation
        simulstart.execute()


if __name__ == "__main__":
    run_workflow()
    
    
    






