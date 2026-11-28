# Copyright (c) 2021-2026 Centre national de la recherche scientifique (CNRS)
# Contributor: Jean-Raynald de Dreuzy
# SPDX-License-Identifier: CECILL-2.1

"""Install and exercise the standalone external-LPM example as a real package."""

from __future__ import annotations

import os
import shutil
import subprocess
import sys
from pathlib import Path

import pytest
from click.testing import CliRunner

from pyages.cli.commands.new import new_group

ROOT = Path(__file__).resolve().parents[2]
EXAMPLE_PROJECTS = (
    (
        ROOT / "examples" / "templates" / "external_lpm_plugin",
        "bounded_power",
        "pyages-lpm-bounded-power",
    ),
    (
        ROOT / "examples" / "templates" / "external_lpm_plugin_scipy",
        "gamma_mean",
        "pyages-lpm-gamma-mean",
    ),
)


def _run(command: list[str], *, cwd: Path, env: dict[str, str] | None = None) -> str:
    """Run a subprocess and return its combined output.

    Keeping stdout and stderr together preserves the build, import, or CLI
    diagnostic that caused a boundary test to fail.
    """
    completed = subprocess.run(
        command,
        cwd=cwd,
        env=env,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        check=False,
    )
    assert completed.returncode == 0, completed.stdout
    return completed.stdout


def _install_and_verify_plugin(
    project: Path,
    *,
    temporary_root: Path,
    model_name: str,
    provider_distribution: str,
    expected_test_count: int,
) -> None:
    """Build, install, discover, construct, check, and test one plugin project.

    The project is installed into an isolated target directory without network
    or dependency resolution. Subprocesses then see the installed plugin first
    and the current PyAges checkout second. This proves that entry-point
    metadata and packaged YAML data work outside the source project itself.
    """
    installed = temporary_root / "site-packages"
    _run(
        [
            sys.executable,
            "-m",
            "pip",
            "install",
            "--disable-pip-version-check",
            "--no-index",
            "--no-deps",
            "--no-build-isolation",
            "--target",
            str(installed),
            str(project),
        ],
        cwd=temporary_root,
    )

    env = os.environ.copy()
    env["PYTHONPATH"] = os.pathsep.join(
        path for path in (str(installed), str(ROOT), env.get("PYTHONPATH", "")) if path
    )
    env["PYTHONDONTWRITEBYTECODE"] = "1"

    listing = _run(
        [sys.executable, "-m", "pyages.cli.main", "list", "lpms"],
        cwd=temporary_root,
        env=env,
    )
    assert model_name in listing

    check = _run(
        [
            sys.executable,
            "-m",
            "pyages.cli.main",
            "check",
            "lpm",
            model_name,
        ],
        cwd=temporary_root,
        env=env,
    )
    assert "satisfies the PyAges integration contract" in check

    probe = _run(
        [
            sys.executable,
            "-c",
            (
                "from pyages.lpm import build_lpm; "
                f"model = build_lpm('{model_name}'); "
                "assert model.provenance is not None; "
                "assert model.provenance.provider_distribution "
                f"== '{provider_distribution}'; "
                "print(model.mean())"
            ),
        ],
        cwd=temporary_root,
        env=env,
    )
    assert float(probe.strip()) > 0.0

    own_tests = _run(
        [sys.executable, "-m", "pytest", "-q"],
        cwd=project,
        env=env,
    )
    assert f"{expected_test_count} passed" in own_tests


@pytest.mark.parametrize(
    ("example_project", "model_name", "provider_distribution"),
    EXAMPLE_PROJECTS,
    ids=("numpy-only", "scipy-backed"),
)
def test_external_example_installs_and_passes_cli_check(
    tmp_path: Path,
    example_project: Path,
    model_name: str,
    provider_distribution: str,
) -> None:
    """Prove that packaged metadata, data files, discovery, and checking cooperate."""
    project = tmp_path / "plugin"
    shutil.copytree(
        example_project, project, ignore=shutil.ignore_patterns(".*", "__pycache__")
    )
    _install_and_verify_plugin(
        project,
        temporary_root=tmp_path,
        model_name=model_name,
        provider_distribution=provider_distribution,
        expected_test_count=2,
    )


@pytest.mark.parametrize(
    ("base", "model_name"),
    (("scipy", "generated_gamma_audit"), ("root", "generated_power_audit")),
)
def test_generated_plugin_is_immediately_installable(
    tmp_path: Path,
    base: str,
    model_name: str,
) -> None:
    """Exercise the exact CLI generation path for both supported model bases."""
    project = tmp_path / f"plugin-{base}"
    result = CliRunner().invoke(
        new_group,
        [
            "lpm",
            model_name,
            "--layout",
            "plugin",
            "--base",
            base,
            "--output",
            str(project),
        ],
    )
    assert result.exit_code == 0, result.output

    _install_and_verify_plugin(
        project,
        temporary_root=tmp_path,
        model_name=model_name,
        provider_distribution=f"pyages-lpm-{model_name.replace('_', '-')}",
        expected_test_count=1,
    )
