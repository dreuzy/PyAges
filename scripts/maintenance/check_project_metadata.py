# Copyright (c) 2021-2026 Centre national de la recherche scientifique (CNRS)
# Contributor: Jean-Raynald de Dreuzy
# SPDX-License-Identifier: CECILL-2.1

"""Validate release identity and qualified dependency metadata."""

from __future__ import annotations

import argparse
import importlib.metadata
import re
import sys
import tomllib
from collections.abc import Iterable, Sequence
from pathlib import Path

import yaml
from packaging.markers import default_environment
from packaging.requirements import Requirement
from packaging.version import Version

ROOT = Path(__file__).resolve().parents[2]
SUPPORTED_PYTHON_VERSIONS = ("3.12", "3.13", "3.14")
OPTIONAL_GROUPS = ("dev", "docs", "examples")


def _normalized_name(value: str) -> str:
    return re.sub(r"[-_.]+", "-", value).lower()


def _pinned_versions(path: Path) -> dict[str, str]:
    versions: dict[str, str] = {}
    for raw in path.read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if not line or line.startswith("#") or "==" not in line:
            continue
        name, version = line.split("==", 1)
        versions[_normalized_name(name)] = version
    return versions


def _qualified_pip_versions() -> dict[str, str]:
    return _pinned_versions(ROOT / "install/constraints.txt")


def _qualified_bootstrap_versions() -> dict[str, str]:
    return _pinned_versions(ROOT / "install/bootstrap-constraints.txt")


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


def _project_requirement_groups(
    project: dict[str, object],
) -> dict[str, list[Requirement]]:
    project_metadata = project["project"]
    if not isinstance(project_metadata, dict):
        raise TypeError("pyproject.toml [project] must be a table")
    optional = project_metadata["optional-dependencies"]
    if not isinstance(optional, dict):
        raise TypeError("pyproject.toml optional dependencies must be a table")
    groups = {
        "runtime": [Requirement(item) for item in project_metadata["dependencies"]],
    }
    for group in OPTIONAL_GROUPS:
        groups[group] = [Requirement(item) for item in optional[group]]
    return groups


def _environment_for(python_version: str, group: str = "") -> dict[str, str]:
    # ``default_environment`` returns a precise TypedDict.  Copy it into the
    # more general mapping accepted by ``Marker.evaluate`` before adding the
    # metadata-only ``extra`` key.
    environment = {str(key): str(value) for key, value in default_environment().items()}
    environment.update(
        {
            "python_version": python_version,
            "python_full_version": f"{python_version}.0",
            "extra": group,
        }
    )
    return environment


def _active_requirements(
    requirements: Iterable[Requirement],
    *,
    python_version: str,
    group: str = "",
) -> list[Requirement]:
    environment = _environment_for(python_version, group)
    return [
        requirement
        for requirement in requirements
        if requirement.marker is None or requirement.marker.evaluate(environment)
    ]


def _direct_constraint_coverage_errors(
    groups: dict[str, list[Requirement]], pip_versions: dict[str, str]
) -> list[str]:
    errors: list[str] = []
    direct_names = {
        _normalized_name(requirement.name)
        for requirements in groups.values()
        for requirement in requirements
    }
    for name in sorted(direct_names - pip_versions.keys()):
        errors.append(f"direct dependency missing from pip constraints: {name}")
    for name in sorted(pip_versions.keys() - direct_names):
        errors.append(f"unexpected pip constraint without a direct dependency: {name}")
    return errors


def _qualified_requirement_errors(
    groups: dict[str, list[Requirement]], pip_versions: dict[str, str]
) -> list[str]:
    errors: list[str] = []

    for group, requirements in groups.items():
        for python_version in SUPPORTED_PYTHON_VERSIONS:
            source = f"pip/{group}/Python {python_version}"
            for requirement in _active_requirements(
                requirements,
                python_version=python_version,
                group=group if group != "runtime" else "",
            ):
                name = _normalized_name(requirement.name)
                if name not in pip_versions:
                    continue
                if Version(pip_versions[name]) not in requirement.specifier:
                    errors.append(
                        f"qualified {source} version for {name} is outside "
                        f"{requirement.specifier}: {pip_versions[name]}"
                    )
    return errors


