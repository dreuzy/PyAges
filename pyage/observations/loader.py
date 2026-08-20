# -*- coding: utf-8 -*-
"""
Generic loaders for observation datasets.

Purpose
-------
Provide small, dataset-agnostic helpers to load concentration tables used
across examples and site workflows.
"""

from __future__ import annotations

from pathlib import Path

from pyage.concentrations.concentrations import Concentrations


def build_observation_path(
    base_dir: str | Path,
    prefix: str,
    well: str,
    dates: str,
    suffix: str = ".txt",
) -> Path:
    """
    Build a dataset file path from naming components.

    Parameters
    ----------
    base_dir : str or Path
        Root folder containing observation files.
    prefix : str
        Filename prefix (e.g., ``ori_ploemeur_``).
    well : str
        Well name (or station identifier).
    dates : str
        Date range identifier (e.g., "2005_2024").
    suffix : str, optional
        Filename suffix, default ".txt".

    Returns
    -------
    Path
        Full path to the observation file.
    """
    return Path(base_dir) / f"{prefix}{well}_{dates}{suffix}"


def build_observation_file(
    base_dir: str | Path,
    prefix: str,
    well: str,
    dates: str,
    suffix: str = ".txt",
) -> str:
    """
    Build an observation filename as a string path.

    Parameters
    ----------
    base_dir : str or Path
        Root folder containing observation files.
    prefix : str
        Filename prefix (e.g., ``ori_ploemeur_``).
    well : str
        Well name (or station identifier).
    dates : str
        Date range identifier (e.g., "2005_2024").
    suffix : str, optional
        Filename suffix, default ".txt".
    """
    return str(build_observation_path(base_dir, prefix, well, dates, suffix=suffix))


def load_observation_concentrations(
    base_dir: str | Path,
    prefix: str,
    well: str,
    dates: str,
    suffix: str = ".txt",
) -> Concentrations:
    """
    Load a concentrations table from a standardized observation filename.

    Parameters
    ----------
    base_dir : str or Path
        Root folder containing observation files.
    prefix : str
        Filename prefix (e.g., ``ori_ploemeur_``).
    well : str
        Well name (or station identifier).
    dates : str
        Date range identifier (e.g., "2005_2024").
    suffix : str, optional
        Filename suffix, default ".txt".
    """
    path = build_observation_path(base_dir, prefix, well, dates, suffix=suffix)
    return load_concentrations(path)


def load_concentrations(file_path: str | Path) -> Concentrations:
    """
    Load a concentrations table from disk.

    Parameters
    ----------
    file_path : str or Path
        Path to the concentration file to load.

    Returns
    -------
    Concentrations
        Loaded concentrations container.
    """
    path = Path(file_path)
    if not path.exists():
        raise FileNotFoundError(f"Concentration file not found: {path}")
    return Concentrations.from_file(path)
