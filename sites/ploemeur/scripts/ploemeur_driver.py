import sys
from pathlib import Path
import argparse
from typing import Optional

try:
    from pyage.config.bootstrap import ensure_repo_imports
except ModuleNotFoundError:
    repo_root = Path(__file__).resolve().parents[3]
    sys.path.insert(0, str(repo_root))
    from pyage.config.bootstrap import ensure_repo_imports

ensure_repo_imports()

# -*- coding: utf-8 -*-
"""
Driver script for running the Ploemeur workflow.
"""

from pydantic import ValidationError

from sites.ploemeur.config.models import PloemeurDriverConfig
from sites.ploemeur.workflows.ploemeur_workflow import run_workflow


def _load_driver_config(params_path: Optional[str]) -> PloemeurDriverConfig:
    data = {}
    if params_path:
        data["params"] = params_path
    try:
        return PloemeurDriverConfig.model_validate(data)
    except ValidationError as exc:
        raise SystemExit(f"Invalid Ploemeur driver config:\n{exc}") from exc


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
    config = _load_driver_config(params_path)
    run_workflow(Path(config.params))
