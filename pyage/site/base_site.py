# -*- coding: utf-8 -*-
"""
Base interface for site-specific workflows.

Sites under `sites/<name>/` can implement this interface to provide a
consistent API for loading, validating, and running workflows.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from pathlib import Path
from typing import Any, Dict


class BaseSite(ABC):
    """Abstract interface for site workflows."""

    @property
    @abstractmethod
    def name(self) -> str:
        """Site identifier (e.g., 'ploemeur')."""

    @property
    @abstractmethod
    def default_params_path(self) -> Path:
        """Default YAML parameters path for the site."""

    @abstractmethod
    def load_params(self, params_path: Path | None) -> Dict[str, Any]:
        """Load site parameters from YAML (or defaults)."""

    @abstractmethod
    def validate_params(self, params: Dict[str, Any]) -> None:
        """Validate site parameters."""

    @abstractmethod
    def run(self, params_path: Path | None) -> None:
        """Execute the workflow."""
