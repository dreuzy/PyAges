"""Build and validate the complete scientific archive for the article."""

from __future__ import annotations

import argparse
import hashlib
import json
import shutil
import subprocess
import sys
import tempfile
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

ROOT = Path(__file__).resolve().parents[1]
EXCLUDED_PARTS = {"work", "__pycache__", ".pytest_cache"}


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _git(*args: str) -> str:
    return subprocess.run(
        ["git", *args], cwd=ROOT, capture_output=True, text=True, check=True
    ).stdout.strip()


def _campaign_files(campaign: Path):
    for path in sorted(campaign.rglob("*")):
        relative = path.relative_to(campaign)
        if path.is_file() and not EXCLUDED_PARTS.intersection(relative.parts):
            yield path, relative


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


def build_archive(
    campaign: Path, output: Path, *, allow_dirty: bool = False
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
    if output.exists():
        raise FileExistsError(f"Refusing to replace existing archive: {output}")
    output.parent.mkdir(parents=True, exist_ok=True)
    staging = Path(tempfile.mkdtemp(prefix=f".{output.name}.staging-", dir=output.parent))
    try:
        campaign_copy = staging / "campaign"
        for source, relative in _campaign_files(campaign):
            destination = campaign_copy / relative
            destination.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(source, destination)

        source_dir = staging / "source"
        source_dir.mkdir(parents=True)
        head = _git("rev-parse", "HEAD")
        subprocess.run(
            ["git", "archive", "--format=zip", "-o", str(source_dir / "pyage-source.zip"), head],
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
            "git_dirty": bool(dirty),
            "campaign_source": str(campaign),
            "scope": "complete article evidence, retained MCMC states, derived products, code and environment",
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
    parser.add_argument("--campaign", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--allow-dirty", action="store_true")
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
    if args.reuse_valid and args.output.exists():
        payload = validate_archive(args.output)
        print(f"Reused valid archive with {len(payload['files'])} files: {args.output}")
        return 0
    built = build_archive(args.campaign, args.output, allow_dirty=args.allow_dirty)
    print(f"Built complete reproduction archive: {built}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
