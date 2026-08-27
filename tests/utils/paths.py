# Copyright (c) 2021-2026 Centre national de la recherche scientifique (CNRS)
# Contributor: Jean-Raynald de Dreuzy
# SPDX-License-Identifier: CECILL-2.1

"""Path helpers for tests."""

from pathlib import Path


def repo_root() -> Path:
    return Path(__file__).resolve().parents[2]


def lpm_dir() -> Path:
    return repo_root() / "pyages" / "lpm" / "models"


def lpm_data_dir() -> Path:
    return repo_root() / "data_core" / "data_lpm"


def tracer_data_dir() -> Path:
    return repo_root() / "data_core" / "data_tracer"
