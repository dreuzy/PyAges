# Copyright (c) 2021-2026 Centre national de la recherche scientifique (CNRS)
# Contributor: Jean-Raynald de Dreuzy
# SPDX-License-Identifier: CECILL-2.1

"""Validate release identity and qualified dependency metadata."""

from __future__ import annotations

import argparse
import re
import tomllib
from pathlib import Path

import yaml
from packaging.markers import default_environment
from packaging.requirements import Requirement
from packaging.version import Version

ROOT = Path(__file__).resolve().parents[1]


def _normalized_name(value: str) -> str:
    return re.sub(r"[-_.]+", "-", value).lower()


def _qualified_pip_versions() -> dict[str, str]:
    versions: dict[str, str] = {}
    for raw in (
        (ROOT / "install/constraints.txt").read_text(encoding="utf-8").splitlines()
    ):
        line = raw.strip()
        if not line or line.startswith("#") or "==" not in line:
            continue
        name, version = line.split("==", 1)
        versions[_normalized_name(name)] = version
    return versions


def _qualified_conda_versions() -> dict[str, str]:
    payload = yaml.safe_load(
        (ROOT / "install/environment.yml").read_text(encoding="utf-8")
    )
    versions: dict[str, str] = {}
    for item in payload["dependencies"]:
        if not isinstance(item, str) or "=" not in item:
            continue
        name, version = item.split("=", 1)
        versions[_normalized_name(name)] = version
    return versions


def dependency_alignment_errors() -> list[str]:
    project = tomllib.loads((ROOT / "pyproject.toml").read_text(encoding="utf-8"))
    runtime_requirements = [
        Requirement(item) for item in project["project"]["dependencies"]
    ]
    pip_versions = _qualified_pip_versions()
    conda_versions = _qualified_conda_versions()
    errors = []

    targets = [
        ("pip/Python 3.12", pip_versions, "3.12"),
        ("pip/Python 3.13", pip_versions, "3.13"),
        ("pip/Python 3.14", pip_versions, "3.14"),
        ("conda/Python 3.12", conda_versions, "3.12"),
    ]
    for source, versions, python_version in targets:
        environment = default_environment()
        environment.update(
            {
                "python_version": python_version,
                "python_full_version": f"{python_version}.0",
                "extra": "",
            }
        )
        active_requirements = [
            requirement
            for requirement in runtime_requirements
            if requirement.marker is None or requirement.marker.evaluate(environment)
        ]
        for requirement in active_requirements:
            name = _normalized_name(requirement.name)
            if name not in versions:
                errors.append(f"runtime dependency missing from {source}: {name}")
                continue
            if Version(versions[name]) not in requirement.specifier:
                errors.append(
                    f"qualified {source} version for {name} is outside "
                    f"{requirement.specifier}: {versions[name]}"
                )
    return errors


def release_identity_errors(tag: str | None = None) -> list[str]:
    namespace: dict[str, object] = {}
    exec((ROOT / "pyages/_version.py").read_text(encoding="utf-8"), namespace)
    version = str(namespace["__version__"])
    citation = yaml.safe_load((ROOT / "CITATION.cff").read_text(encoding="utf-8"))
    changelog = (ROOT / "CHANGELOG.md").read_text(encoding="utf-8")
    errors = []
    if str(citation.get("version")) != version:
        errors.append(
            f"version mismatch: package={version}, CITATION.cff={citation.get('version')}"
        )
    if not re.search(rf"^## {re.escape(version)}(?:\s+-|$)", changelog, re.MULTILINE):
        errors.append(f"CHANGELOG.md has no release heading for {version}")
    if tag is not None and tag != version:
        errors.append(f"tag/version mismatch: tag={tag}, package={version}")
    return errors


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--tag", help="Expected Git tag; release 1.0 uses tag 1.0.")
    args = parser.parse_args(argv)
    errors = dependency_alignment_errors() + release_identity_errors(args.tag)
    if errors:
        for error in errors:
            print(f"ERROR: {error}")
        return 1
    print("Project metadata is internally consistent.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
