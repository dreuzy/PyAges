# Copyright (c) 2021-2026 Centre national de la recherche scientifique (CNRS)
# Contributor: Jean-Raynald de Dreuzy
# SPDX-License-Identifier: CECILL-2.1

"""Run, resume, and validate the complete article reproduction campaign."""

from __future__ import annotations

import argparse
import hashlib
import importlib.metadata
import json
import os
import platform
import shutil
import site
import subprocess
import sys
import tempfile
import time
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

import yaml
from packaging.version import Version

from pyages import __version__

ROOT = Path(__file__).resolve().parents[2]
RELEASE_TAG = "1.0"
RELEASE_VERSION = "1.0"
REPRODUCTION_ENVIRONMENT = ROOT / "install/environment.yml"
ALL_STAGES = (
    "forward",
    "tracerlpm",
    "shifted_exponential",
    "holten_h4",
    "holten_prior",
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


def _stage_map(
    output: Path,
    workers: int,
    tracer_config: Path,
    allow_dirty: bool,
    expected_tag: str = RELEASE_TAG,
    allow_untagged: bool = False,
):
    python = sys.executable
    archive = output.with_name(f"{output.name}-gmd-archive")
    shifted_summary = (
        output / "ploemeur_shifted_exponential/ploemeur_shiftedexp_final_summary.csv"
    )
    dirty_flag = ("--allow-dirty",) if allow_dirty else ()
    untagged_flag = ("--allow-untagged",) if allow_untagged else ()
    return {
        "forward": Stage(
            "forward",
            (
                python,
                "-m",
                "validation.tracerlpm.benchmark.scripts.compare_pyages",
                "--output",
                str(output / "forward"),
                "--config",
                str(ROOT / "validation/tracerlpm/benchmark/configs/campaign.yaml"),
            ),
            (output / "forward/summary.json", output / "forward/case_results.csv"),
        ),
        "tracerlpm": Stage(
            "tracerlpm",
            (
                python,
                "-m",
                "scripts.article.run_tracerlpm_article_campaign",
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
                "scripts.article.run_final_shifted_exponential",
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
                "scripts.article.run_final_holten_h4",
                "all",
                "--output",
                str(output / "holten_h4"),
            ),
            (output / "holten_h4/manifest.json",),
        ),
        "holten_prior": Stage(
            "holten_prior",
            (
                python,
                "-m",
                "scripts.article.run_holten_prior_robustness",
                "--output",
                str(output / "holten_prior_dirichlet1"),
                "--canonical-holten",
                str(output / "holten_h4"),
            ),
            (
                output / "holten_prior_dirichlet1/manifest.json",
                output
                / "holten_prior_dirichlet1/figureC1_holten_prior_sensitivity.pdf",
                output
                / "holten_prior_dirichlet1/figureC1_holten_prior_sensitivity.png",
            ),
        ),
        "ploemeur_shifted": Stage(
            "ploemeur_shifted",
            (
                python,
                "-m",
                "scripts.article.run_ploemeur_shifted_exponential_final",
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
                "scripts.article.run_ploemeur_targeted_ig_reproduction",
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
                "scripts.release.build_article_package",
                "--campaign-root",
                str(output),
                "--output",
                str(output / "article_package"),
                "--replace",
            ),
            (output / "article_package/provenance/article_package_manifest.json",),
        ),
        "archive": Stage(
            "archive",
            (
                python,
                "-m",
                "scripts.release.build_reproduction_archive",
                "--campaign",
                str(output),
                "--output",
                str(archive),
                "--reuse-valid",
                "--expected-tag",
                expected_tag,
                *dirty_flag,
                *untagged_flag,
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


def _check_release_identity(expected_tag: str, allow_untagged: bool) -> list[str]:
    errors = []
    if Version(__version__) != Version(RELEASE_VERSION):
        errors.append(
            f"PyAges {RELEASE_VERSION} required, source reports {__version__}"
        )
    try:
        installed = importlib.metadata.version("pyages")
    except importlib.metadata.PackageNotFoundError:
        errors.append(
            "PyAges is not installed; run `python -m pip install --no-deps -e .`"
        )
    else:
        if Version(installed) != Version(__version__):
            errors.append(
                "installed PyAges version does not match the source tree: "
                f"installed={installed}, source={__version__}; reinstall with "
                "`python -m pip install --no-deps -e .`"
            )

    tags = {tag for tag in _git("tag", "--points-at", "HEAD").splitlines() if tag}
    if expected_tag not in tags and not allow_untagged:
        errors.append(
            f"release tag {expected_tag!r} does not point at HEAD; tag the exact "
            "reviewed commit or use --allow-untagged for development checks only"
        )
    elif (
        expected_tag in tags
        and _git("cat-file", "-t", f"refs/tags/{expected_tag}") != "tag"
    ):
        errors.append(
            f"release tag {expected_tag!r} must be annotated, not lightweight"
        )
    return errors


def _check_reproduction_environment() -> tuple[dict[str, str], list[str]]:
    """Check the direct versions recorded for the article campaign."""
    payload = yaml.safe_load(REPRODUCTION_ENVIRONMENT.read_text(encoding="utf-8"))
    observed = {
        "python": platform.python_version(),
        "executable": sys.executable,
    }
    errors = []
    observed["user_site_enabled"] = str(bool(site.ENABLE_USER_SITE)).lower()
    if site.ENABLE_USER_SITE:
        errors.append(
            "Python user-site packages are enabled; set PYTHONNOUSERSITE=1 "
            "before launching the article campaign"
        )
    for raw in payload["dependencies"]:
        if not isinstance(raw, str) or "=" not in raw:
            continue
        name, expected = raw.split("=", 1)
        normalized = name.strip().lower()
        expected = expected.strip()
        if normalized == "python":
            actual = platform.python_version()
            observed[normalized] = actual
            if not actual.startswith(f"{expected}.") and actual != expected:
                errors.append(
                    f"article environment requires Python {expected}.x, found {actual}"
                )
            continue
        try:
            actual = importlib.metadata.version(name)
        except importlib.metadata.PackageNotFoundError:
            errors.append(f"missing article-environment dependency: {name}=={expected}")
            continue
        observed[normalized] = actual
        if Version(actual) != Version(expected):
            errors.append(
                f"article environment mismatch for {name}: expected {expected}, "
                f"found {actual}"
            )
    return observed, errors


def _check_stage_entrypoints(
    stages: dict[str, Stage], selected: tuple[str, ...]
) -> tuple[dict[str, str], list[str]]:
    """Import selected Python entry points in one isolated subprocess."""
    modules: dict[str, str] = {}
    errors: list[str] = []
    for name in selected:
        command = stages[name].command
        try:
            module_index = command.index("-m") + 1
            module = command[module_index]
        except (IndexError, ValueError):
            continue
        modules[name] = module

    if not modules:
        return modules, errors

    probe = """
import importlib
import json
import sys

modules = json.loads(sys.argv[1])
failures = {}
for stage, module in modules.items():
    try:
        importlib.import_module(module)
    except Exception as error:
        failures[stage] = f"{type(error).__name__}: {error}"
print(json.dumps(failures))
"""
    environment = os.environ.copy()
    environment["PYTHONNOUSERSITE"] = "1"
    completed = subprocess.run(
        [sys.executable, "-c", probe, json.dumps(modules)],
        cwd=ROOT,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        env=environment,
        check=False,
    )
    if completed.returncode != 0:
        detail = completed.stderr.strip() or completed.stdout.strip()
        return modules, [
            "stage entry-point import probe failed" + (f": {detail}" if detail else "")
        ]
    lines = [line for line in completed.stdout.splitlines() if line.strip()]
    try:
        failures = json.loads(lines[-1])
    except (IndexError, json.JSONDecodeError):
        return modules, ["stage entry-point import probe returned invalid output"]
    errors.extend(
        f"stage {name} entry point {modules[name]!r} is not importable: {message}"
        for name, message in failures.items()
    )
    return modules, errors


def preflight(
    output: Path,
    stages: dict[str, Stage],
    selected: tuple[str, ...],
    tracer_config: Path,
    allow_dirty: bool,
    expected_tag: str = RELEASE_TAG,
    allow_untagged: bool = False,
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
    environment, environment_errors = _check_reproduction_environment()
    errors.extend(environment_errors)
    entrypoints, entrypoint_errors = _check_stage_entrypoints(stages, selected)
    errors.extend(entrypoint_errors)
    errors.extend(_check_release_identity(expected_tag, allow_untagged))
    tags = [tag for tag in _git("tag", "--points-at", "HEAD").splitlines() if tag]
    report = {
        "checked_at": _now(),
        "git_head": _git("rev-parse", "HEAD"),
        "git_dirty": bool(dirty),
        "git_tags_at_head": tags,
        "expected_release_tag": expected_tag,
        "pyages_version": __version__,
        "environment": environment,
        "stage_entrypoints": entrypoints,
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
    current_tags = [
        tag for tag in _git("tag", "--points-at", "HEAD").splitlines() if tag
    ]
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
        payload["git_tags_at_head"] = current_tags
        payload.setdefault("release_tag", RELEASE_TAG)
        payload["pyages_version"] = __version__
        return payload
    return {
        "schema_version": 1,
        "created_at": _now(),
        "git_head": current_head,
        "git_tags_at_head": current_tags,
        "release_tag": RELEASE_TAG,
        "pyages_version": __version__,
        "initial_git_head": current_head,
        "campaign_root": str(output),
        "stages": {},
    }


def _stage_complete(stage: Stage) -> bool:
    return all(path.is_file() for path in stage.expected)


def _invalid_campaign_report(output: Path, error: str) -> dict[str, object]:
    return {
        "schema_version": 1,
        "status": "invalid",
        "scope": "fresh campaign structure and checksums",
        "campaign_root": str(output),
        "errors": [error],
        "stages": {},
    }


def _validate_stage_records(
    stages: dict[str, Stage],
    selected: tuple[str, ...],
    records: dict[str, object],
) -> tuple[dict[str, dict[str, object]], list[str]]:
    stage_results: dict[str, dict[str, object]] = {}
    errors: list[str] = []
    for name in selected:
        stage = stages[name]
        record = records.get(name)
        missing = [str(path) for path in stage.expected if not path.is_file()]
        stage_errors = []
        if not isinstance(record, dict):
            stage_errors.append("missing stage record")
            record = {}
        if record.get("status") != "success":
            stage_errors.append(f"recorded status is {record.get('status')!r}")
        if record.get("returncode") != 0:
            stage_errors.append(f"recorded return code is {record.get('returncode')!r}")
        if missing:
            stage_errors.append(f"missing expected files: {', '.join(missing)}")
        errors.extend(f"{name}: {message}" for message in stage_errors)
        stage_results[name] = {
            "status": "valid" if not stage_errors else "invalid",
            "recorded_git_head": record.get("git_head"),
            "expected_file_count": len(stage.expected),
            "missing_expected": missing,
        }
    return stage_results, errors


def _validate_hash_deliverable(
    name: str,
    root: Path,
    collection: str,
    selected: tuple[str, ...],
    stage_results: dict[str, dict[str, object]],
    validator,
) -> tuple[int | None, str | None]:
    if name not in selected or stage_results[name]["missing_expected"]:
        return None, None
    try:
        payload = validator(root)
        items = payload[collection]
        if not isinstance(items, list):
            raise ValueError(f"manifest field {collection!r} is not a list")
        stage_results[name]["checksum_status"] = "valid"
        return len(items), None
    except (KeyError, OSError, RuntimeError, ValueError) as error:
        stage_results[name]["status"] = "invalid"
        stage_results[name]["checksum_status"] = "invalid"
        return None, f"{name} checksum validation: {error}"


def validate_campaign(
    output: Path,
    stages: dict[str, Stage],
    selected: tuple[str, ...],
) -> dict[str, object]:
    """Validate recorded stage completion and hash-protected deliverables.

    This is the canonical gate for a fresh campaign. It does not inspect the
    optional historical result tree used by ``scripts.article.run_case check`` and
    it does not turn measured numerical results into scientific qualification
    decisions.
    """

    from scripts.release import build_article_package, build_reproduction_archive

    output = output.resolve()
    manifest_path = output / "campaign_manifest.json"
    if not manifest_path.is_file():
        return _invalid_campaign_report(
            output, f"missing campaign manifest: {manifest_path}"
        )

    try:
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError) as error:
        return _invalid_campaign_report(output, f"invalid campaign manifest: {error}")

    records = manifest.get("stages", {})
    if not isinstance(records, dict):
        return _invalid_campaign_report(
            output, "campaign manifest field 'stages' is not an object"
        )

    stage_results, errors = _validate_stage_records(stages, selected, records)
    package_artifacts, package_error = _validate_hash_deliverable(
        "package",
        output / "article_package",
        "artifacts",
        selected,
        stage_results,
        build_article_package.validate_package,
    )
    if package_error:
        errors.append(package_error)
    archive = output.with_name(f"{output.name}-gmd-archive")
    archive_files, archive_error = _validate_hash_deliverable(
        "archive",
        archive,
        "files",
        selected,
        stage_results,
        build_reproduction_archive.validate_archive,
    )
    if archive_error:
        errors.append(archive_error)

    if selected == ALL_STAGES and not manifest.get("completed_at"):
        errors.append("campaign manifest has no completion timestamp")
    if selected == ALL_STAGES:
        if manifest.get("pyages_version") != __version__:
            errors.append(
                "campaign manifest version does not match the current release: "
                f"{manifest.get('pyages_version')!r} != {__version__!r}"
            )
        if manifest.get("release_tag") != RELEASE_TAG:
            errors.append(
                "campaign manifest release tag does not match the intended tag: "
                f"{manifest.get('release_tag')!r} != {RELEASE_TAG!r}"
            )

    return {
        "schema_version": 1,
        "status": "valid" if not errors else "invalid",
        "scope": (
            "fresh campaign structure and checksums; scientific qualification "
            "remains defined by each stage output"
        ),
        "campaign_root": str(output),
        "manifest_git_head": manifest.get("git_head"),
        "completed_at": manifest.get("completed_at"),
        "stages": stage_results,
        "package_artifacts": package_artifacts,
        "archive_files": archive_files,
        "errors": errors,
    }


def _run_stage(stage: Stage, log: Path) -> int:
    log.parent.mkdir(parents=True, exist_ok=True)
    with log.open("a", encoding="utf-8", newline="\n") as stream:
        stream.write(f"[{_now()}] {subprocess.list2cmdline(stage.command)}\n")
        environment = os.environ.copy()
        environment["PYTHONNOUSERSITE"] = "1"
        process = subprocess.Popen(
            stage.command,
            cwd=ROOT,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            encoding="utf-8",
            errors="replace",
            env=environment,
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
            "git_tags_at_head": [
                tag for tag in _git("tag", "--points-at", "HEAD").splitlines() if tag
            ],
            "pyages_version": __version__,
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
    parser.add_argument(
        "action", choices=("preflight", "run", "resume", "status", "validate")
    )
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
    parser.add_argument("--expected-tag", default=RELEASE_TAG)
    parser.add_argument(
        "--allow-untagged",
        action="store_true",
        help="development only: do not require the release tag to point at HEAD",
    )
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args(argv)
    output = args.output.resolve()
    try:
        selected = _selected_stages(args.stages)
    except ValueError as error:
        parser.error(str(error))
    stages = _stage_map(
        output,
        args.workers,
        args.tracerlpm_config.resolve(),
        args.allow_dirty,
        args.expected_tag,
        args.allow_untagged,
    )
    if args.action == "status":
        path = output / "campaign_manifest.json"
        if not path.is_file():
            print("No campaign manifest found")
            return 1
        print(path.read_text(encoding="utf-8"), end="")
        return 0
    if args.action == "validate":
        report = validate_campaign(output, stages, selected)
        print(json.dumps(report, ensure_ascii=False, indent=2))
        return 0 if report["status"] == "valid" else 1
    report = preflight(
        output,
        stages,
        selected,
        args.tracerlpm_config.resolve(),
        args.allow_dirty,
        args.expected_tag,
        args.allow_untagged,
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
