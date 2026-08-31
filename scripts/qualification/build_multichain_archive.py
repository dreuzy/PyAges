# Copyright (c) 2021-2026 Centre national de la recherche scientifique (CNRS)
# Contributor: Jean-Raynald de Dreuzy
# SPDX-License-Identifier: CECILL-2.1

"""Build and verify self-contained multi-chain qualification archives."""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import os
import platform
import shutil
import subprocess
import sys
import tarfile
import tempfile
import zipfile
from email.parser import Parser
from pathlib import Path, PurePosixPath, PureWindowsPath
from typing import Any, Iterable, Literal

from pyages import __version__

ROOT = Path(__file__).resolve().parents[2]
ARCHIVE_MANIFEST = "QUALIFICATION_ARCHIVE.json"
ARCHIVE_CHECKSUMS = "CHECKSUMS.sha256"
ARCHIVE_README = "README.md"
ARCHIVE_SCHEMA_VERSION = 1
ZIP_TIMESTAMP = (1980, 1, 1, 0, 0, 0)


def _safe_portable_path(value: object, *, context: str) -> PurePosixPath:
    """Return one canonical relative POSIX path that is safe on every OS."""
    if not isinstance(value, str) or not value or "\\" in value:
        raise RuntimeError(f"Unsafe qualification archive {context}: {value}")
    relative = PurePosixPath(value)
    if (
        relative.is_absolute()
        or not relative.parts
        or ".." in relative.parts
        or value != relative.as_posix()
        or any(PureWindowsPath(part).drive for part in relative.parts)
    ):
        raise RuntimeError(f"Unsafe qualification archive {context}: {value}")
    return relative


def sha256(path: Path) -> str:
    """Return the hexadecimal SHA-256 digest of one file."""
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _git_text(*args: str) -> str:
    return subprocess.run(
        ["git", *args],
        cwd=ROOT,
        capture_output=True,
        text=True,
        check=True,
    ).stdout.strip()


def _git_bytes(*args: str) -> bytes:
    return subprocess.run(
        ["git", *args],
        cwd=ROOT,
        capture_output=True,
        check=True,
    ).stdout


def _write_git_archive(destination: Path, head: str) -> None:
    subprocess.run(
        ["git", "archive", "--format=tar", "-o", str(destination), head],
        cwd=ROOT,
        check=True,
    )


def _is_link_or_junction(path: Path) -> bool:
    is_junction = getattr(os.path, "isjunction", lambda _path: False)
    return path.is_symlink() or bool(is_junction(path))


def _regular_files(root: Path) -> list[Path]:
    if _is_link_or_junction(root):
        raise ValueError(f"Input tree is a symbolic link or junction: {root}")
    files: list[Path] = []
    for current, directories, filenames in os.walk(root, followlinks=False):
        current_path = Path(current)
        for name in directories:
            candidate = current_path / name
            if _is_link_or_junction(candidate):
                raise ValueError(
                    f"Input tree contains a symbolic link or junction: {candidate}"
                )
        for name in filenames:
            candidate = current_path / name
            if _is_link_or_junction(candidate):
                raise ValueError(f"Input tree contains a symbolic link: {candidate}")
            if not candidate.is_file():
                raise ValueError(f"Input tree contains a non-regular file: {candidate}")
            files.append(candidate)
    return sorted(files, key=lambda path: path.relative_to(root).as_posix())


def _read_key_values(path: Path) -> dict[str, str]:
    try:
        return dict(
            line.split("\t", maxsplit=1)
            for line in path.read_text(encoding="utf-8").splitlines()
            if line
        )
    except ValueError as error:
        raise RuntimeError(f"Invalid key/value qualification file: {path}") from error


def _validate_diagnostics(path: Path) -> None:
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


def _validate_result_tree(  # noqa: C901 - validates all nested evidence layers
    root: Path,
) -> dict[str, Any]:
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
        for path in _regular_files(root)
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
        results = _read_key_values(results_path)
        provenance = _read_key_values(provenance_path)
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
        _validate_diagnostics(diagnostics)
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


def _metadata_identity(text: str, source: Path) -> tuple[str, str]:
    metadata = Parser().parsestr(text)
    name = metadata.get("Name")
    version = metadata.get("Version")
    if not name or not version:
        raise RuntimeError(f"Distribution metadata lacks Name or Version: {source}")
    return name, version


