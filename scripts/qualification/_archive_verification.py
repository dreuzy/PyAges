# Copyright (c) 2021-2026 Centre national de la recherche scientifique (CNRS)
# Contributor: Jean-Raynald de Dreuzy
# SPDX-License-Identifier: CECILL-2.1

"""Cross-check an extracted qualification archive against its manifest.

Container checks alone cannot prove that the recorded result, protocol,
distribution, environment, and source paths still describe the extracted
payload. This module validates those semantic links after safe extraction. It
does not open the outer ZIP or verify its adjacent checksum sidecar.
"""

from __future__ import annotations

import zipfile
from collections.abc import Callable
from pathlib import Path, PurePosixPath
from typing import Any

from scripts.qualification._archive_contract import safe_portable_path, sha256
from scripts.qualification._archive_evidence import (
    distribution_identity,
    validate_publishable_result_provenance,
    validate_result_tree,
)


def safe_member_names(archive: zipfile.ZipFile) -> list[str]:
    """Return unique safe member names and reject symbolic-link entries."""
    names = archive.namelist()
    if len(names) != len(set(names)):
        raise RuntimeError("Qualification archive contains duplicate members")
    for member in archive.infolist():
        name = member.filename
        safe_portable_path(name, context="member")
        file_type = (member.external_attr >> 16) & 0o170000
        if file_type == 0o120000:
            raise RuntimeError(f"Qualification archive member is a symlink: {name}")
    return names


def validated_archive_entries(manifest: dict[str, Any]) -> list[dict[str, Any]]:
    """Return the validated, duplicate-free payload inventory."""
    entries = manifest.get("files")
    if not isinstance(entries, list) or not entries:
        raise RuntimeError("Qualification archive inventory is invalid")
    paths: list[str] = []
    for item in entries:
        if not isinstance(item, dict):
            raise RuntimeError("Qualification archive inventory entry is invalid")
        path = item.get("path")
        size = item.get("bytes")
        digest = item.get("sha256")
        if (
            not isinstance(path, str)
            or not isinstance(size, int)
            or isinstance(size, bool)
            or size < 0
            or not isinstance(digest, str)
            or len(digest) != 64
            or any(character not in "0123456789abcdef" for character in digest)
        ):
            raise RuntimeError("Qualification archive inventory entry is invalid")
        safe_portable_path(path, context="inventory path")
        paths.append(path)
    if len(paths) != len(set(paths)):
        raise RuntimeError("Qualification archive inventory contains duplicates")
    return entries


def validate_publication_record(manifest: dict[str, Any]) -> None:
    """Check that draft or publishable labels agree with recorded Git state."""
    publication = manifest.get("publication")
    if not isinstance(publication, dict):
        raise RuntimeError("Qualification archive publication record is invalid")
    mode = publication.get("mode")
    if mode == "draft":
        if publication.get("publishable") is not False:
            raise RuntimeError("Draft qualification archive is labelled publishable")
        return
    if mode != "publishable":
        raise RuntimeError("Qualification archive mode is invalid")
    if (
        publication.get("publishable") is not True
        or publication.get("publishable_criteria_met") is not True
        or publication.get("blockers") != []
        or publication.get("git_status") != []
        or not isinstance(publication.get("git_head"), str)
        or not publication.get("git_head")
        or publication.get("expected_tag_annotated") is not True
        or publication.get("expected_tag") != manifest.get("pyages_version")
    ):
        raise RuntimeError("Publishable qualification archive identity is inconsistent")


def contained_path(root: Path, value: object, prefix: str) -> Path:
    """Resolve one manifest path below ``root`` and require its top-level group."""
    relative = safe_portable_path(value, context="semantic path")
    if relative.parts[0] != prefix:
        raise RuntimeError(f"Unsafe qualification archive semantic path: {value}")
    resolved_root = root.resolve()
    candidate = resolved_root.joinpath(*relative.parts).resolve()
    try:
        candidate.relative_to(resolved_root)
    except ValueError as error:  # pragma: no cover - guarded cross-platform above
        raise RuntimeError(
            f"Unsafe qualification archive semantic path: {value}"
        ) from error
    return candidate


