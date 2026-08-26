"""Validate release identity and qualified dependency metadata."""

from __future__ import annotations

import argparse
import re
import tomllib
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[1]


def _normalized_name(value: str) -> str:
    return re.sub(r"[-_.]+", "-", value).lower()


def _dependency_name(value: str) -> str:
    match = re.match(r"\s*([A-Za-z0-9_.-]+)", value)
    if match is None:
        raise ValueError(f"Cannot parse dependency: {value!r}")
    return _normalized_name(match.group(1))


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
    runtime_names = {
        _dependency_name(item) for item in project["project"]["dependencies"]
    }
    pip_versions = _qualified_pip_versions()
    conda_versions = _qualified_conda_versions()
    errors = []
    for name in sorted(runtime_names):
        if name not in pip_versions:
            errors.append(f"runtime dependency missing from constraints: {name}")
        if name not in conda_versions:
            errors.append(f"runtime dependency missing from Conda environment: {name}")
        if name in pip_versions and name in conda_versions:
            if pip_versions[name] != conda_versions[name]:
                errors.append(
                    f"qualified version mismatch for {name}: "
                    f"pip={pip_versions[name]}, conda={conda_versions[name]}"
                )
    return errors


def release_identity_errors(tag: str | None = None) -> list[str]:
    namespace: dict[str, object] = {}
    exec((ROOT / "pyage/_version.py").read_text(encoding="utf-8"), namespace)
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
    if tag is not None and tag.removeprefix("v") != version:
        errors.append(f"tag/version mismatch: tag={tag}, package={version}")
    return errors


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--tag", help="Expected Git tag, normally v<version>.")
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
