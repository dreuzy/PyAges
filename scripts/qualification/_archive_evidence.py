# Copyright (c) 2021-2026 Centre national de la recherche scientifique (CNRS)
# Contributor: Jean-Raynald de Dreuzy
# SPDX-License-Identifier: CECILL-2.1

"""Validate scientific result trees and Python distribution evidence.

An archive is useful only if its inputs already form a complete qualification
record. This module checks result manifests, retained multi-chain diagnostics,
artifact hashes, package identity, and wheel/sdist metadata before anything is
copied. It returns compact summaries that the outer archive manifest can bind
to the copied evidence.
"""

from __future__ import annotations

import csv
import json
import tarfile
import zipfile
from email.parser import Parser
from pathlib import Path, PurePosixPath
from typing import Any, Iterable, Literal

from scripts.qualification._archive_contract import regular_files, sha256


def read_key_values(path: Path) -> dict[str, str]:
    """Read a tab-separated two-column qualification summary."""
    try:
        return dict(
            line.split("\t", maxsplit=1)
            for line in path.read_text(encoding="utf-8").splitlines()
            if line
        )
    except ValueError as error:
        raise RuntimeError(f"Invalid key/value qualification file: {path}") from error


def validate_diagnostics(path: Path) -> None:
    """Require at least one included diagnostic and reject every failed gate."""
    with path.open(encoding="utf-8", newline="") as stream:
        reader = csv.DictReader(stream, delimiter="\t")
        required = {"included_in_qualification", "qualified"}
        if reader.fieldnames is None or not required <= set(reader.fieldnames):
            raise RuntimeError(f"Diagnostic table lacks qualification columns: {path}")
        included = [row for row in reader if row["included_in_qualification"] == "True"]
    if not included:
        raise RuntimeError(f"Diagnostic table has no qualified quantities: {path}")
    if any(row["qualified"] != "True" for row in included):
        raise RuntimeError(f"Diagnostic table contains a failed gate: {path}")