def _distribution_identity(  # noqa: C901 - validates wheel and both sdist containers
    path: Path,
) -> tuple[str, str, Literal["wheel", "sdist"]]:
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
            name, version = _metadata_identity(
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
                    _metadata_identity(stream.read().decode("utf-8"), path)
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
                _metadata_identity(archive.read(candidate).decode("utf-8"), path)
                for candidate in candidates
            ]
            if len(set(identities)) != 1:
                raise RuntimeError(f"Sdist has inconsistent PKG-INFO metadata: {path}")
            name, version = identities[0]
        return name, version, "sdist"
    raise ValueError(f"Unsupported distribution archive: {path}")


def _publication_state(
    mode: Literal["draft", "publishable"], expected_tag: str | None
) -> dict[str, Any]:
    head = _git_text("rev-parse", "HEAD")
    status = _git_text("status", "--porcelain=v1", "--untracked-files=all")
    tags = sorted(
        tag for tag in _git_text("tag", "--points-at", "HEAD").splitlines() if tag
    )
    annotated = False
    if expected_tag in tags:
        annotated = _git_text("cat-file", "-t", f"refs/tags/{expected_tag}") == "tag"
    blockers: list[str] = []
    if status:
        blockers.append("Git worktree is dirty")
    if expected_tag is None:
        blockers.append("No expected release tag was supplied")
    elif expected_tag not in tags:
        blockers.append(f"Expected tag {expected_tag!r} does not point at HEAD")
    elif not annotated:
        blockers.append(f"Expected tag {expected_tag!r} is not annotated")
    if expected_tag is not None and expected_tag != __version__:
        blockers.append(
            f"Expected tag {expected_tag!r} does not identify version {__version__!r}"
        )
    if mode == "publishable" and blockers:
        raise RuntimeError("Archive is not publishable: " + "; ".join(blockers))
    return {
        "mode": mode,
        "publishable": mode == "publishable",
        "publishable_criteria_met": not blockers,
        "blockers": blockers,
        "git_head": head,
        "git_status": status.splitlines(),
        "git_tags_at_head": tags,
        "expected_tag": expected_tag,
        "expected_tag_annotated": annotated,
    }


def _is_within(path: Path, directory: Path) -> bool:
    """Return whether a resolved path is contained by a resolved directory."""
    try:
        path.resolve().relative_to(directory.resolve())
    except ValueError:
        return False
    return True


def _validate_publishable_result_provenance(
    summaries: Iterable[dict[str, Any]], publication: dict[str, Any]
) -> None:
    """Bind publishable results to the exact clean source revision being archived."""
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


def _recheck_publishable_state(
    publication: dict[str, Any], expected_tag: str | None
) -> None:
    """Reject a source-state change between initial validation and ZIP sealing."""
    if publication.get("mode") != "publishable":
        return
    confirmed = _publication_state("publishable", expected_tag)
    if confirmed != publication:
        raise RuntimeError(
            "Git publication state changed while the qualification archive was built"
        )


def _copy_file(source: Path, destination: Path) -> None:
    if _is_link_or_junction(source):
        raise ValueError(f"Input file is a symbolic link or junction: {source}")
    if not source.is_file():
        raise FileNotFoundError(source)
    destination.parent.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(source, destination)


def _copy_group(sources: Iterable[Path], destination: Path) -> list[dict[str, Any]]:
    entries: list[dict[str, Any]] = []
    for index, source in enumerate(sources, start=1):
        source = source.resolve()
        relative = Path(f"{index:03d}-{source.name}")
        target = destination / relative
        _copy_file(source, target)
        entries.append(
            {
                "path": target.relative_to(destination.parent.parent).as_posix(),
                "sha256": sha256(target),
            }
        )
    return entries


def _copy_result_tree(source: Path, destination: Path) -> None:
    destination.mkdir(parents=True)
    for path in _regular_files(source):
        relative = path.relative_to(source)
        target = destination / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(path, target)


