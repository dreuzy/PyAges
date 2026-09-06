# Copyright (c) 2021-2026 Centre national de la recherche scientifique (CNRS)
# Contributor: Jean-Raynald de Dreuzy
# SPDX-License-Identifier: CECILL-2.1

from pathlib import Path

from scripts.maintenance.check_architecture import ROOT, find_violations


def _write_module(root: Path, relative: str, source: str) -> None:
    path = root / relative
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(source, encoding="utf-8")


def test_current_repository_respects_documented_dependencies() -> None:
    assert find_violations(ROOT) == []


def test_absolute_and_relative_reverse_dependencies_are_reported(tmp_path) -> None:
    _write_module(tmp_path, "pyages/__init__.py", "")
    _write_module(tmp_path, "pyages/calibration/__init__.py", "")
    _write_module(
        tmp_path,
        "pyages/calibration/bad.py",
        "import pyages.workflows\nfrom .. import reporting\n",
    )

    assert find_violations(tmp_path) == [
        "pyages/calibration/bad.py:1: calibration must not import pyages.workflows",
        "pyages/calibration/bad.py:2: calibration must not import pyages.reporting",
    ]


def test_allowed_lower_layer_dependencies_are_ignored(tmp_path) -> None:
    _write_module(tmp_path, "pyages/__init__.py", "")
    _write_module(tmp_path, "pyages/calibration/__init__.py", "")
    _write_module(
        tmp_path,
        "pyages/calibration/good.py",
        "from pyages.data_io import lpm_params\nfrom . import objective\n",
    )

    assert find_violations(tmp_path) == []


def test_configuration_must_not_enter_the_calibration_graph(tmp_path) -> None:
    _write_module(tmp_path, "pyages/__init__.py", "")
    _write_module(tmp_path, "pyages/config/__init__.py", "")
    _write_module(
        tmp_path,
        "pyages/config/bad.py",
        "from pyages.calibration import CalibrationProblem\n",
    )

    assert find_violations(tmp_path) == [
        "pyages/config/bad.py:1: config must not import pyages.calibration"
    ]
