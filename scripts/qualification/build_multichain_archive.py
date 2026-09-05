# Copyright (c) 2021-2026 Centre national de la recherche scientifique (CNRS)
# Contributor: Jean-Raynald de Dreuzy
# SPDX-License-Identifier: CECILL-2.1

"""Build and verify self-contained multi-chain qualification archives.

This module is the stable command-line and orchestration façade. It validates
all supplied evidence before copying it, assembles a deterministic ZIP, records
the source and runtime environment, and independently verifies the completed
container. Detailed filesystem, result-evidence, and extracted-payload checks
live in private sibling modules so each security boundary can be read and
tested separately.
"""

from __future__ import annotations

import argparse
import json
import os
import platform
import shutil
import subprocess
import sys
import tempfile
import zipfile
from pathlib import Path
from typing import Any, Iterable, Literal

from pyages import __version__
from scripts.common.provenance import git_output
from scripts.common.provenance import sha256_bytes as _sha256_bytes
from scripts.qualification._archive_contract import (
    ARCHIVE_CHECKSUMS,
    ARCHIVE_MANIFEST,
    ARCHIVE_README,
    ARCHIVE_SCHEMA_VERSION,
    ZIP_TIMESTAMP,
    sha256,
)
from scripts.qualification._archive_contract import (
    is_link_or_junction as _is_link_or_junction,
)
from scripts.qualification._archive_contract import (
    regular_files as _regular_files,
)
from scripts.qualification._archive_contract import (
    safe_portable_path as _safe_portable_path,
)
from scripts.qualification._archive_evidence import (
    distribution_identity as _distribution_identity,
)
from scripts.qualification._archive_evidence import (
    validate_publishable_result_provenance as _validate_publishable_result_provenance,
)
from scripts.qualification._archive_evidence import (
    validate_result_tree as _validate_result_tree,
)
from scripts.qualification._archive_verification import (
    safe_member_names as _safe_member_names,
)
from scripts.qualification._archive_verification import (
    validate_extracted_semantics as _validate_extracted_semantics_impl,
)
from scripts.qualification._archive_verification import (
    validate_publication_record as _validate_publication_record,
)
from scripts.qualification._archive_verification import (
    validated_archive_entries as _validated_archive_entries,
)

ROOT = Path(__file__).resolve().parents[2]


def _validate_extracted_semantics(root: Path, manifest: dict[str, Any]) -> None:
    """Validate extracted evidence through the façade's replaceable validator."""
    _validate_extracted_semantics_impl(
        root,
        manifest,
        result_validator=_validate_result_tree,
    )


def _git_text(*args: str) -> str:
    return git_output(ROOT, *args).strip()


def _git_bytes(*args: str) -> bytes:
    return git_output(ROOT, *args, binary=True)


def _write_git_archive(destination: Path, head: str) -> None:
    subprocess.run(
        ["git", "archive", "--format=tar", "-o", str(destination), head],
        cwd=ROOT,
        check=True,
    )


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
