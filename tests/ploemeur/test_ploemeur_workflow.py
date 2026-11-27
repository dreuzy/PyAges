# Copyright (c) 2021-2026 Centre national de la recherche scientifique (CNRS)
# Contributor: Jean-Raynald de Dreuzy
# SPDX-License-Identifier: CECILL-2.1

from pathlib import Path
from types import SimpleNamespace

import matplotlib
import matplotlib.pyplot as plt
import pandas as pd
import pytest

from sites.ploemeur.config.models import PloemeurCalibrationConfig
from sites.ploemeur.observations import ploemeur as ploemeur_observations
from sites.ploemeur.workflows import ploemeur_workflow
from sites.ploemeur.workflows import single_run as ploemeur_single_run


def test_parallel_worker_uses_headless_backend_and_closes_figures(monkeypatch):
    calls = []
    pod = SimpleNamespace(perform=lambda: calls.append("perform"))

    monkeypatch.setattr(
        matplotlib,
        "use",
        lambda backend, *, force: calls.append(("backend", backend, force)),
    )
    monkeypatch.setattr(plt, "close", lambda target: calls.append(("close", target)))

    ploemeur_workflow._perform_pod(pod)

    assert calls == [
        ("backend", "Agg", True),
        "perform",
        ("close", "all"),
    ]


def test_observation_path_encodes_ploemeur_naming_convention(tmp_path):
    path = ploemeur_observations.observation_path("F09", "2005_2024", root=tmp_path)

    assert path == (
        tmp_path
        / "sites"
        / "ploemeur"
        / "data"
        / "ori"
        / "ori_ploemeur_F09_2005_2024.txt"
    )
    assert isinstance(path, Path)


def test_observation_selection_creates_temp_directory(monkeypatch, tmp_path):
    temp_directory = tmp_path / "missing" / "temp"
    observations = SimpleNamespace(
        frame=pd.DataFrame(
            {
                "date": [2005.0, 2006.0],
                "cfc11": [1.0, 2.0],
            }
        )
    )
    monkeypatch.setattr(
        ploemeur_workflow,
        "workflow_temp_folder",
        lambda: str(temp_directory),
    )
    monkeypatch.setattr(
        ploemeur_workflow.Concentrations,
        "from_file",
        classmethod(lambda cls, path: observations),
    )

    filename = ploemeur_workflow._write_observation_selection(
        "F09", "2005_2006", 2005, 2006
    )

    assert filename == "F09_2005_2006"
    assert (temp_directory / filename).is_file()


def test_single_run_uses_current_mh_configuration_contract(tmp_path):
    calibration = PloemeurCalibrationConfig(
        exploration_resolution=20,
        posterior_draw_count=10,
        metropolis_hastings={
            "nsteps": 200,
            "burn_in": 0.2,
            "thinning": 1,
            "chains": 4,
            "seed": 12345,
            "pilot": {"enabled": True, "nsteps": 20},
            "diagnostics": {"require_convergence": False},
        },
    )
    runner = ploemeur_single_run.PloemeurSingleRun(
        directory_results=tmp_path,
        well_date="F09_2005_2006",
        error_concentrations=0.2,
        lpm_type="exp_shifted",
        calibration_config=calibration,
        prior=False,
        likelihood=True,
        directory_lpm=tmp_path,
        observation_directory=tmp_path,
        time_span_and_prior_mode="successive",
    )

    assert runner.chain_config.nsteps == 200
    assert runner.chain_config.seed == 12345
    assert runner.chain_config.prior_option is False
    assert runner.chain_config.prior_type == "empirical"
    assert runner.run_config.chains == 4
    assert runner.run_config.pilot.enabled is True
    assert runner.run_config.diagnostics.require_convergence is False