def _write_environment(destination: Path, extra_files: Iterable[Path]) -> list[str]:
    destination.mkdir(parents=True)
    freeze = subprocess.run(
        [sys.executable, "-m", "pip", "freeze", "--all"],
        cwd=ROOT,
        capture_output=True,
        text=True,
        check=True,
    ).stdout
    normalized_freeze = "\n".join(
        sorted(line.strip() for line in freeze.splitlines() if line.strip())
    )
    (destination / "pip-freeze.txt").write_text(
        normalized_freeze + "\n", encoding="utf-8", newline="\n"
    )
    runtime = {
        "python_implementation": platform.python_implementation(),
        "python_version": platform.python_version(),
        "platform": platform.platform(),
        "pyages_version": __version__,
    }
    (destination / "runtime.json").write_text(
        json.dumps(runtime, sort_keys=True, indent=2) + "\n", encoding="utf-8"
    )
    names = ["environment/pip-freeze.txt", "environment/runtime.json"]
    for index, source in enumerate(extra_files, start=1):
        target = destination / f"extra-{index:03d}-{source.name}"
        _copy_file(source.resolve(), target)
        names.append(f"environment/{target.name}")
    return names


def _archive_readme(publication: dict[str, Any]) -> str:
    if publication["mode"] == "draft":
        heading = "# DRAFT — NOT PUBLISHABLE"
        warning = (
            "This archive was intentionally built in draft mode. Review the "
            "blockers in `QUALIFICATION_ARCHIVE.json`; rebuild in publishable "
            "mode from a clean, version-tagged commit before release."
        )
    else:
        heading = "# Publishable multi-chain qualification archive"
        warning = (
            "The builder verified a clean worktree, an annotated version-matching "
            "tag, qualified result manifests, distributions, and archive hashes."
        )
    blockers = publication["blockers"] or ["none"]
    blocker_lines = "\n".join(f"- {blocker}" for blocker in blockers)
    return f"""{heading}

{warning}

Publication blockers recorded by the builder:

{blocker_lines}

Run:

```bash
python -m scripts.qualification.build_multichain_archive verify <archive.zip>
```

`CHECKSUMS.sha256` covers every member except itself. The ZIP SHA-256 sidecar
checks the integrity of the complete container; it is not an origin signature.
"""


def _payload_entries(root: Path) -> list[dict[str, Any]]:
    excluded = {root / ARCHIVE_MANIFEST, root / ARCHIVE_CHECKSUMS}
    entries: list[dict[str, Any]] = []
    for path in _regular_files(root):
        if path in excluded:
            continue
        relative = path.relative_to(root).as_posix()
        _safe_portable_path(relative, context="payload path")
        entries.append(
            {
                "path": relative,
                "bytes": path.stat().st_size,
                "sha256": sha256(path),
            }
        )
    return entries


def _write_deterministic_zip(source: Path, output: Path) -> None:
    temporary = output.with_name(f".{output.name}.staging-{os.getpid()}")
    try:
        with zipfile.ZipFile(
            temporary,
            "w",
            compression=zipfile.ZIP_DEFLATED,
            compresslevel=9,
        ) as archive:
            for path in _regular_files(source):
                relative = path.relative_to(source).as_posix()
                _safe_portable_path(relative, context="member")
                info = zipfile.ZipInfo(relative, ZIP_TIMESTAMP)
                info.compress_type = zipfile.ZIP_DEFLATED
                info.create_system = 3
                info.external_attr = 0o100644 << 16
                with path.open("rb") as stream, archive.open(info, "w") as target:
                    shutil.copyfileobj(stream, target, length=1024 * 1024)
        temporary.replace(output)
    finally:
        temporary.unlink(missing_ok=True)