def _conda_alignment_errors(
    runtime_requirements: list[Requirement], conda_versions: dict[str, str]
) -> list[str]:
    errors: list[str] = []

    for requirement in _active_requirements(
        runtime_requirements, python_version="3.12"
    ):
        name = _normalized_name(requirement.name)
        source = "conda/runtime/Python 3.12"
        if name not in conda_versions:
            errors.append(f"runtime dependency missing from {source}: {name}")
            continue
        if Version(conda_versions[name]) not in requirement.specifier:
            errors.append(
                f"qualified {source} version for {name} is outside "
                f"{requirement.specifier}: {conda_versions[name]}"
            )
    return errors


def _bootstrap_alignment_errors(project: dict[str, object]) -> list[str]:
    errors: list[str] = []

    bootstrap_versions = _qualified_bootstrap_versions()
    expected_bootstrap = {"pip", "setuptools", "wheel"}
    for name in sorted(expected_bootstrap - bootstrap_versions.keys()):
        errors.append(f"bootstrap dependency is not pinned: {name}")
    for name in sorted(bootstrap_versions.keys() - expected_bootstrap):
        errors.append(f"unexpected bootstrap dependency: {name}")

    build_system = project["build-system"]
    if not isinstance(build_system, dict):
        raise TypeError("pyproject.toml [build-system] must be a table")
    build_requirements = [Requirement(item) for item in build_system["requires"]]
    for requirement in build_requirements:
        name = _normalized_name(requirement.name)
        if name not in bootstrap_versions:
            errors.append(
                f"build dependency missing from bootstrap constraints: {name}"
            )
            continue
        if Version(bootstrap_versions[name]) not in requirement.specifier:
            errors.append(
                f"bootstrap version for {name} is outside "
                f"{requirement.specifier}: {bootstrap_versions[name]}"
            )
    return errors


def _documentation_install_errors() -> list[str]:
    errors: list[str] = []

    requirements_lines = {
        line.strip()
        for line in (ROOT / "docs/requirements.txt")
        .read_text(encoding="utf-8")
        .splitlines()
        if line.strip() and not line.lstrip().startswith("#")
    }
    expected_docs_lines = {
        "-r ../install/bootstrap-constraints.txt",
        "-c ../install/constraints.txt",
        "-e .[docs]",
    }
    if requirements_lines != expected_docs_lines:
        errors.append(
            "docs/requirements.txt must install the bootstrap pins, use the "
            "qualified constraints, and install .[docs]"
        )

    readthedocs = yaml.safe_load(
        (ROOT / ".readthedocs.yaml").read_text(encoding="utf-8")
    )
    install_steps = readthedocs.get("python", {}).get("install", [])
    if {"requirements": "docs/requirements.txt"} not in install_steps:
        errors.append("Read the Docs must install docs/requirements.txt")
    return errors


def dependency_alignment_errors() -> list[str]:
    project = tomllib.loads((ROOT / "pyproject.toml").read_text(encoding="utf-8"))
    groups = _project_requirement_groups(project)
    pip_versions = _qualified_pip_versions()
    errors = _direct_constraint_coverage_errors(groups, pip_versions)
    errors.extend(_qualified_requirement_errors(groups, pip_versions))
    errors.extend(
        _conda_alignment_errors(groups["runtime"], _qualified_conda_versions())
    )
    errors.extend(_bootstrap_alignment_errors(project))
    errors.extend(_documentation_install_errors())
    return errors


def _installed_group_errors(
    groups: dict[str, list[Requirement]],
    selected: Sequence[str],
    *,
    python_version: str,
    qualified: dict[str, str],
    require_qualified_versions: bool,
) -> list[str]:
    errors: list[str] = []
    checked_names: set[str] = set()
    for group in selected:
        active = _active_requirements(
            groups[group],
            python_version=python_version,
            group=group if group != "runtime" else "",
        )
        for requirement in active:
            name = _normalized_name(requirement.name)
            if name in checked_names:
                continue
            checked_names.add(name)
            try:
                installed = importlib.metadata.version(requirement.name)
            except importlib.metadata.PackageNotFoundError:
                errors.append(f"installed {group} dependency is missing: {name}")
                continue
            if Version(installed) not in requirement.specifier:
                errors.append(
                    f"installed {group} dependency {name} is outside "
                    f"{requirement.specifier}: {installed}"
                )
            if require_qualified_versions and installed != qualified[name]:
                errors.append(
                    f"installed {group} dependency does not match the qualified "
                    f"pin: {name}=={installed}, expected {qualified[name]}"
                )
    return errors


