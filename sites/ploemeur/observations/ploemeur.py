# -*- coding: utf-8 -*-
"""
Ploemeur dataset helpers.

Purpose
-------
Centralize filesystem conventions for Ploemeur observations (raw/ori data,
results folders) so examples and site workflows share the same access logic.
"""

from __future__ import annotations

from pathlib import Path

from pyage.config.paths import (
    ROOT_DIRECTORY,
    ROOT_DIRECTORY_RESULTS,
    result_subdirectory,
    timestamp_name,
)


def ploemeur_data_folder(root: str | Path | None = None) -> str:
    """
    Return the root data folder for Ploemeur observations.

    Parameters
    ----------
    root : str or Path, optional
        Repository root. Defaults to the canonical PyAge repository root.
    """
    base = Path(root) if root is not None else ROOT_DIRECTORY
    return str(base / "sites" / "ploemeur" / "data")


def ploemeur_brut_folder(root: str | Path | None = None) -> str:
    """
    Return the folder containing raw Ploemeur data files.
    """
    return str(Path(ploemeur_data_folder(root)) / "brut")


def ploemeur_ori_folder(root: str | Path | None = None) -> str:
    """
    Return the folder containing normalized Ploemeur data files.
    """
    return str(Path(ploemeur_data_folder(root)) / "ori")


def ploemeur_results_folder(file_root: str) -> tuple[Path, Path, str]:
    """
    Build a timestamped results folder structure for a Ploemeur run.

    Parameters
    ----------
    file_root : str
        Base name for the results folder.
    """
    dir_root = result_subdirectory(ROOT_DIRECTORY_RESULTS, file_root)
    date_file = timestamp_name()
    directory_results = result_subdirectory(dir_root, date_file)
    return directory_results, dir_root, date_file
