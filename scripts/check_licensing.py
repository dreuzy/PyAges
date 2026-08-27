# Copyright (c) 2021-2026 Centre national de la recherche scientifique (CNRS)
# Contributor: Jean-Raynald de Dreuzy
# SPDX-License-Identifier: CECILL-2.1

"""Validate the repository's CeCILL declarations and source notices."""

from __future__ import annotations

import hashlib
import json
import subprocess
import sys
import tomllib
import xml.etree.ElementTree as ET
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SPDX_NOTICE = "SPDX-License-Identifier: CECILL-2.1"
COPYRIGHT_NOTICE = "Copyright (c)"
SOURCE_SUFFIXES = {".cs", ".ipynb", ".ps1", ".py"}
LICENSE_SHA256 = {
    "LICENSE": "b450b3b1ad1552ee0c1f6f9564b26aad105509e268e774ba9a0711a6f72f9236",
    "LICENSE.en": "b3ba449a732eb7d2d1d52ffe7a644da65a7164eb59876bb219a0a53f7188aacd",
}


def _normalized_digest(path: Path) -> str:
    lines = path.read_text(encoding="utf-8").splitlines()
    normalized = "\n".join(line.rstrip() for line in lines).strip()
    return hashlib.sha256(normalized.encode()).hexdigest()


def _inside_virtual_environment(path: Path) -> bool:
    """Return whether *path* is below a Python virtual environment."""
    for parent in path.parents:
        if parent == ROOT:
            return False
        if (parent / "pyvenv.cfg").is_file():
            return True
    return False


def _repository_files() -> list[Path]:
    output = subprocess.check_output(
        [
            "git",
            "ls-files",
            "--cached",
            "--others",
            "--exclude-standard",
            "-z",
        ],
        cwd=ROOT,
    )
    paths = (ROOT / item.decode() for item in output.split(b"\0") if item)
    return sorted(
        path
        for path in paths
        if path.is_file() and not _inside_virtual_environment(path)
    )


def _repository_sources() -> list[Path]:
    return [
        path for path in _repository_files() if path.suffix.lower() in SOURCE_SUFFIXES
    ]


def _check_license_texts(errors: list[str]) -> None:
    for filename, expected_digest in LICENSE_SHA256.items():
        path = ROOT / filename
        if not path.is_file():
            errors.append(f"missing {filename}")
        elif _normalized_digest(path) != expected_digest:
            errors.append(f"{filename} differs from the audited CeCILL 2.1 text")


def _check_metadata(errors: list[str]) -> None:
    metadata = tomllib.loads((ROOT / "pyproject.toml").read_text(encoding="utf-8"))
    project = metadata["project"]
    if project.get("license") != "CECILL-2.1":
        errors.append('pyproject.toml must declare license = "CECILL-2.1"')

    required_files = {
        "LICENSE",
        "LICENSE.en",
        "COPYRIGHT",
        "NOTICE-DATA.md",
        "THIRD_PARTY_NOTICES.md",
    }
    declared_files = set(project.get("license-files", []))
    missing = sorted(required_files - declared_files)
    if missing:
        errors.append(f"pyproject.toml license-files is missing: {', '.join(missing)}")

    citation = (ROOT / "CITATION.cff").read_text(encoding="utf-8")
    if "license: CECILL-2.1" not in citation:
        errors.append("CITATION.cff must declare CECILL-2.1")

    readme = (ROOT / "README.md").read_text(encoding="utf-8")
    if "CeCILL 2.1" not in readme:
        errors.append("README.md must identify CeCILL 2.1")


def _check_source_headers(errors: list[str]) -> None:
    for path in _repository_sources():
        if path.suffix.lower() == ".ipynb":
            metadata = json.loads(path.read_text(encoding="utf-8"))["metadata"]
            if COPYRIGHT_NOTICE not in metadata.get("copyright", ""):
                errors.append(f"missing notebook copyright: {path.relative_to(ROOT)}")
            if metadata.get("license") != "CECILL-2.1":
                errors.append(
                    f"missing notebook CeCILL metadata: {path.relative_to(ROOT)}"
                )
            continue
        header = "\n".join(path.read_text(encoding="utf-8-sig").splitlines()[:12])
        if COPYRIGHT_NOTICE not in header:
            errors.append(f"missing copyright header: {path.relative_to(ROOT)}")
        if SPDX_NOTICE not in header:
            errors.append(f"missing CeCILL SPDX header: {path.relative_to(ROOT)}")


def _check_dependency_inventory(errors: list[str]) -> None:
    constraints = (ROOT / "install" / "constraints.txt").read_text(encoding="utf-8")
    notices = (ROOT / "THIRD_PARTY_NOTICES.md").read_text(encoding="utf-8")
    for line in constraints.splitlines():
        if "==" not in line or line.lstrip().startswith("#"):
            continue
        name, version = line.split("==", maxsplit=1)
        if f"| `{name}` | `{version}` |" not in notices:
            errors.append(f"dependency notice is stale or missing: {name}=={version}")

    for project_file in (
        path for path in _repository_files() if path.suffix.lower() == ".csproj"
    ):
        try:
            root = ET.parse(project_file).getroot()
        except ET.ParseError as exc:
            errors.append(
                f"invalid .NET project file {project_file.relative_to(ROOT)}: {exc}"
            )
            continue

        for reference in root.iter():
            if reference.tag.rsplit("}", maxsplit=1)[-1] != "PackageReference":
                continue
            name = reference.get("Include") or reference.get("Update")
            version = reference.get("Version") or reference.get("VersionOverride")
            if version is None:
                version_element = next(
                    (
                        child
                        for child in reference
                        if child.tag.rsplit("}", maxsplit=1)[-1] == "Version"
                    ),
                    None,
                )
                version = version_element.text if version_element is not None else None
            if name and version and f"| `{name}` | `{version}` |" not in notices:
                errors.append(
                    f"dependency notice is stale or missing: {name}=={version}"
                )


def main() -> int:
    errors: list[str] = []
    _check_license_texts(errors)
    _check_metadata(errors)
    _check_source_headers(errors)
    _check_dependency_inventory(errors)
    if errors:
        print("Licensing checks failed:", file=sys.stderr)
        for error in errors:
            print(f"- {error}", file=sys.stderr)
        return 1
    print("Licensing checks passed (CeCILL 2.1 metadata, texts, and source notices).")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