def _installed_bootstrap_errors() -> list[str]:
    errors: list[str] = []
    for name, expected in _qualified_bootstrap_versions().items():
        try:
            installed = importlib.metadata.version(name)
        except importlib.metadata.PackageNotFoundError:
            errors.append(f"installed bootstrap dependency is missing: {name}")
            continue
        if installed != expected:
            errors.append(
                f"installed bootstrap dependency does not match the qualified "
                f"pin: {name}=={installed}, expected {expected}"
            )
    return errors


def installed_dependency_errors(
    extras: Sequence[str] = (),
    *,
    require_qualified_versions: bool = False,
) -> list[str]:
    """Return errors for direct dependencies in the running interpreter."""
    unknown = set(extras) - set(OPTIONAL_GROUPS)
    if unknown:
        raise ValueError(f"unknown optional dependency groups: {sorted(unknown)}")

    project = tomllib.loads((ROOT / "pyproject.toml").read_text(encoding="utf-8"))
    groups = _project_requirement_groups(project)
    python_version = f"{sys.version_info.major}.{sys.version_info.minor}"
    selected = ("runtime", *extras)
    qualified = _qualified_pip_versions()
    errors = _installed_group_errors(
        groups,
        selected,
        python_version=python_version,
        qualified=qualified,
        require_qualified_versions=require_qualified_versions,
    )
    if require_qualified_versions:
        errors.extend(_installed_bootstrap_errors())
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


def canonical_naming_errors() -> list[str]:
    """Return public naming inconsistencies for the PyAges project."""
    metadata = tomllib.loads((ROOT / "pyproject.toml").read_text(encoding="utf-8"))
    project = metadata["project"]
    citation = yaml.safe_load((ROOT / "CITATION.cff").read_text(encoding="utf-8"))
    errors = []

    if project.get("name") != "pyages":
        errors.append(f"distribution name must be pyages: {project.get('name')}")
    if set(project.get("scripts", {})) != {"pyages"}:
        errors.append("the only installed command must be pyages")
    if not (ROOT / "pyages/__init__.py").is_file() or (ROOT / "pyage").exists():
        errors.append("the import package must be pyages with no pyage package alias")

    expected_urls = {
        "Homepage": "https://github.com/dreuzy/PyAges",
        "Repository": "https://github.com/dreuzy/PyAges.git",
        "Issues": "https://github.com/dreuzy/PyAges/issues",
        "Changelog": "https://github.com/dreuzy/PyAges/blob/main/CHANGELOG.md",
    }
    for label, expected in expected_urls.items():
        actual = project.get("urls", {}).get(label)
        if actual != expected:
            errors.append(f"{label} URL must be {expected}: {actual}")

    if not str(citation.get("title", "")).startswith("PyAges:"):
        errors.append("CITATION.cff title must use the PyAges display name")
    if citation.get("repository-code") != expected_urls["Repository"]:
        errors.append("CITATION.cff repository-code must use the canonical GitHub URL")

    for path in (ROOT / "data_core/data_tracer").glob("*/recharge.csv"):
        if "pyage-support@" in path.read_text(encoding="utf-8").lower():
            errors.append(
                f"legacy PyAge support address remains in {path.relative_to(ROOT)}"
            )
    return errors


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--tag", help="Expected Git tag; it must equal the version.")
    parser.add_argument(
        "--check-installed",
        action="store_true",
        help="also validate direct dependencies in the running interpreter",
    )
    parser.add_argument(
        "--extra",
        action="append",
        choices=OPTIONAL_GROUPS,
        default=[],
        help="optional dependency group required by --check-installed; repeatable",
    )
    parser.add_argument(
        "--require-qualified-versions",
        action="store_true",
        help="require installed direct and bootstrap versions to equal their pins",
    )
    args = parser.parse_args(argv)
    if args.extra and not args.check_installed:
        parser.error("--extra requires --check-installed")
    if args.require_qualified_versions and not args.check_installed:
        parser.error("--require-qualified-versions requires --check-installed")

    errors = (
        canonical_naming_errors()
        + dependency_alignment_errors()
        + release_identity_errors(args.tag)
    )
    if args.check_installed:
        print(f"Interpreter: {sys.executable}")
        selected = ", ".join(("runtime", *args.extra))
        print(f"Installed dependency groups: {selected}")
        errors += installed_dependency_errors(
            args.extra,
            require_qualified_versions=args.require_qualified_versions,
        )
    if errors:
        for error in errors:
            print(f"ERROR: {error}")
        return 1
    print("Project metadata is internally consistent.")
    if args.check_installed:
        level = "qualified" if args.require_qualified_versions else "compatible"
        print(f"Installed direct dependencies are {level}.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