def build_archive(  # noqa: C901 - transactional assembly has explicit gates
    *,
    results: Iterable[Path],
    yaml_files: Iterable[Path],
    test_files: Iterable[Path],
    reports: Iterable[Path],
    distributions: Iterable[Path],
    output: Path,
    mode: Literal["draft", "publishable"],
    expected_tag: str | None = None,
    environment_files: Iterable[Path] = (),
) -> Path:
    """Build one immutable ZIP from qualified multi-chain result trees."""
    result_paths = tuple(Path(path).resolve() for path in results)
    yaml_paths = tuple(Path(path).resolve() for path in yaml_files)
    test_paths = tuple(Path(path).resolve() for path in test_files)
    report_paths = tuple(Path(path).resolve() for path in reports)
    distribution_paths = tuple(Path(path).resolve() for path in distributions)
    environment_paths = tuple(Path(path).resolve() for path in environment_files)
    if not result_paths or not yaml_paths or not test_paths or not report_paths:
        raise ValueError("At least one result, YAML, test, and report is required")
    if mode not in {"draft", "publishable"}:
        raise ValueError("mode must be 'draft' or 'publishable'")
    output = Path(output).resolve()
    sidecar = output.with_name(f"{output.name}.sha256")
    if output.suffix != ".zip":
        raise ValueError("Archive output must use the .zip suffix")
    if output.exists() or sidecar.exists():
        raise FileExistsError(f"Refusing to replace archive or sidecar: {output}")
    if mode == "publishable" and _is_within(output, ROOT):
        raise ValueError(
            "Publishable archive output must be outside the source repository"
        )
    for result in result_paths:
        if output == result or result in output.parents or output in result.parents:
            raise ValueError("Archive output and result trees must be separate")

    publication = _publication_state(mode, expected_tag)
    result_summaries = [_validate_result_tree(path) for path in result_paths]
    yaml_digests = {sha256(path) for path in yaml_paths}
    for summary in result_summaries:
        if summary["configuration_sha256"] not in yaml_digests:
            raise RuntimeError(
                "Each result manifest configuration digest must match a supplied YAML"
            )

    distribution_records = []
    kinds: list[str] = []
    for path in distribution_paths:
        name, version, kind = _distribution_identity(path)
        kinds.append(kind)
        distribution_records.append(
            {
                "filename": path.name,
                "kind": kind,
                "name": name,
                "version": version,
                "sha256": sha256(path),
            }
        )
    if sorted(kinds) != ["sdist", "wheel"]:
        raise RuntimeError("Supply exactly one wheel and one source distribution")
    identities = {
        (record["name"].lower().replace("_", "-"), record["version"])
        for record in distribution_records
    }
    if identities != {("pyages", __version__)}:
        raise RuntimeError(
            f"Wheel and sdist must both identify PyAges version {__version__}"
        )
    if any(summary["package_version"] != __version__ for summary in result_summaries):
        raise RuntimeError("Qualified result package versions do not match the archive")
    _validate_publishable_result_provenance(result_summaries, publication)

    output.parent.mkdir(parents=True, exist_ok=True)
    staging = Path(tempfile.mkdtemp(prefix=f".{output.stem}-", dir=output.parent))
    try:
        archived_results: list[dict[str, Any]] = []
        for index, (source, summary) in enumerate(
            zip(result_paths, result_summaries, strict=True), start=1
        ):
            relative = Path("results") / f"{index:03d}-{source.name}"
            _copy_result_tree(source, staging / relative)
            archived_results.append({"path": relative.as_posix(), **summary})

        protocol = {
            "yaml": _copy_group(yaml_paths, staging / "protocol/yaml"),
            "tests": _copy_group(test_paths, staging / "protocol/tests"),
            "reports": _copy_group(report_paths, staging / "protocol/reports"),
        }
        distribution_dir = staging / "distributions"
        for source in distribution_paths:
            _copy_file(source, distribution_dir / source.name)
        environment = _write_environment(staging / "environment", environment_paths)

        source_dir = staging / "source"
        source_dir.mkdir(parents=True)
        _write_git_archive(source_dir / "pyages-source.tar", publication["git_head"])
        (source_dir / "git-status.txt").write_text(
            "\n".join(publication["git_status"]) + "\n",
            encoding="utf-8",
            newline="\n",
        )
        (source_dir / "tracked-changes.patch").write_bytes(
            _git_bytes("diff", "--binary", "HEAD")
        )
        untracked = _git_text("ls-files", "--others", "--exclude-standard")
        (source_dir / "untracked-files.txt").write_text(
            untracked + ("\n" if untracked else ""), encoding="utf-8", newline="\n"
        )
        (staging / ARCHIVE_README).write_text(
            _archive_readme(publication), encoding="utf-8", newline="\n"
        )

        entries = _payload_entries(staging)
        manifest = {
            "schema_version": ARCHIVE_SCHEMA_VERSION,
            "archive_kind": "pyages-multichain-qualification",
            "pyages_version": __version__,
            "publication": publication,
            "results": archived_results,
            "protocol": protocol,
            "distributions": distribution_records,
            "environment": environment,
            "source": {
                "git_archive": "source/pyages-source.tar",
                "git_status": "source/git-status.txt",
                "tracked_changes": "source/tracked-changes.patch",
                "untracked_inventory": "source/untracked-files.txt",
                "dirty_snapshot_complete": not publication["git_status"],
            },
            "files": entries,
        }
        manifest_path = staging / ARCHIVE_MANIFEST
        manifest_path.write_text(
            json.dumps(manifest, ensure_ascii=False, sort_keys=True, indent=2) + "\n",
            encoding="utf-8",
            newline="\n",
        )
        checksummed = [
            *entries,
            {
                "path": ARCHIVE_MANIFEST,
                "bytes": manifest_path.stat().st_size,
                "sha256": sha256(manifest_path),
            },
        ]
        (staging / ARCHIVE_CHECKSUMS).write_text(
            "".join(
                f"{item['sha256']}  {item['path']}\n"
                for item in sorted(checksummed, key=lambda item: item["path"])
            ),
            encoding="ascii",
            newline="\n",
        )
        _recheck_publishable_state(publication, expected_tag)
        _write_deterministic_zip(staging, output)
        sidecar.write_text(
            f"{sha256(output)}  {output.name}\n", encoding="ascii", newline="\n"
        )
        verify_archive(output)
    except Exception:
        output.unlink(missing_ok=True)
        sidecar.unlink(missing_ok=True)
        raise
    finally:
        shutil.rmtree(staging, ignore_errors=True)
    return output


