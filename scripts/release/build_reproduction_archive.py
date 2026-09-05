# Copyright (c) 2021-2026 Centre national de la recherche scientifique (CNRS)
# Contributor: Jean-Raynald de Dreuzy
# SPDX-License-Identifier: CECILL-2.1

"""Build and validate the complete article reproduction archive."""

from __future__ import annotations

import argparse
import json
import shutil
import subprocess
import sys
import tempfile
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

from pyages import __version__
from scripts.common.provenance import git_output
from scripts.common.provenance import sha256_file as sha256

ROOT = Path(__file__).resolve().parents[2]
RELEASE_TAG = "1.0"
EXCLUDED_PARTS = {"work", "__pycache__", ".pytest_cache"}


def _git(*args: str) -> str:
    return git_output(ROOT, *args).strip()


def _campaign_files(campaign: Path):
    for path in sorted(campaign.rglob("*")):
        relative = path.relative_to(campaign)
        if path.is_file() and not EXCLUDED_PARTS.intersection(relative.parts):
            yield path, relative


def _release_tags(expected_tag: str, allow_untagged: bool) -> list[str]:
    tags = [tag for tag in _git("tag", "--points-at", "HEAD").splitlines() if tag]
    if expected_tag not in tags and not allow_untagged:
        raise RuntimeError(
            f"Refusing to archive HEAD without release tag {expected_tag!r}"
        )
    if (
        expected_tag in tags
        and _git("cat-file", "-t", f"refs/tags/{expected_tag}") != "tag"
    ):
        raise RuntimeError(
            f"Refusing to archive lightweight release tag {expected_tag!r}"
        )
    return tags


def validate_archive(output: Path) -> dict[str, object]:
    manifest_path = output.resolve() / "ARCHIVE_MANIFEST.json"
    payload = json.loads(manifest_path.read_text(encoding="utf-8"))
    failures = []
    for item in payload["files"]:
        path = output / item["path"]
        if not path.is_file():
            failures.append(f"missing: {item['path']}")
        elif path.stat().st_size != item["bytes"]:
            failures.append(f"size: {item['path']}")
        elif sha256(path) != item["sha256"]:
            failures.append(f"hash: {item['path']}")
    if failures:
        raise RuntimeError("Invalid reproduction archive: " + ", ".join(failures))
    return payload


def _campaign_promotion(
    campaign: Path, head: str, expected_tag: str
) -> dict[str, object] | None:
    campaign_manifest = json.loads(
        (campaign / "campaign_manifest.json").read_text(encoding="utf-8")
    )
    numerical_names = {
        "forward",
        "tracerlpm",
        "shifted_exponential",
        "holten_h4",
        "holten_prior",
        "ploemeur_shifted",
        "ploemeur_ig",
    }
    numerical_heads = {
        record.get("git_head")
        for name, record in campaign_manifest.get("stages", {}).items()
        if name in numerical_names and record.get("git_head")
    }
    if numerical_heads == {head}:
        return None

    from scripts.release import promote_article_campaign

    promotion_path = campaign / promote_article_campaign.PROMOTION_NAME
    if not promotion_path.is_file():
        raise RuntimeError(
            "Campaign numerical stages do not share the release commit; "
            "a validated release_promotion.json is required"
        )
    return promote_article_campaign.validate_promotion(
        campaign,
        promotion_path,
        expected_head=head,
        expected_tag=expected_tag,
    )


def reuse_archive(
    campaign: Path,
    output: Path,
    *,
    expected_tag: str,
) -> dict[str, object]:
    dirty = _git("status", "--short")
    if dirty:
        raise RuntimeError("Refusing to reuse an archive from a dirty Git worktree")
    tags = _release_tags(expected_tag, allow_untagged=False)
    head = _git("rev-parse", "HEAD")
    promotion = _campaign_promotion(campaign.resolve(), head, expected_tag)
    payload = validate_archive(output)
    if payload.get("git_head") != head:
        raise RuntimeError("Existing archive Git commit does not match HEAD")
    if payload.get("git_tags_at_head") != tags:
        raise RuntimeError("Existing archive Git tags do not match HEAD")
    expected_mode = (
        "maintainer-functional-equivalence"
        if promotion is not None
        else "single-release-commit"
    )
    if payload.get("numerical_provenance_mode") != expected_mode:
        raise RuntimeError("Existing archive numerical provenance mode is stale")
    return payload


