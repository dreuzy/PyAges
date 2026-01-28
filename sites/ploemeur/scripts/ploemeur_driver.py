import sys
from pathlib import Path
import argparse

repo_root = Path(__file__).resolve().parents[3]
for p in (repo_root, repo_root / "pyage"):
    if str(p) not in sys.path:
        sys.path.insert(0, str(p))

# -*- coding: utf-8 -*-
"""
Driver script for running the Ploemeur workflow.
"""

from sites.ploemeur.workflows.ploemeur_workflow import run_workflow


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Run Ploemeur workflow.")
    parser.add_argument(
        "params",
        nargs="?",
        default=None,
        help="Path to the workflow YAML file (positional).",
    )
    parser.add_argument(
        "--params",
        dest="params_opt",
        default=None,
        help="Path to the workflow YAML file.",
    )
    args = parser.parse_args()
    params_path = args.params_opt or args.params
    if params_path is None:
        params_path = Path(__file__).resolve().parents[1] / "params" / "ploemeur_full.yaml"
    run_workflow(Path(params_path))
