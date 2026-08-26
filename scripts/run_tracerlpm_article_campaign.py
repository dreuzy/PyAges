"""Rebuild the paired PyAge/TracerLPM robustness evidence outside the repository."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import shutil
import subprocess
import sys
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[1]
SOURCE_BENCHMARK = ROOT / "validation/tracerlpm/benchmark"
RUNNER_PROJECT = ROOT / "validation/tracerlpm/TracerLpmRunner.sln"
RUNNER = (
    ROOT
    / "validation/tracerlpm/src/TracerLpmRunner/bin/x64/Release/net8.0-windows/TracerLpmRunner.exe"
)


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _copy_versioned_inputs(destination: Path) -> None:
    prefix = "validation/tracerlpm/benchmark/"
    process = subprocess.run(
        ["git", "ls-files", "-z", f"{prefix}configs", f"{prefix}inputs", f"{prefix}references"],
        cwd=ROOT,
        capture_output=True,
        check=True,
    )
    for raw in process.stdout.split(b"\0"):
        if not raw:
            continue
        relative = Path(raw.decode("utf-8"))
        target = destination / relative.relative_to(prefix)
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(ROOT / relative, target)


def _run_python(module: str, arguments: list[str], env: dict[str, str]) -> None:
    command = [sys.executable, "-m", module, *arguments]
    subprocess.run(command, cwd=ROOT, env=env, check=True)


def _runner_config(source: Path, output: Path) -> Path:
    payload = yaml.safe_load(source.read_text(encoding="utf-8"))
    mapping_source = Path(payload["workbook_map_path"])
    mapping_target = output / "workbook-map.yaml"
    shutil.copy2(mapping_source, mapping_target)
    payload.update(
        {
            "workbook_map_path": str(mapping_target),
            "work_root": str(output / "work"),
            "output_root": str(output / "output/robustness-study"),
            "excel_visible": False,
            "reuse_excel_session": True,
        }
    )
    path = output / "runner-config.yaml"
    path.write_text(
        yaml.safe_dump(payload, sort_keys=False, allow_unicode=True), encoding="utf-8"
    )
    return path


def _validate_local_config(path: Path) -> None:
    payload = yaml.safe_load(path.read_text(encoding="utf-8"))
    for key, hash_key in (
        ("workbook_path", "workbook_sha256"),
        ("xll_path", "xll_sha256"),
    ):
        target = Path(payload[key])
        if not target.is_file():
            raise FileNotFoundError(target)
        if _sha256(target).upper() != str(payload[hash_key]).upper():
            raise RuntimeError(f"SHA-256 mismatch for {key}: {target}")


def _ensure_runner() -> None:
    if RUNNER.is_file():
        return
    subprocess.run(
        ["dotnet", "build", str(RUNNER_PROJECT), "-c", "Release", "-p:Platform=x64"],
        cwd=ROOT,
        check=True,
    )
    if not RUNNER.is_file():
        raise FileNotFoundError(RUNNER)


def _run_shard(config: Path, shard: Path, log: Path) -> int:
    log.parent.mkdir(parents=True, exist_ok=True)
    with log.open("w", encoding="utf-8") as stream:
        return subprocess.run(
            [str(RUNNER), "--config", str(config), "--cases", str(shard)],
            cwd=ROOT,
            stdout=stream,
            stderr=subprocess.STDOUT,
            text=True,
            check=False,
        ).returncode


def run(output: Path, config: Path, workers: int) -> None:
    output = output.resolve()
    output.mkdir(parents=True, exist_ok=True)
    benchmark = output / "benchmark"
    _copy_versioned_inputs(benchmark)
    _validate_local_config(config)
    _ensure_runner()
    local_config = _runner_config(config, output)
    env = os.environ.copy()
    env["PYAGE_TRACERLPM_BENCHMARK_ROOT"] = str(benchmark)

    for name in ("robustness-width-noise.yaml", "robustness-age-noise.yaml"):
        _run_python(
            "validation.tracerlpm.benchmark.scripts.run_monte_carlo_pyage",
            ["--config", str(benchmark / "configs" / name), "--workers", str(workers)],
            env,
        )
    _run_python(
        "validation.tracerlpm.benchmark.scripts.prepare_robustness_study", [], env
    )
    process = subprocess.run(
        [
            sys.executable,
            "-m",
            "validation.tracerlpm.benchmark.scripts.prepare_remaining_robustness_shards",
            "--shards",
            str(min(6, workers)),
            "--prefix",
            "article-reproduction",
        ],
        cwd=ROOT,
        env=env,
        capture_output=True,
        text=True,
        check=True,
    )
    queue = json.loads(process.stdout)
    failures = []
    with ThreadPoolExecutor(max_workers=max(1, min(6, workers))) as executor:
        futures = {
            executor.submit(
                _run_shard,
                local_config,
                Path(item["path"]),
                output / "logs" / f"shard-{index}.log",
            ): index
            for index, item in enumerate(queue["shards"], start=1)
        }
        for future in as_completed(futures):
            index = futures[future]
            code = future.result()
            print(f"TracerLPM shard {index}: returncode={code}", flush=True)
            if code:
                failures.append(index)
    if failures:
        raise RuntimeError(f"TracerLPM shards failed: {failures}")
    _run_python(
        "validation.tracerlpm.benchmark.scripts.summarize_robustness_study", [], env
    )
    summary = benchmark / "generated/robustness-study/summary.json"
    if not summary.is_file():
        raise FileNotFoundError(summary)
    manifest = {
        "git_head": subprocess.run(
            ["git", "rev-parse", "HEAD"], cwd=ROOT, capture_output=True, text=True, check=True
        ).stdout.strip(),
        "cases_expected": queue["expected"],
        "cases_valid_before_resume": queue["valid"],
        "cases_run": queue["remaining"],
        "summary": str(summary.relative_to(output)),
        "summary_sha256": _sha256(summary),
        "workbook_sha256": yaml.safe_load(config.read_text(encoding="utf-8"))["workbook_sha256"],
        "xll_sha256": yaml.safe_load(config.read_text(encoding="utf-8"))["xll_sha256"],
    }
    (output / "manifest.json").write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--config", type=Path, required=True)
    parser.add_argument("--workers", type=int, default=6)
    args = parser.parse_args(argv)
    run(args.output, args.config.resolve(), args.workers)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