def validate_extracted_semantics(  # noqa: C901 - cross-links evidence layers
    root: Path,
    manifest: dict[str, Any],
    *,
    result_validator: Callable[[Path], dict[str, Any]] = validate_result_tree,
) -> None:
    """Recompute and cross-check every semantic record after extraction.

    Result summaries are rebuilt from their nested manifests, protocol and
    distribution hashes are checked, and publishable archives are required to
    contain clean source evidence. Thus a self-consistent ZIP inventory is not
    accepted when its higher-level scientific records disagree.
    """
    archive_version = manifest.get("pyages_version")
    if not isinstance(archive_version, str) or not archive_version:
        raise RuntimeError("Qualification archive PyAges version is invalid")
    results = manifest.get("results")
    if not isinstance(results, list) or not results:
        raise RuntimeError("Qualification archive contains no result records")
    summaries: list[dict[str, Any]] = []
    for result in results:
        if not isinstance(result, dict) or not isinstance(result.get("path"), str):
            raise RuntimeError("Qualification archive result record is invalid")
        summary = result_validator(contained_path(root, result["path"], "results"))
        for key in (
            "workflow",
            "run_id",
            "configuration_sha256",
            "package_version",
            "repository_git_head",
            "repository_dirty",
            "qualified_directories",
            "artifact_count",
            "manifest_sha256",
        ):
            if summary[key] != result.get(key):
                raise RuntimeError(
                    f"Archived result summary changed for {result['path']}: {key}"
                )
        summaries.append(summary)
    if any(summary["package_version"] != archive_version for summary in summaries):
        raise RuntimeError("Archived result versions do not match the archive")
    publication = manifest.get("publication")
    if not isinstance(publication, dict):  # pragma: no cover - checked before extract
        raise RuntimeError("Qualification archive publication record is invalid")
    validate_publishable_result_provenance(summaries, publication)

    protocol = manifest.get("protocol")
    if not isinstance(protocol, dict):
        raise RuntimeError("Qualification archive protocol record is invalid")
    for group in ("yaml", "tests", "reports"):
        records = protocol.get(group)
        if not isinstance(records, list) or not records:
            raise RuntimeError(f"Qualification archive has no supplied {group}")
        for record in records:
            if not isinstance(record, dict) or not isinstance(record.get("path"), str):
                raise RuntimeError(f"Qualification archive {group} record is invalid")
            supplied = contained_path(root, record["path"], "protocol")
            parts = PurePosixPath(record["path"]).parts
            if len(parts) < 3 or parts[1] != group:
                raise RuntimeError(f"Qualification archive {group} path is invalid")
            if not supplied.is_file() or sha256(supplied) != record.get("sha256"):
                raise RuntimeError(f"Qualification archive {group} hash is invalid")
    yaml_digests = {record.get("sha256") for record in protocol["yaml"]}
    if any(
        summary["configuration_sha256"] not in yaml_digests for summary in summaries
    ):
        raise RuntimeError("Archived result configuration has no supplied YAML")

    environment = manifest.get("environment")
    if (
        not isinstance(environment, list)
        or not environment
        or not all(isinstance(value, str) for value in environment)
        or len(environment) != len(set(environment))
    ):
        raise RuntimeError("Qualification archive environment record is invalid")
    for value in environment:
        if not contained_path(root, value, "environment").is_file():
            raise RuntimeError("Qualification archive environment file is missing")

    source = manifest.get("source")
    if not isinstance(source, dict) or not isinstance(
        source.get("dirty_snapshot_complete"), bool
    ):
        raise RuntimeError("Qualification archive source record is invalid")
    if (
        publication.get("mode") == "publishable"
        and not source["dirty_snapshot_complete"]
    ):
        raise RuntimeError("Publishable archive source snapshot is incomplete")
    source_paths: dict[str, Path] = {}
    for key in ("git_archive", "git_status", "tracked_changes", "untracked_inventory"):
        source_path = contained_path(root, source.get(key), "source")
        if not source_path.is_file():
            raise RuntimeError(f"Qualification archive source file is missing: {key}")
        source_paths[key] = source_path
    if publication.get("mode") == "publishable" and (
        source_paths["git_status"].read_text(encoding="utf-8").strip()
        or source_paths["tracked_changes"].read_bytes()
        or source_paths["untracked_inventory"].read_text(encoding="utf-8").strip()
    ):
        raise RuntimeError("Publishable archive contains dirty source evidence")

    records = manifest.get("distributions")
    if not isinstance(records, list) or len(records) != 2:
        raise RuntimeError("Qualification archive distribution records are invalid")
    kinds: list[str] = []
    for record in records:
        filename = record.get("filename") if isinstance(record, dict) else None
        try:
            filename_path = safe_portable_path(
                filename, context="distribution filename"
            )
        except RuntimeError as error:
            raise RuntimeError(
                "Qualification archive distribution filename is invalid"
            ) from error
        if len(filename_path.parts) != 1:
            raise RuntimeError("Qualification archive distribution filename is invalid")
        distribution = contained_path(
            root, f"distributions/{filename}", "distributions"
        )
        name, version, kind = distribution_identity(distribution)
        kinds.append(kind)
        if (
            name.lower().replace("_", "-") != "pyages"
            or name != record.get("name")
            or version != record.get("version")
            or version != archive_version
            or kind != record.get("kind")
            or sha256(distribution) != record.get("sha256")
        ):
            raise RuntimeError(
                f"Archived distribution metadata changed: {distribution}"
            )
    if sorted(kinds) != ["sdist", "wheel"]:
        raise RuntimeError("Qualification archive must contain one wheel and one sdist")
