# Copyright (c) 2021-2026 Centre national de la recherche scientifique (CNRS)
# Contributor: Jean-Raynald de Dreuzy
# SPDX-License-Identifier: CECILL-2.1

"""List or execute reproducible HYP-26-0172 matrix experiments.

The command validates enabled matrix rows, resolves an immutable per-run
configuration, records source and input fingerprints, and launches the normal
Ploemeur driver only when ``--execute`` is explicit. Dry-run selection is the
default so maintainers can inspect a campaign without starting calibration.
"""

from __future__ import annotations

import argparse
import os
import platform
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

import yaml

from .study_common import (
    REPO_ROOT,
    checksums,
    checksums_digest,
    input_files,
    load_matrix,
    profile_results_root,
    profiled_experiment_id,
    resolve_repo_path,
    source_files,
    split_field,
    validate_profile,
    write_json,
)
from .validate_study import validate_row


def select_rows(
    rows: list[dict[str, str]], args: argparse.Namespace
) -> list[dict[str, str]]:
    """Return enabled matrix rows matching an identifier and column selectors."""
    selected = [row for row in rows if row["enabled"].lower() == "true"]
    if args.experiment_id:
        selected = [
            row for row in selected if row["experiment_id"] == args.experiment_id
        ]
    for expression in args.select:
        if "=" not in expression:
            raise ValueError(f"Invalid selector {expression!r}; expected COLUMN=VALUE")
        column, value = expression.split("=", 1)
        if column not in rows[0]:
            raise ValueError(f"Unknown matrix column: {column}")
        selected = [row for row in selected if value in split_field(row[column])]
    return selected


def git_value(*args: str) -> str:
    """Return Git output, or ``unavailable`` when provenance cannot be queried."""
    result = subprocess.run(
        ["git", *args], cwd=REPO_ROOT, text=True, capture_output=True, check=False
    )
    return result.stdout.strip() if result.returncode == 0 else "unavailable"


def prepare_run(
    row: dict[str, str], resume: bool, profile: str, mh_nsteps: int | None
) -> tuple[Path, list[str], dict]:
    """Create an isolated run directory, resolved config, and prepared manifest.

    No calibration is started. Existing non-empty output is rejected unless
    ``resume`` is explicit, and an optional step override is recorded in the
    resolved configuration and manifest.
    """
    experiment_id = profiled_experiment_id(row["experiment_id"], profile)
    run_dir = profile_results_root(profile) / "runs" / experiment_id
    workflow_dir = run_dir / "workflow"
    if run_dir.exists() and any(run_dir.iterdir()) and not resume:
        raise FileExistsError(
            f"Run directory is not empty: {run_dir}; use --resume to reuse it"
        )
    run_dir.mkdir(parents=True, exist_ok=True)
    workflow_dir.mkdir(parents=True, exist_ok=True)

    params_path = resolve_repo_path(row["params_path"])
    resolved_config = run_dir / "resolved_config.yaml"
    with params_path.open(encoding="utf-8") as handle:
        config = yaml.safe_load(handle) or {}
    if mh_nsteps is not None:
        config.setdefault("calibration", {})["mh_nsteps"] = mh_nsteps
    config.setdefault("results", {}).update(
        {
            "use_default": False,
            "directory": str(workflow_dir.relative_to(REPO_ROOT)).replace("\\", "/"),
        }
    )
    resolved_config.write_text(
        yaml.safe_dump(config, sort_keys=False, allow_unicode=True), encoding="utf-8"
    )
    input_checksums = checksums(input_files(row, params_path))
    source_checksums = checksums(source_files())
    write_json(run_dir / "input_checksums.json", input_checksums)
    write_json(run_dir / "source_checksums.json", source_checksums)
    pip_freeze = subprocess.run(
        [sys.executable, "-m", "pip", "freeze"],
        cwd=REPO_ROOT,
        text=True,
        capture_output=True,
        check=False,
    )
    (run_dir / "environment.txt").write_text(
        f"python={sys.version.replace(os.linesep, ' ')}\n"
        f"platform={platform.platform()}\n"
        "\n[pip-freeze]\n"
        f"{pip_freeze.stdout}",
        encoding="utf-8",
    )
    command = [
        sys.executable,
        "-m",
        "sites.ploemeur.scripts.ploemeur_driver",
        "--params",
        str(resolved_config),
    ]
    now = datetime.now(timezone.utc).isoformat()
    manifest = {
        "schema_version": 2,
        "profile": profile,
        "mh_nsteps": config.get("calibration", {}).get("mh_nsteps"),
        "experiment": row,
        "status": "prepared",
        "prepared_at_utc": now,
        "started_at_utc": None,
        "finished_at_utc": None,
        "return_code": None,
        "command": command,
        "git": {
            "commit": git_value("rev-parse", "HEAD"),
            "dirty": bool(git_value("status", "--porcelain")),
            "status": git_value("status", "--porcelain"),
        },
        "fingerprints": {
            "inputs_sha256": checksums_digest(input_checksums),
            "sources_sha256": checksums_digest(source_checksums),
        },
        "artifacts": {
            "resolved_config": str(resolved_config.relative_to(REPO_ROOT)),
            "input_checksums": str(
                (run_dir / "input_checksums.json").relative_to(REPO_ROOT)
            ),
            "source_checksums": str(
                (run_dir / "source_checksums.json").relative_to(REPO_ROOT)
            ),
            "environment": str((run_dir / "environment.txt").relative_to(REPO_ROOT)),
            "workflow": str(workflow_dir.relative_to(REPO_ROOT)),
        },
    }
    write_json(run_dir / "manifest.json", manifest)
    return run_dir, command, manifest


