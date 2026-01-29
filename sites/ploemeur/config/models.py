# -*- coding: utf-8 -*-
"""
Pydantic models specific to the Ploemeur site scripts.

These schemas live under sites/ to avoid coupling with core pyage config
when only local workflows are concerned.
"""

from __future__ import annotations

from pathlib import Path

from pydantic import BaseModel, ConfigDict, Field, ValidationError, field_validator


PLOEMEUR_ROOT = Path(__file__).resolve().parents[1]


class _BaseCfg(BaseModel):
    """Base config: ignore unknown keys to keep legacy YAML compatible."""
    model_config = ConfigDict(extra="ignore")


class PloemeurDriverConfig(_BaseCfg):
    """Configuration for the Ploemeur driver entrypoint."""
    params: Path = Field(default_factory=lambda: PLOEMEUR_ROOT / "params" / "ploemeur_full.yaml")

    @field_validator("params")
    @classmethod
    def _resolve_params(cls, value: Path) -> Path:
        if not value.is_absolute():
            value = PLOEMEUR_ROOT / value
        if not value.exists():
            raise ValueError(f"Ploemeur params file not found: {value}")
        return value


__all__ = [
    "ValidationError",
    "PloemeurDriverConfig",
]
