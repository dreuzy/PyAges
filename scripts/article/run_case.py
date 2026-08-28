# Copyright (c) 2021-2026 Centre national de la recherche scientifique (CNRS)
# Contributor: Jean-Raynald de Dreuzy
# SPDX-License-Identifier: CECILL-2.1

"""Command-line entry point for cases supporting the PyAges 1.0 article.

This module deliberately keeps checking, post-processing, and simulation as
three separate operations. In particular, ``check`` audits the optional
historical evidence inventory and never imports a scientific runner. It is not
the gate for a fresh campaign; use ``scripts.article.reproduce_article validate`` for
that. ``postprocess`` only calls the guarded article wrapper.

The label ``v1.0`` names the manuscript target, not the currently released
package version. Each case manifest remains authoritative for its source
commit, environment, and requested release tag.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
import sys
from pathlib import Path
from typing import Any

import yaml

ROOT = Path(__file__).resolve().parents[2]
ARTICLE = ROOT / "article"
REGISTRY = ARTICLE / "cases.yaml"


def _load_registry() -> dict[str, dict[str, Any]]:
    payload = yaml.safe_load(REGISTRY.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError(f"Invalid case registry: {REGISTRY}")
    return payload


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _repo_path(raw: str) -> Path:
    path = Path(raw.replace("\\", "/"))
    if path.is_absolute() or ".." in path.parts:
        raise ValueError(f"Unsafe repository-relative path: {raw}")
    return ROOT / path


def _check_resources(
    manifest: dict[str, Any], historical_paths: set[str] | None = None
) -> list[str]:
    errors: list[str] = []
    for raw in manifest.get("required_paths", []):
        if not _repo_path(raw).exists():
            errors.append(f"missing: {raw}")
    indexed = (
        list(manifest.get("inputs", []))
        + list(manifest.get("scripts", []))
        + list(manifest.get("resources", []))
    )
    seen: set[str] = set()
    for item in indexed:
        normalized = item["path"].replace("\\", "/")
        if historical_paths and normalized in historical_paths:
            continue
        if item["path"] in seen:
            continue
        seen.add(item["path"])
        path = _repo_path(item["path"])
        if not path.is_file():
            errors.append(f"missing: {item['path']}")
        elif item.get("sha256") and _sha256(path).lower() != item["sha256"].lower():
            errors.append(f"checksum mismatch: {item['path']}")
    return errors


def _check_historical_json(path: Path) -> tuple[list[str], int]:
    errors: list[str] = []
    payload = json.loads(path.read_text(encoding="utf-8"))
    checked = 0
    for group in ("input_sha256", "source_sha256", "artifact_sha256"):
        for raw, expected in payload.get(group, {}).items():
            target = _repo_path(raw)
            checked += 1
            if not target.is_file():
                errors.append(f"missing ({group}): {raw}")
            elif _sha256(target).lower() != str(expected).lower():
                errors.append(f"checksum mismatch ({group}): {raw}")
    return errors, checked


def _check_manifest(case: dict[str, Any]) -> tuple[list[str], list[str]]:
    errors: list[str] = []
    notes: list[str] = []
    manifest_path = _repo_path(case["manifest"])
    if not manifest_path.is_file():
        return [f"missing article manifest: {case['manifest']}"], notes
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    historical = manifest.get("historical_manifest")
    historical_paths: set[str] = set()
    if historical:
        historical_path = _repo_path(historical)
        if historical_path.is_file() and historical_path.suffix.lower() == ".json":
            payload = json.loads(historical_path.read_text(encoding="utf-8"))
            for group in ("input_sha256", "source_sha256", "artifact_sha256"):
                historical_paths.update(
                    raw.replace("\\", "/") for raw in payload.get(group, {})
                )
    errors.extend(_check_resources(manifest, historical_paths))

    if historical:
        path = _repo_path(historical)
        if not path.is_file():
            errors.append(f"missing historical manifest: {historical}")
        elif path.suffix.lower() == ".json":
            historical_errors, checked = _check_historical_json(path)
            errors.extend(historical_errors)
            notes.append(f"{checked} historical checksums inspected")
        else:
            notes.append(
                "historical YAML manifest present; indexed resource hashes inspected"
            )
    return errors, notes


def _command(case: dict[str, Any], action: str) -> int:
    raw = case.get("commands", {}).get(action)
    if not raw:
        print(
            f"No {action} command is registered for {case['case_id']}.", file=sys.stderr
        )
        return 2
    command = list(raw)
    if command[0] == "python":
        command[0] = sys.executable
    print("Executing:", subprocess.list2cmdline(command), flush=True)
    return subprocess.run(command, cwd=ROOT, check=False).returncode


def main(argv: list[str] | None = None) -> int:
    registry = _load_registry()
    parser = argparse.ArgumentParser(description=__doc__)
    subparsers = parser.add_subparsers(dest="action", required=True)
    subparsers.add_parser("list", help="list manuscript cases")
    for action in ("check", "postprocess", "run"):
        help_text = (
            "audit optional historical evidence"
            if action == "check"
            else f"{action} one manuscript case"
        )
        child = subparsers.add_parser(action, help=help_text)
        child.add_argument("case_id", choices=tuple(registry))
    args = parser.parse_args(argv)

    if args.action == "list":
        print(
            "Case                                      Manuscript               "
            "Historical status  Main output"
        )
        for case_id, case in registry.items():
            outputs = case.get("figures", []) + case.get("tables", [])
            print(
                f"{case_id:<41} {str(case['manuscript_section']):<24} "
                f"{case['status']:<18} {', '.join(outputs) or '-'}"
            )
        return 0

    case = registry[args.case_id]
    if args.action == "check":
        print(
            "NOTE  legacy evidence audit only; fresh campaigns are validated "
            "with `python -m scripts.article.reproduce_article validate --output ...`"
        )
        errors, notes = _check_manifest(case)
        for note in notes:
            print(f"NOTE  {note}")
        if errors:
            for error in errors:
                print(f"FAIL  {error}")
            print(
                f"{case['case_id']}: HISTORICAL EVIDENCE UNAVAILABLE "
                f"({len(errors)} issue(s))"
            )
            return 1
        print(f"{case['case_id']}: HISTORICAL EVIDENCE OK")
        return 0
    if args.action == "run":
        print(
            f"WARNING: full calculation; expected runtime: {case['expected_runtime']}"
        )
    return _command(case, args.action)


if __name__ == "__main__":
    raise SystemExit(main())