def validate_result_tree(  # noqa: C901 - validates all nested evidence layers
    root: Path,
) -> dict[str, Any]:
    """Validate one terminal workflow result and summarize its evidence.

    The result must use manifest schema 2, contain exactly the files recorded by
    that manifest, and provide qualified multi-chain outputs with at least two
    retained chains. Package and repository provenance are checked here so the
    archive builder can later bind them to a release source snapshot.
    """
    root = root.resolve()
    if not root.is_dir():
        raise NotADirectoryError(root)
    manifest_path = root / "result_manifest.json"
    if not manifest_path.is_file():
        raise FileNotFoundError(manifest_path)
    try:
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as error:
        raise RuntimeError(f"Invalid result manifest JSON: {manifest_path}") from error
    if not isinstance(manifest, dict) or manifest.get("status") != "complete":
        raise RuntimeError(f"Result tree is not terminal and complete: {root}")
    if manifest.get("schema_version") != 2:
        raise RuntimeError(f"Unsupported result manifest schema in {root}")
    if manifest.get("workflow") not in {"single_date", "temporal"}:
        raise RuntimeError(f"Unknown result workflow in {root}")
    artifacts = manifest.get("artifacts_sha256")
    if not isinstance(artifacts, dict) or not all(
        isinstance(name, str) and isinstance(digest, str)
        for name, digest in artifacts.items()
    ):
        raise RuntimeError(f"Result manifest has no valid artifact inventory: {root}")
    state_path = root / ".pyages-run-state.json"
    if state_path.exists():
        raise RuntimeError(
            f"Result tree still contains a staging journal: {state_path}"
        )
    actual = {
        path.relative_to(root).as_posix(): sha256(path)
        for path in regular_files(root)
        if path != manifest_path
    }
    if actual != artifacts:
        missing = sorted(set(artifacts) - set(actual))
        unexpected = sorted(set(actual) - set(artifacts))
        changed = sorted(
            name
            for name in set(actual) & set(artifacts)
            if actual[name] != artifacts[name]
        )
        raise RuntimeError(
            "Result artifacts do not match result_manifest.json: "
            f"missing={missing}, unexpected={unexpected}, changed={changed}"
        )

    diagnostic_paths = sorted(root.rglob("mcmc_diagnostics.tsv"))
    if not diagnostic_paths:
        raise RuntimeError(f"Result tree contains no multi-chain diagnostics: {root}")
    qualified_directories: list[str] = []
    for diagnostics in diagnostic_paths:
        method_directory = diagnostics.parent
        results_path = method_directory / "results_calibration.txt"
        provenance_path = method_directory / "ensemble_provenance.txt"
        if not results_path.is_file() or not provenance_path.is_file():
            raise RuntimeError(
                f"Incomplete multi-chain qualification artifacts beside {diagnostics}"
            )
        results = read_key_values(results_path)
        provenance = read_key_values(provenance_path)
        if results.get("qualification_status") != "qualified":
            raise RuntimeError(f"Multi-chain result is not qualified: {results_path}")
        if results.get("pooling_written") != "True":
            raise RuntimeError(f"Qualified pooling is absent: {results_path}")
        if provenance.get("execution_mode") != "multi_chain":
            raise RuntimeError(
                f"Result is not a multi-chain execution: {provenance_path}"
            )
        if provenance.get("qualification_status") != "qualified":
            raise RuntimeError(f"Provenance is not qualified: {provenance_path}")
        validate_diagnostics(diagnostics)
        chain_tables = list(
            (method_directory / "chains").glob("chain_*/lpm_dist_calibrated.txt")
        )
        if len(chain_tables) < 2:
            raise RuntimeError(f"Fewer than two retained chains beside {diagnostics}")
        qualified_directories.append(method_directory.relative_to(root).as_posix())

    configuration = manifest.get("configuration")
    package = manifest.get("package")
    repository = manifest.get("repository")
    if not isinstance(configuration, dict) or not isinstance(
        configuration.get("sha256"), str
    ):
        raise RuntimeError(f"Result manifest has no configuration digest: {root}")
    if not isinstance(package, dict) or not isinstance(package.get("version"), str):
        raise RuntimeError(f"Result manifest has no package version: {root}")
    if str(package.get("name", "")).lower().replace("_", "-") != "pyages":
        raise RuntimeError(f"Result manifest does not identify PyAges: {root}")
    if manifest.get("pyages_version") != package["version"]:
        raise RuntimeError(f"Result manifest has inconsistent PyAges versions: {root}")
    if not isinstance(repository, dict):
        raise RuntimeError(f"Result manifest has no repository provenance: {root}")
    repository_head = repository.get("git_head")
    repository_dirty = repository.get("dirty")
    if repository_head is not None and (
        not isinstance(repository_head, str) or not repository_head
    ):
        raise RuntimeError(f"Result manifest has invalid repository HEAD: {root}")
    if repository_dirty is not None and not isinstance(repository_dirty, bool):
        raise RuntimeError(f"Result manifest has invalid repository status: {root}")
    return {
        "workflow": manifest.get("workflow"),
        "run_id": manifest.get("run_id"),
        "configuration_sha256": configuration["sha256"],
        "package_version": package["version"],
        "repository_git_head": repository_head,
        "repository_dirty": repository_dirty,
        "qualified_directories": qualified_directories,
        "artifact_count": len(artifacts),
        "manifest_sha256": sha256(manifest_path),
    }


def metadata_identity(text: str, source: Path) -> tuple[str, str]:
    """Return normalized package name and version from distribution metadata."""
    metadata = Parser().parsestr(text)
    name = metadata.get("Name")
    version = metadata.get("Version")
    if not name or not version:
        raise RuntimeError(f"Distribution metadata lacks Name or Version: {source}")
    return name, version


