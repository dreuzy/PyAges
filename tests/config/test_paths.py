# Copyright (c) 2021-2026 Centre national de la recherche scientifique (CNRS)
# Contributor: Jean-Raynald de Dreuzy
# SPDX-License-Identifier: CECILL-2.1

"""Installation-safe path and resource contracts."""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

from pyages.config.paths import DIRECTORY_LPM_DATA, DIRECTORY_TRACER_DATA

REPO_ROOT = Path(__file__).resolve().parents[2]


def test_core_data_directories_are_available() -> None:
    assert (DIRECTORY_LPM_DATA / "exp" / "params.yaml").is_file()
    assert (DIRECTORY_TRACER_DATA / "cfc11" / "cfc11.yaml").is_file()


def test_import_does_not_create_results_directory(tmp_path: Path) -> None:
    results_directory = tmp_path / "not-created-by-import"
    environment = os.environ.copy()
    environment["PYAGES_RESULTS_DIR"] = str(results_directory)
    environment["PYTHONPATH"] = os.pathsep.join(
        filter(
            None,
            [str(REPO_ROOT), environment.get("PYTHONPATH", "")],
        )
    )

    subprocess.run(
        [sys.executable, "-c", "import pyages.config.paths"],
        cwd=tmp_path,
        env=environment,
        check=True,
    )

    assert not results_directory.exists()
