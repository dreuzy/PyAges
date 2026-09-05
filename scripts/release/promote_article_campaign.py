# Copyright (c) 2021-2026 Centre national de la recherche scientifique (CNRS)
# Contributor: Jean-Raynald de Dreuzy
# SPDX-License-Identifier: CECILL-2.1

"""Promote retained article calculations by functional equivalence.

This command never runs simulations or rewrites historical run manifests. It
freezes the numerical evidence, verifies recorded artifact and source hashes,
and records the maintainer's non-functional-change decision.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import tempfile
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

from pyages import __version__
from scripts.common.provenance import git_output
from scripts.common.provenance import sha256_file as sha256

ROOT = Path(__file__).resolve().parents[2]
PROMOTION_NAME = "release_promotion.json"
NUMERICAL_STAGES = {
    "forward": Path("forward"),
    "tracerlpm": Path("tracerlpm"),
    "shifted_exponential": Path("shifted_exponential"),
    "holten_h4": Path("holten_h4"),
    "holten_prior": Path("holten_prior_dirichlet1"),
    "ploemeur_shifted": Path("ploemeur_shifted_exponential"),
    "ploemeur_ig": Path("ploemeur_physical_ig"),
}
SOURCE_MANIFESTS = {
    "shifted_exponential": Path("shifted_exponential/manifest.json"),
    "holten_h4": Path("holten_h4/manifest.json"),
    "holten_prior": Path("holten_prior_dirichlet1/manifest.json"),
    "ploemeur_shifted": Path("ploemeur_shifted_exponential/manifest.json"),
    "ploemeur_ig": Path("ploemeur_physical_ig/manifest.json"),
}
EXCLUDED_PARTS = {"work", "__pycache__", ".pytest_cache"}


def _git(*args: str) -> str:
    return git_output(ROOT, *args).strip()


def _files(root: Path):
    for path in sorted(root.rglob("*")):
        relative = path.relative_to(root)
        if path.is_file() and not EXCLUDED_PARTS.intersection(relative.parts):
            yield path, relative


def tree_fingerprint(root: Path) -> dict[str, object]:
    if not root.is_dir():
        raise FileNotFoundError(root)
    digest = hashlib.sha256()
    count = 0
    size = 0
    hashes: dict[str, list[str]] = {}
    for path, relative in _files(root):
        file_hash = sha256(path)
        file_size = path.stat().st_size
        label = relative.as_posix()
        digest.update(label.encode("utf-8"))
        digest.update(b"\0")
        digest.update(str(file_size).encode("ascii"))
        digest.update(b"\0")
        digest.update(file_hash.encode("ascii"))
        digest.update(b"\n")
        count += 1
        size += file_size
        hashes.setdefault(file_hash, []).append(label)
    return {
        "file_count": count,
        "bytes": size,
        "tree_sha256": digest.hexdigest(),
        "_hashes": hashes,
    }


def _source_origins(
    campaign: Path,
    stage: str,
    source_path: str,
    expected: str,
    stage_hashes: dict[str, dict[str, list[str]]],
) -> list[str]:
    origins = []
    relative = Path(source_path)
    current = ROOT / relative
    if current.is_file() and sha256(current) == expected:
        origins.append(f"release_tree:{relative.as_posix()}")

    snapshot_names = {
        "holten_prior": "holten_prior_dirichlet1",
        "ploemeur_shifted": "ploemeur_shifted_exponential",
    }
    snapshot = (
        campaign
        / "article_package/provenance/execution_source"
        / snapshot_names.get(stage, stage)
        / relative
    )
    if snapshot.is_file() and sha256(snapshot) == expected:
        origins.append(
            "article_package:"
            + snapshot.relative_to(campaign / "article_package").as_posix()
        )

    for numerical_stage, hashes in stage_hashes.items():
        for match in hashes.get(expected, []):
            location = NUMERICAL_STAGES[numerical_stage] / match
            origins.append(f"campaign:{location.as_posix()}")
    return origins


def _verify_source_manifests(
    campaign: Path, stage_trees: dict[str, dict[str, object]]
) -> dict[str, object]:
    result = {}
    stage_hashes = {stage: tree["_hashes"] for stage, tree in stage_trees.items()}
    for stage, relative_manifest in SOURCE_MANIFESTS.items():
        manifest_path = campaign / relative_manifest
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        stage_root = manifest_path.parent
        artifact_failures = []
        for raw_relative, expected in manifest.get("artifact_sha256", {}).items():
            artifact = stage_root / raw_relative
            if not artifact.is_file():
                artifact_failures.append(f"missing:{raw_relative}")
            elif sha256(artifact) != expected.lower():
                artifact_failures.append(f"hash:{raw_relative}")

        sources = {}
        for raw_relative, expected in manifest.get("source_sha256", {}).items():
            origins = _source_origins(
                campaign,
                stage,
                raw_relative,
                expected.lower(),
                stage_hashes,
            )
            sources[raw_relative] = {
                "sha256": expected.lower(),
                "exact_origins": origins,
            }
        missing_sources = [
            path for path, item in sources.items() if not item["exact_origins"]
        ]
        if artifact_failures or missing_sources:
            details = artifact_failures + [f"source:{path}" for path in missing_sources]
            raise RuntimeError(
                f"Invalid retained evidence for {stage}: {', '.join(details)}"
            )
        result[stage] = {
            "manifest": relative_manifest.as_posix(),
            "manifest_sha256": sha256(manifest_path),
            "recorded_git_head": manifest.get("git_head"),
            "artifact_count": len(manifest.get("artifact_sha256", {})),
            "all_artifacts_match": True,
            "source_count": len(sources),
            "all_sources_preserved": True,
            "sources": sources,
        }
    return result


def _public_tree(tree: dict[str, object]) -> dict[str, object]:
    return {key: value for key, value in tree.items() if not key.startswith("_")}


def build_promotion(
    campaign: Path,
    *,
    expected_tag: str,
    attestation: str,
    attestation_source: str,
) -> dict[str, object]:
    campaign = campaign.resolve()
    manifest_path = campaign / "campaign_manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    records = manifest.get("stages", {})
    failures = [
        name
        for name in NUMERICAL_STAGES
        if records.get(name, {}).get("status") != "success"
    ]
    if failures:
        raise RuntimeError(f"Numerical stages are not successful: {failures}")

    dirty = _git("status", "--short")
    if dirty:
        raise RuntimeError("Refusing to promote from a dirty Git worktree")
    head = _git("rev-parse", "HEAD")
    tags = [tag for tag in _git("tag", "--points-at", "HEAD").splitlines() if tag]

    stage_trees = {
        stage: tree_fingerprint(campaign / relative)
        for stage, relative in NUMERICAL_STAGES.items()
    }
    source_audit = _verify_source_manifests(campaign, stage_trees)
    historical_stages = {}
    for stage in NUMERICAL_STAGES:
        record = records[stage]
        historical_stages[stage] = {
            "status": record.get("status"),
            "git_head": record.get("git_head"),
            "git_tags_at_head": record.get("git_tags_at_head", []),
            "command": record.get("command", []),
            "expected": record.get("expected", []),
        }

    return {
        "schema_version": 1,
        "promotion_kind": "maintainer-functional-equivalence",
        "created_at": datetime.now(ZoneInfo("Europe/Paris")).isoformat(),
        "release_identity": {
            "git_head": head,
            "git_tags_at_head": tags,
            "expected_release_tag": expected_tag,
            "pyages_version": __version__,
        },
        "maintainer_attestation": {
            "accepted": True,
            "text": attestation,
            "source": attestation_source,
        },
        "policy": {
            "historical_manifests_preserved": True,
            "numerical_recalculation_performed": False,
            "claim": (
                "Retained numerical outputs are promoted to the release after "
                "maintainer review established that intervening changes are "
                "non-functional for the published calculations."
            ),
        },
        "campaign_manifest": {
            "path": "campaign_manifest.json",
            "sha256": sha256(manifest_path),
        },
        "historical_execution": {
            "commits": sorted(
                {
                    item["git_head"]
                    for item in historical_stages.values()
                    if item["git_head"]
                }
            ),
            "stages": historical_stages,
        },
        "numerical_evidence": {
            stage: {
                "path": relative.as_posix(),
                **_public_tree(stage_trees[stage]),
            }
            for stage, relative in NUMERICAL_STAGES.items()
        },
        "source_and_artifact_audit": source_audit,
        "limitations": [
            "Forward and TracerLPM manifests lack per-source SHA-256 maps.",
            (
                "Their promotion relies on retained inputs/results plus the "
                "explicit maintainer functional-equivalence attestation."
            ),
            (
                "This document records equivalence; it does not rewrite where "
                "or when calculations ran."
            ),
        ],
    }


def write_promotion(path: Path, payload: dict[str, object]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile(
        mode="w", encoding="utf-8", dir=path.parent, delete=False, suffix=".tmp"
    ) as stream:
        json.dump(payload, stream, ensure_ascii=False, indent=2)
        stream.write("\n")
        temporary = Path(stream.name)
    temporary.replace(path)


def _validate_evidence(campaign: Path, payload: dict[str, object]) -> list[str]:
    failures = []
    manifest = campaign / payload["campaign_manifest"]["path"]
    if sha256(manifest) != payload["campaign_manifest"]["sha256"]:
        failures.append("campaign_manifest_sha256")
    for stage, recorded in payload["numerical_evidence"].items():
        observed = _public_tree(tree_fingerprint(campaign / recorded["path"]))
        for field in ("file_count", "bytes", "tree_sha256"):
            if observed[field] != recorded[field]:
                failures.append(f"{stage}:{field}")
    return failures


def _validate_release_identity(
    payload: dict[str, object],
    expected_head: str | None,
    expected_tag: str | None,
) -> list[str]:
    failures = []
    release = payload["release_identity"]
    if expected_head is not None and release.get("git_head") != expected_head:
        failures.append("release_git_head")
    if expected_tag is None:
        return failures
    if release.get("expected_release_tag") != expected_tag:
        failures.append("expected_release_tag")
    if expected_tag not in release.get("git_tags_at_head", []):
        failures.append("recorded_release_tag_not_at_head")
    tags = [tag for tag in _git("tag", "--points-at", "HEAD").splitlines() if tag]
    if expected_tag not in tags:
        failures.append("release_tag_not_at_head")
    elif _git("cat-file", "-t", f"refs/tags/{expected_tag}") != "tag":
        failures.append("release_tag_not_annotated")
    return failures


def validate_promotion(
    campaign: Path,
    promotion_path: Path | None = None,
    *,
    expected_head: str | None = None,
    expected_tag: str | None = None,
) -> dict[str, object]:
    campaign = campaign.resolve()
    path = promotion_path or campaign / PROMOTION_NAME
    payload = json.loads(path.read_text(encoding="utf-8"))
    failures = []
    if payload.get("promotion_kind") != "maintainer-functional-equivalence":
        failures.append("promotion_kind")
    if not payload.get("maintainer_attestation", {}).get("accepted"):
        failures.append("maintainer_attestation")
    policy = payload.get("policy", {})
    if policy.get("numerical_recalculation_performed") is not False:
        failures.append("numerical_recalculation_performed")
    failures.extend(_validate_evidence(campaign, payload))
    failures.extend(_validate_release_identity(payload, expected_head, expected_tag))
    if failures:
        raise RuntimeError("Invalid campaign promotion: " + ", ".join(failures))
    return payload


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=("create", "validate"))
    parser.add_argument("--campaign", type=Path, required=True)
    parser.add_argument("--expected-tag", default="1.0")
    parser.add_argument("--attestation")
    parser.add_argument(
        "--attestation-source",
        default="explicit project-maintainer directive recorded during release audit",
    )
    parser.add_argument("--require-release-identity", action="store_true")
    args = parser.parse_args(argv)
    path = args.campaign.resolve() / PROMOTION_NAME
    if args.action == "create":
        if not args.attestation:
            parser.error("--attestation is required for create")
        payload = build_promotion(
            args.campaign,
            expected_tag=args.expected_tag,
            attestation=args.attestation,
            attestation_source=args.attestation_source,
        )
        write_promotion(path, payload)
        print(f"Created non-recalculation promotion: {path}")
        return 0
    head = _git("rev-parse", "HEAD") if args.require_release_identity else None
    tag = args.expected_tag if args.require_release_identity else None
    payload = validate_promotion(
        args.campaign, path, expected_head=head, expected_tag=tag
    )
    print(
        "Validated promoted numerical evidence for "
        f"{len(payload['numerical_evidence'])} stages"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