def distribution_identity(  # noqa: C901 - validates all supported containers
    path: Path,
) -> tuple[str, str, Literal["wheel", "sdist"]]:
    """Validate a wheel or sdist and return its package identity and kind.

    ZIP integrity is checked for wheels and ZIP sdists. Tar sdists are read in
    full so truncated members fail before metadata is trusted. Multiple
    ``PKG-INFO`` files are accepted only when they identify the same package.
    """
    if path.suffix == ".whl":
        with zipfile.ZipFile(path) as archive:
            corrupt = archive.testzip()
            if corrupt is not None:
                raise RuntimeError(
                    f"Wheel contains a corrupt member {corrupt!r}: {path}"
                )
            candidates = sorted(
                name
                for name in archive.namelist()
                if name.endswith(".dist-info/METADATA")
            )
            if len(candidates) != 1:
                raise RuntimeError(f"Wheel must contain exactly one METADATA: {path}")
            name, version = metadata_identity(
                archive.read(candidates[0]).decode("utf-8"), path
            )
        return name, version, "wheel"
    if path.name.endswith((".tar.gz", ".tar.bz2", ".tar.xz")):
        with tarfile.open(path, "r:*") as archive:
            for member in archive.getmembers():
                if not member.isfile():
                    continue
                stream = archive.extractfile(member)
                if stream is None:  # pragma: no cover - guarded by member.isfile()
                    raise RuntimeError(
                        f"Cannot read sdist member {member.name}: {path}"
                    )
                for _block in iter(lambda source=stream: source.read(1024 * 1024), b""):
                    pass
            candidates = sorted(
                (
                    member
                    for member in archive.getmembers()
                    if member.isfile() and PurePosixPath(member.name).name == "PKG-INFO"
                ),
                key=lambda member: member.name,
            )
            if not candidates:
                raise RuntimeError(f"Sdist contains no PKG-INFO: {path}")
            identities: list[tuple[str, str]] = []
            for candidate in candidates:
                stream = archive.extractfile(candidate)
                if stream is None:  # pragma: no cover - guarded by member.isfile()
                    raise RuntimeError(f"Cannot read sdist metadata: {path}")
                identities.append(
                    metadata_identity(stream.read().decode("utf-8"), path)
                )
            if len(set(identities)) != 1:
                raise RuntimeError(f"Sdist has inconsistent PKG-INFO metadata: {path}")
            name, version = identities[0]
        return name, version, "sdist"
    if path.suffix == ".zip":
        with zipfile.ZipFile(path) as archive:
            corrupt = archive.testzip()
            if corrupt is not None:
                raise RuntimeError(
                    f"Sdist contains a corrupt member {corrupt!r}: {path}"
                )
            candidates = sorted(
                name
                for name in archive.namelist()
                if PurePosixPath(name).name == "PKG-INFO"
            )
            if not candidates:
                raise RuntimeError(f"Sdist contains no PKG-INFO: {path}")
            identities = [
                metadata_identity(archive.read(candidate).decode("utf-8"), path)
                for candidate in candidates
            ]
            if len(set(identities)) != 1:
                raise RuntimeError(f"Sdist has inconsistent PKG-INFO metadata: {path}")
            name, version = identities[0]
        return name, version, "sdist"
    raise ValueError(f"Unsupported distribution archive: {path}")


def validate_publishable_result_provenance(
    summaries: Iterable[dict[str, Any]], publication: dict[str, Any]
) -> None:
    """Bind publishable results to the exact clean source revision archived."""
    if publication.get("mode") != "publishable":
        return
    expected_head = publication.get("git_head")
    if not isinstance(expected_head, str) or not expected_head:
        raise RuntimeError("Publishable archive has no valid Git HEAD")
    for summary in summaries:
        if summary.get("repository_git_head") != expected_head:
            raise RuntimeError(
                "Publishable result was not produced from the tagged Git commit: "
                f"{summary.get('run_id')}"
            )
        if summary.get("repository_dirty") is not False:
            raise RuntimeError(
                "Publishable result was produced from a dirty or unknown worktree: "
                f"{summary.get('run_id')}"
            )