def build_archive(
    campaign: Path,
    output: Path,
    *,
    allow_dirty: bool = False,
    expected_tag: str = RELEASE_TAG,
    allow_untagged: bool = False,
) -> Path:
    campaign = campaign.resolve()
    output = output.resolve()
    if not (campaign / "campaign_manifest.json").is_file():
        raise FileNotFoundError(campaign / "campaign_manifest.json")
    if output == campaign or campaign in output.parents or output in campaign.parents:
        raise ValueError("Archive output and campaign must be separate directories")
    dirty = _git("status", "--short")
    if dirty and not allow_dirty:
        raise RuntimeError("Refusing to archive a dirty Git worktree")
    tags = _release_tags(expected_tag, allow_untagged)
    head = _git("rev-parse", "HEAD")
    promotion = _campaign_promotion(campaign, head, expected_tag)
    if output.exists():
        raise FileExistsError(f"Refusing to replace existing archive: {output}")
    output.parent.mkdir(parents=True, exist_ok=True)
    staging = Path(
        tempfile.mkdtemp(prefix=f".{output.name}.staging-", dir=output.parent)
    )
    try:
        campaign_copy = staging / "campaign"
        for source, relative in _campaign_files(campaign):
            destination = campaign_copy / relative
            destination.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(source, destination)

        source_dir = staging / "source"
        source_dir.mkdir(parents=True)
        subprocess.run(
            [
                "git",
                "archive",
                "--format=zip",
                "-o",
                str(source_dir / "pyages-source.zip"),
                head,
            ],
            cwd=ROOT,
            check=True,
        )
        freeze = subprocess.run(
            [sys.executable, "-m", "pip", "freeze"],
            cwd=ROOT,
            capture_output=True,
            text=True,
            check=True,
        ).stdout
        (source_dir / "environment-pip-freeze.txt").write_text(
            freeze, encoding="utf-8", newline="\n"
        )

        entries = []
        for path in sorted(staging.rglob("*")):
            if path.is_file():
                entries.append(
                    {
                        "path": path.relative_to(staging).as_posix(),
                        "bytes": path.stat().st_size,
                        "sha256": sha256(path),
                    }
                )
        manifest = {
            "schema_version": 1,
            "created_at": datetime.now(ZoneInfo("Europe/Paris")).isoformat(),
            "git_head": head,
            "git_tags_at_head": tags,
            "git_dirty": bool(dirty),
            "release_tag": expected_tag,
            "pyages_version": __version__,
            "campaign_source": str(campaign),
            "numerical_provenance_mode": (
                "maintainer-functional-equivalence"
                if promotion is not None
                else "single-release-commit"
            ),
            "release_promotion": (
                {
                    "path": "campaign/release_promotion.json",
                    "sha256": sha256(campaign / "release_promotion.json"),
                    "historical_commits": promotion["historical_execution"]["commits"],
                }
                if promotion is not None
                else None
            ),
            "scope": (
                "complete article campaign evidence, retained MCMC states, derived "
                "products, code and environment; includes the distinct Holten "
                "Dirichlet(1,1,1,1) prior-sensitivity campaign"
            ),
            "files": entries,
        }
        (staging / "ARCHIVE_MANIFEST.json").write_text(
            json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
        )
        (staging / "CHECKSUMS.sha256").write_text(
            "\n".join(f"{item['sha256']}  {item['path']}" for item in entries) + "\n",
            encoding="ascii",
            newline="\n",
        )
        staging.rename(output)
        validate_archive(output)
    except Exception:
        shutil.rmtree(staging, ignore_errors=True)
        raise
    return output


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--campaign", type=Path)
    parser.add_argument("--output", type=Path)
    parser.add_argument("--allow-dirty", action="store_true")
    parser.add_argument("--expected-tag", default=RELEASE_TAG)
    parser.add_argument("--allow-untagged", action="store_true")
    parser.add_argument(
        "--reuse-valid",
        action="store_true",
        help="accept an existing archive only after full hash validation",
    )
    parser.add_argument("--validate-only", type=Path)
    args = parser.parse_args(argv)
    if args.validate_only is not None:
        payload = validate_archive(args.validate_only)
        print(f"Validated {len(payload['files'])} archived files")
        return 0
    if args.campaign is None or args.output is None:
        parser.error(
            "--campaign and --output are required unless --validate-only is used"
        )
    if args.reuse_valid and args.output.exists():
        payload = reuse_archive(
            args.campaign,
            args.output,
            expected_tag=args.expected_tag,
        )
        if payload.get("release_tag") != args.expected_tag:
            raise RuntimeError(
                "Existing archive release tag does not match the requested tag: "
                f"{payload.get('release_tag')!r} != {args.expected_tag!r}"
            )
        if payload.get("pyages_version") != __version__:
            raise RuntimeError(
                "Existing archive PyAges version does not match the source tree: "
                f"{payload.get('pyages_version')!r} != {__version__!r}"
            )
        print(f"Reused valid archive with {len(payload['files'])} files: {args.output}")
        return 0
    built = build_archive(
        args.campaign,
        args.output,
        allow_dirty=args.allow_dirty,
        expected_tag=args.expected_tag,
        allow_untagged=args.allow_untagged,
    )
    print(f"Built complete reproduction archive: {built}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