def _safe_member_names(archive: zipfile.ZipFile) -> list[str]:
    names = archive.namelist()
    if len(names) != len(set(names)):
        raise RuntimeError("Qualification archive contains duplicate members")
    for member in archive.infolist():
        name = member.filename
        _safe_portable_path(name, context="member")
        file_type = (member.external_attr >> 16) & 0o170000
        if file_type == 0o120000:
            raise RuntimeError(f"Qualification archive member is a symlink: {name}")
    return names


def _validated_archive_entries(manifest: dict[str, Any]) -> list[dict[str, Any]]:
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
        _safe_portable_path(path, context="inventory path")
        paths.append(path)
    if len(paths) != len(set(paths)):
        raise RuntimeError("Qualification archive inventory contains duplicates")
    return entries


def _validate_publication_record(manifest: dict[str, Any]) -> None:
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


def _contained_path(root: Path, value: object, prefix: str) -> Path:
    relative = _safe_portable_path(value, context="semantic path")
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


def _validate_extracted_semantics(  # noqa: C901 - cross-links nested records
    root: Path, manifest: dict[str, Any]
) -> None:
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
        summary = _validate_result_tree(
            _contained_path(root, result["path"], "results")
        )
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
    _validate_publishable_result_provenance(summaries, publication)

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
            supplied = _contained_path(root, record["path"], "protocol")
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
        if not _contained_path(root, value, "environment").is_file():
            raise RuntimeError("Qualification archive environment file is missing")

    source = manifest.get("source")
    if not isinstance(source, dict) or not isinstance(
        source.get("dirty_snapshot_complete"), bool
    ):
        raise RuntimeError("Qualification archive source record is invalid")
    if (
        publication.get("mode") == "publishable"
        and source["dirty_snapshot_complete"] is not True
    ):
        raise RuntimeError("Publishable archive source snapshot is incomplete")
    source_paths: dict[str, Path] = {}
    for key in (
        "git_archive",
        "git_status",
        "tracked_changes",
        "untracked_inventory",
    ):
        source_path = _contained_path(root, source.get(key), "source")
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
            filename_path = _safe_portable_path(
                filename, context="distribution filename"
            )
        except RuntimeError as error:
            raise RuntimeError(
                "Qualification archive distribution filename is invalid"
            ) from error
        if len(filename_path.parts) != 1:
            raise RuntimeError("Qualification archive distribution filename is invalid")
        distribution = _contained_path(
            root, f"distributions/{filename}", "distributions"
        )
        name, version, kind = _distribution_identity(distribution)
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


