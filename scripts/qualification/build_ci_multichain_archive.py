# Copyright (c) 2021-2026 Centre national de la recherche scientifique (CNRS)
# Contributor: Jean-Raynald de Dreuzy
# SPDX-License-Identifier: CECILL-2.1

"""Build the canonical four-case multi-chain qualification archive.

The generic archive builder accepts arbitrary qualified result trees. This
adapter is stricter: it discovers exactly the registered synthetic,
single-date, prior-active, and temporal results produced by one extensive
pytest run, matches each result to its executed YAML digest, and then delegates
the deterministic archive assembly. It never changes scientific outputs.
"""

from __future__ import annotations

import argparse
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterable, Literal

from scripts.qualification import build_multichain_archive

ROOT = Path(__file__).resolve().parents[2]


@dataclass(frozen=True)
class QualificationCase:
    """Canonical protocol files for one extensive multi-chain qualification."""

    key: str
    executed_yaml_name: str
    test: Path
    report: Path


@dataclass(frozen=True)
class DiscoveredQualification:
    """Exactly matched result and executed YAML for one canonical case."""

    case: QualificationCase
    result: Path
    executed_yaml: Path
    configuration_sha256: str


CASES = (
    QualificationCase(
        key="synthetic",
        executed_yaml_name="synthetic_multichain_scientific.yaml",
        test=ROOT / "tests/examples/test_synthetic_recovery_multichain_scientific.py",
        report=ROOT / "docs/examples/synthetic-recovery.md",
    ),
    QualificationCase(
        key="ploemeur_f09",
        executed_yaml_name="ploemeur_f09_multichain_scientific.yaml",
        test=ROOT / "tests/examples/test_ploemeur_multichain_scientific.py",
        report=ROOT / "docs/examples/ploemeur-multichain.md",
    ),
    QualificationCase(
        key="ploemeur_ig_shifted_prior",
        executed_yaml_name="ploemeur_ig_shifted_prior_multichain.yaml",
        test=(
            ROOT
            / "tests/examples/test_ploemeur_ig_shifted_prior_multichain_scientific.py"
        ),
        report=ROOT / "docs/examples/ploemeur-ig-shifted-prior-multichain.md",
    ),
    QualificationCase(
        key="ploemeur_temporal",
        executed_yaml_name="ploemeur_temporal_multichain_scientific.yaml",
        test=(ROOT / "tests/examples/test_ploemeur_temporal_multichain_scientific.py"),
        report=ROOT / "docs/examples/ploemeur-temporal-multichain.md",
    ),
)


def _unique_resolved_files(root: Path, filename: str) -> tuple[Path, ...]:
    found: dict[Path, Path] = {}
    for candidate in root.rglob(filename):
        if candidate.is_file():
            resolved = candidate.resolve()
            found.setdefault(resolved, candidate)
    return tuple(sorted(found, key=lambda path: path.as_posix()))