def test_single_run_routes_all_managed_mh_stages_and_exports_pool(
    monkeypatch, tmp_path
):
    calibration = PloemeurCalibrationConfig(
        exploration_resolution=20,
        posterior_draw_count=10,
        metropolis_hastings={
            "nsteps": 100,
            "thinning": 1,
            "chains": 2,
            "seed": 12345,
            "pilot": {"enabled": True, "nsteps": 20},
            "diagnostics": {"require_convergence": False},
        },
    )
    single_run = ploemeur_single_run.PloemeurSingleRun(
        directory_results=tmp_path,
        well_date="F09_2005_2006",
        error_concentrations=0.2,
        lpm_type="exp_shifted",
        calibration_config=calibration,
        prior=False,
        likelihood=True,
        directory_lpm=tmp_path,
        observation_directory=tmp_path,
        time_span_and_prior_mode="successive",
    )
    stage_directories = []
    analyzed = []
    exported = []
    pooled = object()

    class Template:
        lpm = object()

        def clone_prepared(self, *, display_options):
            stage_directories.append(Path(display_options.directory))
            return object()

        def analyze(self, results):
            analyzed.append(results)

    template = Template()

    class Problem:
        def __init__(self, *args, **kwargs):
            pass

        def prepare(self):
            return template

    def execute_mh_run(chain_config, run_config, directory, problem_builder):
        assert chain_config is single_run.chain_config
        assert run_config is single_run.run_config
        assert directory == Path(single_run.output_directory) / "Metropolis_Hastings"
        problem_builder(directory / "initialization")
        problem_builder(directory / "pilot" / "chain_001")
        problem_builder(directory / "chains" / "chain_001")
        problem_builder(directory / "chains" / "chain_002")
        return pooled

    monkeypatch.setattr(ploemeur_single_run, "CalibrationProblem", Problem)
    monkeypatch.setattr(ploemeur_single_run, "execute_mh_run", execute_mh_run)
    monkeypatch.setattr(
        ploemeur_single_run,
        "posterior_directory",
        lambda *args, **kwargs: tmp_path / "prior_distributions",
    )
    monkeypatch.setattr(ploemeur_single_run, "write_histograms", lambda *args: None)
    monkeypatch.setattr(
        ploemeur_single_run,
        "export_calibrated_chronicles",
        lambda *args, **kwargs: exported.append((args, kwargs)),
    )

    assert single_run.calibrate(object()) is pooled
    method = Path(single_run.output_directory) / "Metropolis_Hastings"
    assert stage_directories == [
        method / "initialization",
        method / "pilot" / "chain_001",
        method / "chains" / "chain_001",
        method / "chains" / "chain_002",
    ]
    assert analyzed == [pooled]
    assert len(exported) == 1


@pytest.mark.extensive
def test_single_run_managed_multichain_smoke_end_to_end(monkeypatch, tmp_path):
    """Exercise the site adapter with real observations and short chains."""
    monkeypatch.setenv("MPLBACKEND", "Agg")
    observations = tmp_path / "observations"
    well_date = ploemeur_workflow._write_observation_selection(
        "F09", "2005_2024", 2018, 2019, directory=observations
    )
    calibration = PloemeurCalibrationConfig(
        exploration_resolution=20,
        posterior_draw_count=10,
        metropolis_hastings={
            "nsteps": 100,
            "burn_in": 0.2,
            "thinning": 1,
            "chains": 4,
            "seed": 20260908,
            "pilot": {"enabled": True, "nsteps": 100, "burn_in": 0.5},
            "diagnostics": {"require_convergence": False},
        },
    )
    single_run = ploemeur_single_run.PloemeurSingleRun(
        directory_results=tmp_path / "results",
        well_date=well_date,
        error_concentrations=0.2,
        lpm_type="exp_shifted",
        calibration_config=calibration,
        prior=False,
        likelihood=True,
        directory_lpm=Path("sites/ploemeur/params_lpm"),
        observation_directory=observations,
        time_span_and_prior_mode="successive",
    )

    single_run.perform()

    method = Path(single_run.output_directory) / "Metropolis_Hastings"
    assert len(list((method / "chains").glob("chain_*"))) == 4
    assert (method / "mcmc_diagnostics.tsv").is_file()
    assert (method / "run_provenance.txt").is_file()
    assert (method / "lpm_dist_calibrated.txt").is_file()
