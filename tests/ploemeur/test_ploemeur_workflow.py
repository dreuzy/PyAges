# Copyright (c) 2021-2026 Centre national de la recherche scientifique (CNRS)
# Contributor: Jean-Raynald de Dreuzy
# SPDX-License-Identifier: CECILL-2.1

from pathlib import Path
from types import SimpleNamespace

import matplotlib
import matplotlib.pyplot as plt
import pandas as pd

from sites.ploemeur.observations import ploemeur as ploemeur_observations
from sites.ploemeur.workflows import ploemeur_workflow


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
