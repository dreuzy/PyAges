# -*- coding: utf-8 -*-
"""
Bootstrap helpers for dual-mode execution (installed or repo-direct).
"""

from __future__ import annotations

import sys
from pathlib import Path


def ensure_repo_imports() -> Path | None:
    """Ensure `pyage` is importable when running from the repo.

    Returns the repo root if it had to be added, otherwise None.
    """
    try:
        import pyage  # noqa: F401
        return None
    except ModuleNotFoundError:
        repo_root = Path(__file__).resolve().parents[2]
        sys.path.insert(0, str(repo_root))
        return repo_root
