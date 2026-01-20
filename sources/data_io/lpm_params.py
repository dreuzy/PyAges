"""Load and validate LPM parameter files (params.yaml)."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml


class LPMParamsError(Exception):
    """Raised when LPM parameters are missing or malformed."""


def load_params(model_name: str, data_dir: Path) -> dict[str, Any]:
    """Load params.yaml for a given model."""
    path = data_dir / model_name / "params.yaml"
    if not path.exists():
        raise LPMParamsError(f"Missing params.yaml: {path}")
    return yaml.safe_load(path.read_text(encoding="utf-8")) or {}


def get_bounds(params: dict[str, Any]) -> dict[str, tuple[float, float]]:
    """Return {param_name: (min, max)} bounds."""
    out: dict[str, tuple[float, float]] = {}
    for param in params.get("parameters", []):
        name = param.get("name")
        bounds = param.get("bounds")
        if not name or not bounds or len(bounds) != 2:
            raise LPMParamsError(f"Missing bounds for {name}")
        out[name] = (float(bounds[0]), float(bounds[1]))
    return out


def get_init(params: dict[str, Any]) -> dict[str, float]:
    """Return {param_name: init}."""
    out: dict[str, float] = {}
    for param in params.get("parameters", []):
        name = param.get("name")
        if name and "init" in param:
            out[name] = float(param["init"])
    return out


def get_steps(params: dict[str, Any]) -> dict[str, float]:
    """Return {param_name: step}."""
    out: dict[str, float] = {}
    for param in params.get("parameters", []):
        name = param.get("name")
        if name and "step" in param:
            out[name] = float(param["step"])
    return out


def get_priors(params: dict[str, Any]) -> dict[str, Any]:
    """Return {param_name: prior_dict}."""
    out: dict[str, Any] = {}
    for param in params.get("parameters", []):
        name = param.get("name")
        prior = param.get("prior")
        if name and prior:
            out[name] = prior
    return out
