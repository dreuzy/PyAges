# -*- coding: utf-8 -*-
"""
Ploemeur site API implementation.

This class adapts the existing workflow functions to the BaseSite interface.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any, Dict

from pyage.site.base_site import BaseSite
from sites.ploemeur.workflows.ploemeur_workflow import (
    load_workflow_params,
    validate_workflow_params,
    run_workflow,
)


class PloemeurSite(BaseSite):
    """Site wrapper for the Ploemeur workflows."""

    @property
    def name(self) -> str:
        return "ploemeur"

    @property
    def default_params_path(self) -> Path:
        return Path(__file__).resolve().parent / "params" / "ploemeur_full.yaml"

    def load_params(self, params_path: Path | None) -> Dict[str, Any]:
        if params_path is None:
            params_path = self.default_params_path
        return load_workflow_params(Path(params_path))

    def validate_params(self, params: Dict[str, Any]) -> None:
        validate_workflow_params(params)

    def run(self, params_path: Path | None) -> None:
        if params_path is None:
            params_path = self.default_params_path
        run_workflow(Path(params_path))
