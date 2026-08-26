"""Run, resume, validate, and archive the complete stabilized article campaign."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import platform
import shutil
import subprocess
import sys
import tempfile
import time
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

import yaml

ROOT = Path(__file__).resolve().parents[1]
ALL_STAGES = (
    "forward",
    "tracerlpm",
    "shifted_exponential",
    "holten_h4",
    "ploemeur_shifted",
    "ploemeur_ig",
    "package",
    "archive",
)


@dataclass(frozen=True)
class Stage:
    name: str
    command: tuple[str, ...]
    expected: tuple[Path, ...]


def _now() -> str:
    return datetime.now(ZoneInfo("Europe/Paris")).isoformat()


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _git(*args: str) -> str:
    return subprocess.run(
        ["git", *args], cwd=ROOT, capture_output=True, text=True, check=True
    ).stdout.strip()


def _outside_repository(path: Path) -> bool:
    try:
        path.resolve().relative_to(ROOT.resolve())
    except ValueError:
        return True
    return False


def _stage_map(output: Path, workers: int, tracer_config: Path, allow_dirty: bool):
    python = sys.executable
    archive = output.with_name(f"{output.name}-gmd-archive")
    shifted_summary = (
        output / "ploemeur_shifted_exponential/ploemeur_shiftedexp_final_summary.csv"
    )
    dirty_flag = ("--allow-dirty",) if allow_dirty else ()
    return {
        "forward": Stage(
            "forward",
            (
                python,
                "-m",
                "validation.tracerlpm.benchmark.scripts.compare_pyage",
                "--output",
                str(output / "forward"),
            ),
            (output / "forward/summary.json", output / "forward/case_results.csv"),
        ),
        "tracerlpm": Stage(
            "tracerlpm",
            (
                python,
                "-m",
                "scripts.run_tracerlpm_article_campaign",
                "--output",
                str(output / "tracerlpm"),
                "--config",
                str(tracer_config),
                "--workers",
                str(workers),
            ),
            (
                output / "tracerlpm/benchmark/generated/robustness-study/summary.json",
                output / "tracerlpm/manifest.json",
            ),
        ),
        "shifted_exponential": Stage(
            "shifted_exponential",
            (
                python,
                "-m",
                "scripts.run_final_shifted_exponential",
                "all",
                "--output",
                str(output / "shifted_exponential"),
                "--workers",
                str(workers),
            ),
            (output / "shifted_exponential/manifest.json",),
        ),
        "holten_h4": Stage(
            "holten_h4",
            (
                python,
                "-m",
                "scripts.run_final_holten_h4",
                "all",
                "--output",
                str(output / "holten_h4"),
            ),
            (output / "holten_h4/manifest.json",),
        ),
        "ploemeur_shifted": Stage(
            "ploemeur_shifted",
            (
                python,
                "-m",
                "scripts.run_ploemeur_shifted_exponential_final",
                "all",
                "--output",
                str(output / "ploemeur_shifted_exponential"),
                "--workers",
                str(workers),
            ),
            (output / "ploemeur_shifted_exponential/manifest.json", shifted_summary),
        ),
        "ploemeur_ig": Stage(
            "ploemeur_ig",
            (
                python,
                "-m",
                "scripts.run_ploemeur_targeted_ig_reproduction",
                "--stage",
                "resume",
                "--output",
                str(output / "ploemeur_physical_ig"),
                "--shifted-summary",
                str(shifted_summary),
            ),
            (output / "ploemeur_physical_ig/manifest.json",),
        ),
        "package": Stage(
            "package",
            (
                python,
                "-m",
                "scripts.build_article_package",
                "--campaign-root",
                str(output),
                "--output",
                str(output / "article_package"),
                "--reuse-valid",
            ),
            (output / "article_package/provenance/article_package_manifest.json",),
        ),
        "archive": Stage(
            "archive",
            (
                python,
                "-m",
                "scripts.build_reproduction_archive",
                "--campaign",
                str(output),
                "--output",
                str(archive),
                "--reuse-valid",
                *dirty_flag,
            ),
            (archive / "ARCHIVE_MANIFEST.json", archive / "CHECKSUMS.sha256"),
        ),
    }


def _required_inputs() -> tuple[Path, ...]:
    return (
        ROOT / "pyproject.toml",
        ROOT / "article/cases.yaml",
        ROOT / "validation/tracerlpm/benchmark/references/forward_reference.csv",
        ROOT / "validation/tracerlpm/benchmark/configs/robustness-width-noise.yaml",
        ROOT / "validation/tracerlpm/benchmark/configs/robustness-age-noise.yaml",
        ROOT / "sites/ploemeur/data/brut/chronique CFC pptv_080125.xlsx",
        ROOT / "sites/ploemeur/data/ori/ori_ploemeur_F09_2005_2024.txt",
        ROOT / "sites/ploemeur/data/ori/ori_ploemeur_F11_2004_2024.txt",
        ROOT / "examples/natural/holten/holten.yaml",
    )


def _check_tracer_config(path: Path) -> list[str]:
    errors = []
    if not path.is_file():
        return [f"missing TracerLPM local config: {path}"]
    payload = yaml.safe_load(path.read_text(encoding="utf-8"))
    for key, hash_key in (
        ("workbook_path", "workbook_sha256"),
        ("xll_path", "xll_sha256"),
    ):
        target = Path(payload[key])
        if not target.is_file():
            errors.append(f"missing {key}: {target}")
        elif _sha256(target).upper() != str(payload[hash_key]).upper():
            errors.append(f"SHA-256 mismatch for {key}: {target}")
    mapping = Path(payload["workbook_map_path"])
    if not mapping.is_file():
        errors.append(f"missing workbook_map_path: {mapping}")
    runner = (
        ROOT
        / "validation/tracerlpm/src/TracerLpmRunner/bin/x64/Release/net8.0-windows/TracerLpmRunner.exe"
    )
    if not runner.is_file() and shutil.which("dotnet") is None:
        errors.append("neither a built TracerLPM runner nor dotnet is available")
    return errors


def preflight(
    output: Path,
    selected: tuple[str, ...],
    tracer_config: Path,
    allow_dirty: bool,
) -> dict[str, object]:
    errors = []
    if not _outside_repository(output):
        errors.append(f"campaign output must be outside the Git repository: {output}")
    if sys.version_info < (3, 12):
        errors.append(f"Python 3.12+ required, found {platform.python_version()}")
    errors.extend(
        f"missing input: {path}" for path in _required_inputs() if not path.is_file()
    )
    dirty = _git("status", "--short")
    if dirty and not allow_dirty:
        errors.append(
            "Git worktree is dirty; commit/stash changes or pass --allow-dirty"
        )
    if "tracerlpm" in selected:
        errors.extend(_check_tracer_config(tracer_config))
    report = {
        "checked_at": _now(),
        "git_head": _git("rev-parse", "HEAD"),
        "git_dirty": bool(dirty),
        "output": str(output),
        "selected_stages": list(selected),
        "errors": errors,
        "passed": not errors,
    }
    return report


def _write_json_atomic(path: Path, payload: dict[str, object]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile(
        mode="w", encoding="utf-8", dir=path.parent, delete=False, suffix=".tmp"
    ) as stream:
        json.dump(payload, stream, ensure_ascii=False, indent=2)
        stream.write("\n")
        temporary = Path(stream.name)
    temporary.replace(path)


def _load_manifest(path: Path, output: Path) -> dict[str, object]:
    current_head = _git("rev-parse", "HEAD")
    if path.is_file():
        payload = json.loads(path.read_text(encoding="utf-8"))
        previous_head = str(payload.get("git_head", current_head))
        payload.setdefault("initial_git_head", previous_head)
        records = payload.get("stages", {})
        if isinstance(records, dict):
            for record in records.values():
                if isinstance(record, dict):
                    record.setdefault("git_head", previous_head)
        payload["git_head"] = current_head
        return payload
    return {
        "schema_version": 1,
        "created_at": _now(),
        "git_head": current_head,
        "initial_git_head": current_head,
        "campaign_root": str(output),
        "stages": {},
    }


def _stage_complete(stage: Stage) -> bool:
    return all(path.is_file() for path in stage.expected)


def _run_stage(stage: Stage, log: Path) -> int:
    log.parent.mkdir(parents=True, exist_ok=True)
    with log.open("a", encoding="utf-8", newline="\n") as stream:
        stream.write(f"[{_now()}] {subprocess.list2cmdline(stage.command)}\n")
        process = subprocess.Popen(
            stage.command,
            cwd=ROOT,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            encoding="utf-8",
            errors="replace",
            env=os.environ.copy(),
        )
        assert process.stdout is not None
        for line in process.stdout:
            print(line, end="", flush=True)
            stream.write(line)
            stream.flush()
        return process.wait()


def run_campaign(
    output: Path,
    stages: dict[str, Stage],
    selected: tuple[str, ...],
    *,
    resume: bool,
    dry_run: bool,
) -> int:
    output.mkdir(parents=True, exist_ok=True)
    manifest_path = output / "campaign_manifest.json"
    manifest = _load_manifest(manifest_path, output)
    records = manifest.setdefault("stages", {})
    assert isinstance(records, dict)
    for name in selected:
        stage = stages[name]
        existing = records.get(name, {})
        if resume and existing.get("status") == "success" and _stage_complete(stage):
            print(f"SKIP {name}: validated successful stage")
            continue
        print(
            f"{'DRY  ' if dry_run else 'RUN  '} {name}: {subprocess.list2cmdline(stage.command)}"
        )
        if dry_run:
            continue
        started = time.perf_counter()
        records[name] = {
            "status": "running",
            "started_at": _now(),
            "git_head": _git("rev-parse", "HEAD"),
            "command": list(stage.command),
            "expected": [str(path) for path in stage.expected],
        }
        _write_json_atomic(manifest_path, manifest)
        code = _run_stage(stage, output / "logs" / f"{name}.log")
        complete = code == 0 and _stage_complete(stage)
        records[name].update(
            {
                "status": "success" if complete else "failed",
                "finished_at": _now(),
                "elapsed_seconds": time.perf_counter() - started,
                "returncode": code,
            }
        )
        _write_json_atomic(manifest_path, manifest)
        if not complete:
            print(
                f"FAILED {name}; see {output / 'logs' / f'{name}.log'}", file=sys.stderr
            )
            return code or 1
    if not dry_run:
        manifest["completed_at"] = _now()
        _write_json_atomic(manifest_path, manifest)
    return 0


def _selected_stages(raw: str | None) -> tuple[str, ...]:
    if raw is None:
        return ALL_STAGES
    selected = tuple(item.strip() for item in raw.split(",") if item.strip())
    unknown = set(selected) - set(ALL_STAGES)
    if unknown:
        raise ValueError(f"unknown stages: {sorted(unknown)}")
    return selected


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=("preflight", "run", "resume", "status"))
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument(
        "--workers", type=int, default=max(1, min(6, os.cpu_count() or 1))
    )
    parser.add_argument("--stages", help="comma-separated subset in execution order")
    parser.add_argument(
        "--tracerlpm-config",
        type=Path,
        default=ROOT
        / "validation/tracerlpm/config/runner-config.robustness.local.yaml",
    )
    parser.add_argument("--allow-dirty", action="store_true")
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args(argv)
    output = args.output.resolve()
    try:
        selected = _selected_stages(args.stages)
    except ValueError as error:
        parser.error(str(error))
    stages = _stage_map(
        output, args.workers, args.tracerlpm_config.resolve(), args.allow_dirty
    )
    if args.action == "status":
        path = output / "campaign_manifest.json"
        if not path.is_file():
            print("No campaign manifest found")
            return 1
        print(path.read_text(encoding="utf-8"), end="")
        return 0
    report = preflight(
        output, selected, args.tracerlpm_config.resolve(), args.allow_dirty
    )
    print(json.dumps(report, ensure_ascii=False, indent=2))
    if args.action == "preflight":
        return 0 if report["passed"] else 1
    if not report["passed"]:
        return 1
    return run_campaign(
        output,
        stages,
        selected,
        resume=args.action == "resume",
        dry_run=args.dry_run,
    )


if __name__ == "__main__":
    raise SystemExit(main())