def _configuration_digest(manifest_path: Path) -> str | None:
    try:
        payload = json.loads(manifest_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None
    configuration = payload.get("configuration") if isinstance(payload, dict) else None
    digest = configuration.get("sha256") if isinstance(configuration, dict) else None
    return digest if isinstance(digest, str) else None


def _canonical_protocol_files() -> tuple[tuple[Path, ...], tuple[Path, ...]]:
    tests = tuple(case.test.resolve() for case in CASES)
    reports = tuple(case.report.resolve() for case in CASES)
    missing = [path for path in (*tests, *reports) if not path.is_file()]
    if missing:
        raise FileNotFoundError(
            f"Canonical qualification protocol files missing: {missing}"
        )
    return tests, reports


def _pytest_owner(basetemp: Path, path: Path) -> str | None:
    """Return the top-level pytest temporary directory containing one file."""
    try:
        relative = path.resolve().relative_to(basetemp.resolve())
    except ValueError:
        return None
    return relative.parts[0] if len(relative.parts) >= 2 else None


def discover_qualifications(  # noqa: C901 - strict four-way discovery is deliberate
    basetemp: Path,
) -> tuple[DiscoveredQualification, ...]:
    """Return exactly the four qualified results matched to executed YAML hashes."""
    basetemp = Path(basetemp).resolve()
    if not basetemp.is_dir():
        raise NotADirectoryError(basetemp)

    yaml_candidates: dict[QualificationCase, list[tuple[Path, str, str | None]]] = {}
    for case in CASES:
        candidates = _unique_resolved_files(basetemp, case.executed_yaml_name)
        yaml_candidates[case] = [
            (
                candidate,
                build_multichain_archive.sha256(candidate),
                _pytest_owner(basetemp, candidate),
            )
            for candidate in candidates
        ]
    canonical_owners = {
        owner
        for candidates in yaml_candidates.values()
        for _path, _digest, owner in candidates
        if owner is not None
    }

    qualified_by_case: dict[
        QualificationCase, list[tuple[Path, Path, dict[str, Any]]]
    ] = {}
    unexpected_qualified: list[Path] = []
    manifests = _unique_resolved_files(basetemp, "result_manifest.json")
    for manifest_path in manifests:
        digest = _configuration_digest(manifest_path)
        try:
            summary = build_multichain_archive._validate_result_tree(
                manifest_path.parent
            )
        except (FileNotFoundError, NotADirectoryError, RuntimeError, ValueError):
            continue
        owner = _pytest_owner(basetemp, manifest_path)
        paired = [
            (case, executed_yaml)
            for case, candidates in yaml_candidates.items()
            for executed_yaml, yaml_digest, yaml_owner in candidates
            if yaml_digest == digest and yaml_owner == owner and owner is not None
        ]
        if not paired:
            if owner in canonical_owners:
                unexpected_qualified.append(manifest_path.parent)
            continue
        if len(paired) != 1:
            case_names = sorted({case.key for case, _path in paired})
            raise RuntimeError(
                "Expected exactly one executed YAML beside a qualified result, "
                f"found {len(paired)} for {case_names}"
            )
        case, executed_yaml = paired[0]
        qualified_by_case.setdefault(case, []).append(
            (manifest_path.parent.resolve(), executed_yaml, summary)
        )

    if unexpected_qualified:
        raise RuntimeError(
            "Unexpected qualified result manifests below pytest basetemp: "
            f"{unexpected_qualified}"
        )
    discovered: list[DiscoveredQualification] = []
    for case in CASES:
        matches = qualified_by_case.get(case, [])
        if len(matches) != 1:
            raise RuntimeError(
                f"Expected exactly one qualified result for {case.key}, "
                f"found {len(matches)}"
            )
        result, executed_yaml, summary = matches[0]
        digest = build_multichain_archive.sha256(executed_yaml)
        if summary["configuration_sha256"] != digest:
            raise RuntimeError(f"Qualified result summary SHA mismatch for {case.key}")
        discovered.append(
            DiscoveredQualification(
                case=case,
                result=result,
                executed_yaml=executed_yaml,
                configuration_sha256=digest,
            )
        )
    if len({item.configuration_sha256 for item in discovered}) != len(CASES):
        raise RuntimeError("Canonical executed YAML files have duplicate SHA-256")
    return tuple(discovered)


def _distribution_files(directory: Path) -> tuple[Path, Path]:
    directory = Path(directory).resolve()
    if not directory.is_dir():
        raise NotADirectoryError(directory)
    wheel = tuple(sorted(directory.glob("*.whl")))
    sdists = tuple(
        sorted(
            path
            for path in directory.iterdir()
            if path.is_file()
            and path.name.endswith((".tar.gz", ".tar.bz2", ".tar.xz", ".zip"))
        )
    )
    if len(wheel) != 1 or len(sdists) != 1:
        raise RuntimeError(
            "Distribution directory must contain exactly one wheel and one sdist"
        )
    return wheel[0], sdists[0]


def build_ci_archive(
    *,
    basetemp: Path,
    dist_dir: Path,
    output: Path,
    mode: Literal["draft", "publishable"] = "draft",
    expected_tag: str | None = None,
) -> Path:
    """Discover exactly four cases and delegate deterministic archive assembly."""
    if mode == "publishable" and expected_tag is None:
        raise ValueError("Publishable canonical archive requires --expected-tag")
    discovered = discover_qualifications(basetemp)
    tests, reports = _canonical_protocol_files()
    distributions = _distribution_files(dist_dir)
    return build_multichain_archive.build_archive(
        results=[item.result for item in discovered],
        yaml_files=[item.executed_yaml for item in discovered],
        test_files=tests,
        reports=reports,
        distributions=distributions,
        output=output,
        mode=mode,
        expected_tag=expected_tag,
    )


def main(argv: Iterable[str] | None = None) -> int:
    """Build a canonical archive from one extensive-test base directory."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--basetemp", type=Path, required=True)
    parser.add_argument("--dist-dir", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--mode", choices=("draft", "publishable"), default="draft")
    parser.add_argument("--expected-tag")
    args = parser.parse_args(argv)
    output = build_ci_archive(
        basetemp=args.basetemp,
        dist_dir=args.dist_dir,
        output=args.output,
        mode=args.mode,
        expected_tag=args.expected_tag,
    )
    print(f"Built canonical {args.mode} multi-chain qualification archive: {output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