def verify_archive(  # noqa: C901 - rechecks container and scientific evidence
    path: Path, *, require_sidecar: bool = True
) -> dict[str, Any]:
    """Verify the ZIP sidecar, inventories, result manifests, and qualification."""
    path = Path(path).resolve()
    if not path.is_file():
        raise FileNotFoundError(path)
    sidecar = path.with_name(f"{path.name}.sha256")
    if require_sidecar:
        if not sidecar.is_file():
            raise FileNotFoundError(sidecar)
        parts = sidecar.read_text(encoding="ascii").strip().split("  ", maxsplit=1)
        if parts != [sha256(path), path.name]:
            raise RuntimeError("Qualification archive SHA-256 sidecar is invalid")

    with zipfile.ZipFile(path) as archive:
        names = _safe_member_names(archive)
        required = {ARCHIVE_MANIFEST, ARCHIVE_CHECKSUMS, ARCHIVE_README}
        if not required <= set(names):
            raise RuntimeError("Qualification archive control files are incomplete")
        if archive.testzip() is not None:
            raise RuntimeError("Qualification archive contains a corrupt ZIP member")
        manifest = json.loads(archive.read(ARCHIVE_MANIFEST).decode("utf-8"))
        if manifest.get("schema_version") != ARCHIVE_SCHEMA_VERSION:
            raise RuntimeError("Unsupported qualification archive schema")
        if manifest.get("archive_kind") != "pyages-multichain-qualification":
            raise RuntimeError("Qualification archive kind is invalid")
        _validate_publication_record(manifest)
        entries = _validated_archive_entries(manifest)
        expected_names = {item["path"] for item in entries} | {
            ARCHIVE_MANIFEST,
            ARCHIVE_CHECKSUMS,
        }
        if expected_names != set(names):
            raise RuntimeError("Qualification archive member inventory does not match")
        for item in entries:
            data = archive.read(item["path"])
            if len(data) != item["bytes"] or _sha256_bytes(data) != item["sha256"]:
                raise RuntimeError(
                    f"Qualification archive member changed: {item['path']}"
                )
        checksum_lines = archive.read(ARCHIVE_CHECKSUMS).decode("ascii").splitlines()
        checksums = dict(line.split("  ", maxsplit=1)[::-1] for line in checksum_lines)
        expected_checksums = {
            name: _sha256_bytes(archive.read(name))
            for name in names
            if name != ARCHIVE_CHECKSUMS
        }
        if checksums != expected_checksums:
            raise RuntimeError("Qualification archive CHECKSUMS.sha256 is invalid")

        with tempfile.TemporaryDirectory(prefix="pyages-qualification-verify-") as temp:
            extracted = Path(temp)
            archive.extractall(extracted)
            _validate_extracted_semantics(extracted, manifest)
    return manifest


def main(argv: list[str] | None = None) -> int:
    """Run the qualification archive builder or verifier."""
    parser = argparse.ArgumentParser(description=__doc__)
    subparsers = parser.add_subparsers(dest="command", required=True)
    build = subparsers.add_parser("build", help="build a qualification ZIP")
    build.add_argument("--result", type=Path, action="append", required=True)
    build.add_argument("--yaml", type=Path, action="append", required=True)
    build.add_argument("--test", type=Path, action="append", required=True)
    build.add_argument("--report", type=Path, action="append", required=True)
    build.add_argument("--distribution", type=Path, action="append", required=True)
    build.add_argument("--environment-file", type=Path, action="append", default=[])
    build.add_argument("--output", type=Path, required=True)
    build.add_argument("--mode", choices=("draft", "publishable"), required=True)
    build.add_argument("--expected-tag")
    verify = subparsers.add_parser("verify", help="verify a qualification ZIP")
    verify.add_argument("archive", type=Path)
    args = parser.parse_args(argv)
    if args.command == "verify":
        manifest = verify_archive(args.archive)
        print(
            f"Verified {len(manifest['results'])} qualified result tree(s): "
            f"{args.archive}"
        )
        return 0
    built = build_archive(
        results=args.result,
        yaml_files=args.yaml,
        test_files=args.test,
        reports=args.report,
        distributions=args.distribution,
        environment_files=args.environment_file,
        output=args.output,
        mode=args.mode,
        expected_tag=args.expected_tag,
    )
    print(f"Built {args.mode} multi-chain qualification archive: {built}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
