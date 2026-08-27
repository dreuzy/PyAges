# Copyright (c) 2021-2026 Centre national de la recherche scientifique (CNRS)
# Contributor: Jean-Raynald de Dreuzy
# SPDX-License-Identifier: CECILL-2.1

"""Filesystem contract tests for the Ploemeur workflow."""

from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from threading import Barrier
from types import SimpleNamespace

import pandas as pd

from sites.ploemeur.workflows import path_helpers
from sites.ploemeur.workflows import ploemeur_workflow as workflow


def test_workflow_temp_folder_creates_missing_directory(
    monkeypatch, tmp_path: Path
) -> None:
    data_directory = tmp_path / "missing" / "data"
    monkeypatch.setattr(
        path_helpers,
        "ploemeur_data_folder",
        lambda: str(data_directory),
    )

    workflow_directory = Path(path_helpers.workflow_temp_folder())

    assert workflow_directory == data_directory / "temp"
    assert workflow_directory.is_dir()


def _strategy_stub(
    monkeypatch, observed_directories: list[Path], barrier: Barrier
) -> workflow.SimulationStrategy:
    strategy = object.__new__(workflow.SimulationStrategy)
    strategy.observations_cfg = SimpleNamespace(
        conc_error_rel=[0.05], wells=["F09"], well_dates={}
    )
    strategy.time_span_and_prior = ["span_full"]
    strategy.prior = [False]
    strategy.likelihood = [True]
    strategy.prior_folder = [""]
    strategy.lpm_types_default = ["exp_shifted"]
    strategy.lpm_types_by_well = {}
    strategy.folder = "test"

    monkeypatch.setattr(workflow, "build_jobs", lambda *args: [("job",)])

    def record_directory(*args, **kwargs) -> None:
        directory = Path(kwargs["observation_directory"])
        assert directory.is_dir()
        (directory / "selection").write_text("data", encoding="utf-8")
        observed_directories.append(directory)
        barrier.wait()

    strategy._execute_job = record_directory
    return strategy


def test_concurrent_strategies_use_isolated_temporary_directories(monkeypatch) -> None:
    """Concurrent workflows must never share intermediate observation files."""
    observed_directories: list[Path] = []
    barrier = Barrier(2)
    strategies = [
        _strategy_stub(monkeypatch, observed_directories, barrier) for _ in range(2)
    ]

    with ThreadPoolExecutor(max_workers=2) as executor:
        list(executor.map(lambda strategy: strategy.execute(), strategies))

    assert len(observed_directories) == 2
    assert observed_directories[0] != observed_directories[1]
    assert all(not directory.exists() for directory in observed_directories)


def test_observation_selection_uses_the_execution_directory(
    monkeypatch, tmp_path: Path
) -> None:
    """Selection files are written to the caller's isolated directory."""
    concentrations = SimpleNamespace(
        frame=pd.DataFrame(
            {
                "date": [2021, 2022, 2023],
                "value": [1.0, 2.0, 3.0],
            }
        )
    )
    monkeypatch.setattr(
        workflow.Concentrations,
        "from_file",
        classmethod(lambda cls, path: concentrations),
    )
    monkeypatch.setattr(
        workflow,
        "workflow_temp_folder",
        lambda: (_ for _ in ()).throw(AssertionError("shared directory accessed")),
    )

    filename = workflow._write_observation_selection(
        "F09", "2021_2023", 2021, 2022, directory=str(tmp_path)
    )

    assert filename == "F09_2021_2023"
    assert (tmp_path / filename).is_file()


def test_prior_correspondence_uses_the_execution_directory(
    monkeypatch, tmp_path: Path
) -> None:
    """Prior input selections must remain inside the isolated execution."""
    observed_calls = []

    monkeypatch.setattr(
        workflow,
        "_periods_years",
        lambda *args: ([2021], [2022], [2021, 2022]),
    )

    def observation_files(well, dates, mode, breakups=(), directory=None):
        observed_calls.append((mode, directory))
        return ["F09_2021_2022"]

    monkeypatch.setattr(workflow, "_observation_files", observation_files)

    correspondence = workflow._build_prior_correspondence(
        "F09",
        "2021_2022",
        "successive_with_prior",
        directory=str(tmp_path),
    )

    assert correspondence == {"F09_2021_2022": "F09_2021_2022"}
    assert observed_calls == [
        ("successive", str(tmp_path)),
        ("span_full", str(tmp_path)),
    ]