def execute(
    row: dict[str, str], resume: bool, profile: str, mh_nsteps: int | None
) -> int:
    """Prepare and execute one row while recording terminal manifest status."""
    run_dir, command, manifest = prepare_run(row, resume, profile, mh_nsteps)
    manifest["status"] = "running"
    manifest["started_at_utc"] = datetime.now(timezone.utc).isoformat()
    write_json(run_dir / "manifest.json", manifest)
    result = subprocess.run(command, cwd=REPO_ROOT, check=False)
    manifest["return_code"] = result.returncode
    manifest["status"] = "completed" if result.returncode == 0 else "failed"
    manifest["finished_at_utc"] = datetime.now(timezone.utc).isoformat()
    write_json(run_dir / "manifest.json", manifest)
    return result.returncode


def parse_args() -> argparse.Namespace:
    """Parse matrix selection, profile, resume, and execution options."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--experiment-id")
    parser.add_argument("--select", action="append", default=[], metavar="COLUMN=VALUE")
    parser.add_argument(
        "--execute", action="store_true", help="actually launch selected calibrations"
    )
    parser.add_argument(
        "--resume", action="store_true", help="allow an existing run directory"
    )
    parser.add_argument(
        "--profile",
        type=validate_profile,
        default="production",
        help="campaign name; non-production profiles use isolated output directories",
    )
    parser.add_argument(
        "--mh-nsteps",
        type=int,
        help="override calibration steps in the resolved config (recommended for smoke runs)",
    )
    return parser.parse_args()


def main() -> int:
    """Validate selected rows, print dry-run commands, or execute them."""
    args = parse_args()
    if args.profile == "smoke" and args.mh_nsteps is None:
        args.mh_nsteps = 100
    if args.mh_nsteps is not None and args.mh_nsteps < 100:
        raise ValueError(
            "--mh-nsteps must be at least 100; shorter chains produce degenerate posteriors"
        )
    rows = load_matrix()
    selected = select_rows(rows, args)
    if not selected:
        print("No enabled experiment matched the selection.")
        return 1
    errors = [error for row in selected for error in validate_row(row)]
    if errors:
        for error in errors:
            print(f"ERROR: {error}", file=sys.stderr)
        return 2
    for row in selected:
        params_path = resolve_repo_path(row["params_path"])
        steps = args.mh_nsteps or "configured"
        command = f'{sys.executable} -m sites.ploemeur.scripts.ploemeur_driver --params "{params_path.relative_to(REPO_ROOT)}"'
        if not args.execute:
            print(f"{row['experiment_id']} [{args.profile}, steps={steps}]: {command}")
            continue
        return_code = execute(row, args.resume, args.profile, args.mh_nsteps)
        if return_code:
            return return_code
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
