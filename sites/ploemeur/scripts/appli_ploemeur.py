import sys
from pathlib import Path

repo_root = Path(__file__).resolve().parents[3]
for p in (repo_root, repo_root / "sources"):
    if str(p) not in sys.path:
        sys.path.insert(0, str(p))

# -*- coding: utf-8 -*-
"""
Backward-compatible entry point for Ploemeur runs.

Use sites/ploemeur/workflows/ploemeur_workflow.py for the actual workflow
implementation. This module keeps old imports working.
"""

from sites.ploemeur.workflows.ploemeur_workflow import *  # noqa: F401,F403
from sites.ploemeur.workflows.ploemeur_workflow import run_workflow


if __name__ == "__main__":
    run_workflow()
