# -*- coding: utf-8 -*-
"""
Repository root detection utilities.

Provides functions to locate the repository root directory, useful for scripts
that may be executed from any working directory.
"""

import sys
from pathlib import Path


def find_repo_root():
    """
    Return the repository root by walking up from cwd until 'pyage' exists.

    Returns
    -------
    Path
        The repository root directory.
    """
    root = Path.cwd()
    if not (root / "pyage").exists():
        for parent in root.parents:
            if (parent / "pyage").exists():
                root = parent
                break
    return root


def setup_repo_path():
    """
    Return the repository root and ensure it is on sys.path.

    This enables running scripts from any working directory while keeping
    imports stable (e.g., `concentrations`, `calibration`, `LPM`).

    Returns
    -------
    Path
        The repository root directory.
    """
    root = find_repo_root()
    sys.path.insert(0, str(root))
    sys.path.insert(0, str(root / "pyage"))
    return root
