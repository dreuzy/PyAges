import sys
from pathlib import Path
import argparse

repo_root = Path(__file__).resolve().parents[3]
for p in (repo_root, repo_root / "sources"):
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
        default=str(Path(__file__).resolve().parents[1] / "params" / "ploemeur_params.yaml"),
        help="Path to the workflow YAML file.",
    )
    args = parser.parse_args()
    run_workflow(Path(args.params))
