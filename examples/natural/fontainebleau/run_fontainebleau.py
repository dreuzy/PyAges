# -*- coding: utf-8 -*-
"""
Launcher/orchestrator for the Fontainebleau workflow.
"""

from __future__ import annotations

import argparse
import os
from pathlib import Path
import subprocess
import sys

try:
    from pyage.config.bootstrap import ensure_repo_imports
except ModuleNotFoundError:
    repo_root = Path(__file__).resolve().parents[3]
    sys.path.insert(0, str(repo_root))
    from pyage.config.bootstrap import ensure_repo_imports


ensure_repo_imports()

try:
    from .fontainebleau_benchmark import (
        build_pre_model_figures,
        prepare_fontainebleau_case,
        write_benchmark_summary,
        write_prepared_tables,
    )
    from .fontainebleau_case import (
        build_context,
        write_effective_config,
    )
except ImportError:
    from fontainebleau_benchmark import (
        build_pre_model_figures,
        prepare_fontainebleau_case,
        write_benchmark_summary,
        write_prepared_tables,
    )
    from fontainebleau_case import (
        build_context,
        write_effective_config,
    )


def _running_in_ipython() -> bool:
    try:
        from IPython import get_ipython

        return get_ipython() is not None
    except Exception:
        return False


def _set_results_dir(option: str | None) -> Path | None:
    if option is None:
        return None
    default_dir = Path.home() / "results" / "PyAge"
    if option == "__ASK__":
        user_value = input(f"PYAGE_RESULTS_DIR [{default_dir}]: ").strip()
        results_dir = Path(user_value or str(default_dir))
    else:
        results_dir = Path(option)
    os.environ["PYAGE_RESULTS_DIR"] = str(results_dir)
    if os.name == "nt":
        subprocess.run(["setx", "PYAGE_RESULTS_DIR", str(results_dir)], check=True)
    else:
        print("PYAGE_RESULTS_DIR set for current process only (non-Windows).")
    return results_dir


def _write_effective_launcher_config(
    config_path: Path,
    dataset_name: str | None = None,
    lpm_model_name: str | None = None,
    mh_nstep: int | None = None,
) -> Path:
    context = build_context(config_path)
    return write_effective_config(
        context,
        dataset_name=dataset_name,
        lpm_model_name=lpm_model_name,
        mh_nstep=mh_nstep,
    )


def _resolve_effective_config(
    config_path: Path,
    dataset_name: str | None = None,
    lpm_model_name: str | None = None,
    mh_nstep: int | None = None,
) -> Path:
    if dataset_name or lpm_model_name or mh_nstep is not None:
        return _write_effective_launcher_config(
            config_path,
            dataset_name=dataset_name,
            lpm_model_name=lpm_model_name,
            mh_nstep=mh_nstep,
        )
    return config_path


def write_benchmark_artifacts(prepared) -> None:
    benchmark_root = prepared.context.paths.benchmark_dir
    write_prepared_tables(prepared, benchmark_root / "prepared")
    build_pre_model_figures(prepared, benchmark_root / "pre_model")
    write_benchmark_summary(prepared, benchmark_root)


def run_launcher(config_path: Path, inline: bool = False) -> Path:
    root = Path(__file__).resolve().parents[3]
    if inline or _running_in_ipython():
        if str(root) not in sys.path:
            sys.path.insert(0, str(root))
        import scripts.launcher as launcher

        output_dir = launcher.main(str(config_path), force_inline=True)
        return Path(output_dir)

    subprocess.run(
        [sys.executable, str(root / "scripts" / "launcher.py"), str(config_path)],
        check=True,
    )
    return build_context(config_path).expected_results_dir


def main() -> None:
    parser = argparse.ArgumentParser(description="Run the Fontainebleau workflow.")
    parser.add_argument("--config", default=str(Path(__file__).resolve().parent / "exemple_fontainebleau.yaml"))
    parser.add_argument(
        "--mode",
        choices=("full", "benchmark_only", "calibration_only"),
        default="full",
    )
    parser.add_argument(
        "--dataset",
        default="",
        help="Optional dataset override, for example fontainebleau_IMR.",
    )
    parser.add_argument(
        "--lpm",
        default="",
        help="Optional LPM override, for example ig or dirac_double.",
    )
    parser.add_argument(
        "--mh-nstep",
        type=int,
        default=None,
        help="Optional Metropolis-Hastings step override.",
    )
    parser.add_argument(
        "--inline",
        action="store_true",
        help="Force inline backend for the launcher (useful in notebooks).",
    )
    parser.add_argument(
        "--set-results-dir",
        nargs="?",
        const="__ASK__",
        default=None,
        help="Persist PYAGE_RESULTS_DIR before running the workflow.",
    )
    args = parser.parse_args()

    config_path = Path(args.config)
    _set_results_dir(args.set_results_dir)
    effective_config = _resolve_effective_config(
        config_path,
        dataset_name=args.dataset.strip() or None,
        lpm_model_name=args.lpm.strip() or None,
        mh_nstep=args.mh_nstep,
    )

    prepared = None
    if args.mode in ("full", "benchmark_only"):
        prepared = prepare_fontainebleau_case(effective_config)
        write_benchmark_artifacts(prepared)
        if args.mode == "benchmark_only":
            print(prepared.context.paths.benchmark_dir)
            return

    if args.mode in ("full", "calibration_only"):
        output_dir = run_launcher(effective_config, inline=args.inline)
        print(output_dir)


if __name__ == "__main__":
    main()
