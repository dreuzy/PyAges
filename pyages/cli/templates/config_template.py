# Copyright (c) 2021-2026 Centre national de la recherche scientifique (CNRS)
# Contributor: Jean-Raynald de Dreuzy
# SPDX-License-Identifier: CECILL-2.1
# This file generates self-contained installed-package quickstart projects.

"""Create editable schema-3 quickstarts without requiring a source checkout."""

from __future__ import annotations

import os
import shutil
import tempfile
from pathlib import Path
from typing import Literal, TypeAlias

from pyages.cli._atomic import atomic_write_text

QuickstartKind: TypeAlias = Literal["single_date", "temporal"]

_SINGLE_DATE_CONFIG = """
schema_version: 3

workflow:
  kind: single_date

data:
  name: observations.tsv
  year: 2010
  data_dir: data
  verbose: false
  missing_error_rel: 0.01

lpm:
  models: [exp_shifted]

run:
  reachable_concentrations: false
  objective_function: false
  metropolis_hastings: false
  simplex: false

calibration:
  metropolis_hastings:
    nsteps: 200
    burn_in: 0.2
    thinning: 10
    seed: 12345
    prior_option: false
    likelihood: true
  simplex:
    init_multiples_n: 2
    fuq_n: 5

output:
  use_default: false
  directory: results
  study_name: quickstart
""".lstrip()

_TEMPORAL_CONFIG = """
schema_version: 3

workflow:
  kind: temporal
  mode: span

data:
  file: data/observations.tsv
  error_rel: 0.2
  missing_error_rel: 0.01

lpm:
  models: [exp_shifted]

calibration:
  exploration_resolution: 10
  posterior_draw_count: 10
  metropolis_hastings:
    nsteps: 200
    burn_in: 0.2
    thinning: 10
    seed: 12345
    prior_option: true

reporting:
  temporal: false
  distributions: false
  concentrations_2d: false

output:
  study_name: quickstart-temporal
  use_default: false
  directory: results
""".lstrip()

_SINGLE_DATE_DATA = """element\tconcentration\terror\tunit\tdate
cfc11\t235.0\t11.75\tpptv\t2010.0
cfc12\t475.0\t23.75\tpptv\t2010.0
cfc113\t69.0\t3.45\tpptv\t2010.0
"""

_TEMPORAL_DATA = """element\tconcentration\terror\tunit\tdate
cfc11\t260.0\t13.0\tpptv\t2005.0
cfc12\t520.0\t26.0\tpptv\t2005.0
cfc113\t82.0\t4.1\tpptv\t2005.0
cfc11\t235.0\t11.75\tpptv\t2010.0
cfc12\t475.0\t23.75\tpptv\t2010.0
cfc113\t69.0\t3.45\tpptv\t2010.0
"""


def generate_config_quickstart(
    destination: str | Path,
    kind: QuickstartKind,
) -> tuple[Path, Path]:
    """Publish one complete configuration-and-observation quickstart tree."""
    root = Path(destination).resolve()
    if kind == "single_date":
        config_text = _SINGLE_DATE_CONFIG
        data_text = _SINGLE_DATE_DATA
    elif kind == "temporal":
        config_text = _TEMPORAL_CONFIG
        data_text = _TEMPORAL_DATA
    else:  # pragma: no cover - Click and the public type reject this path.
        raise ValueError(f"Unsupported quickstart kind: {kind}")

    if root.exists():
        raise FileExistsError(f"Quickstart destination already exists: {root}")
    root.parent.mkdir(parents=True, exist_ok=True)
    staging = Path(
        tempfile.mkdtemp(
            dir=root.parent,
            prefix=f".{root.name}.",
            suffix=".tmp",
        )
    )
    try:
        staged_config = staging / "pyages.yaml"
        staged_data = staging / "data" / "observations.tsv"
        staged_data.parent.mkdir()
        atomic_write_text(staged_config, config_text)
        atomic_write_text(staged_data, data_text)

        # A second check protects against a destination created while the
        # private tree was being prepared. os.rename then publishes both files
        # together because source and destination share a parent filesystem.
        if root.exists():
            raise FileExistsError(f"Quickstart destination already exists: {root}")
        os.rename(staging, root)
    except BaseException:
        shutil.rmtree(staging, ignore_errors=True)
        raise
    return root / "pyages.yaml", root / "data" / "observations.tsv"


__all__ = ["QuickstartKind", "generate_config_quickstart"]
