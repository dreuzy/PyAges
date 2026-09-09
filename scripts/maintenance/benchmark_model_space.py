# Copyright (c) 2021-2026 Centre national de la recherche scientifique (CNRS)
# Contributor: Jean-Raynald de Dreuzy
# SPDX-License-Identifier: CECILL-2.1

"""Benchmark one-time versus per-panel model-space result preparation.

This microbenchmark isolates the preparation work factored out of the plotting
loop. It uses deterministic synthetic posterior tables and reports medians; it
does not assert a performance threshold because timings depend on the host.
"""

from __future__ import annotations

import argparse
import json
from collections.abc import Mapping, Sequence
from pathlib import Path
from statistics import median
from time import perf_counter

import matplotlib
import numpy as np
import pandas as pd

matplotlib.use("Agg", force=True)

from pyages.reporting.plots._common import (  # noqa: E402
    _best_row,
    _ensure_frame,
    _method_color,
)
from pyages.reporting.plots.model_space import (  # noqa: E402
    _prepare_posterior_results,
)


def _synthetic_results(rows: int, methods: int) -> dict[str, pd.DataFrame]:
    """Return deterministic posterior-like tables for the benchmark."""
    generator = np.random.default_rng(20260906)
    return {
        f"method_{method_index}": pd.DataFrame(
            {
                "cfc11@2010.0#0": generator.normal(size=rows),
                "cfc12@2010.0#1": generator.normal(size=rows),
                "sf6@2010.0#2": generator.normal(size=rows),
                "3H@2010.0#3": generator.normal(size=rows),
                "obj_function": generator.random(rows),
            }
        )
        for method_index in range(methods)
    }


def _prepare_per_panel(
    results: Mapping[str, pd.DataFrame], panels: int
) -> tuple[int, int]:
    """Reproduce the former repeated preparation pattern."""
    preparations = 0
    consumed_rows = 0
    for _ in range(panels):
        for method_index, (method_name, result) in enumerate(results.items()):
            frame = _ensure_frame(result)
            best = _best_row(frame)
            _method_color(method_name, method_index)
            preparations += 1
            consumed_rows += len(frame) + int(best is not None)
    return preparations, consumed_rows


def _prepare_once(results: Mapping[str, pd.DataFrame], panels: int) -> tuple[int, int]:
    """Prepare once, then reuse the result in every panel."""
    prepared = _prepare_posterior_results(results)
    consumed_rows = 0
    for _ in range(panels):
        for _, frame, best, _ in prepared:
            consumed_rows += len(frame) + int(best is not None)
    return len(prepared), consumed_rows


def _validate_positive(name: str, value: int) -> None:
    if value <= 0:
        raise ValueError(f"{name} must be positive")


def run_benchmark(
    *,
    rows: int = 50_000,
    methods: int = 3,
    panels: int = 4,
    repeat: int = 5,
) -> dict[str, int | float]:
    """Return median timings and preparation counts for both strategies."""
    for name, value in (
        ("rows", rows),
        ("methods", methods),
        ("panels", panels),
        ("repeat", repeat),
    ):
        _validate_positive(name, value)

    results = _synthetic_results(rows, methods)
    repeated_timings: list[float] = []
    shared_timings: list[float] = []
    repeated_count = 0
    shared_count = 0
    for _ in range(repeat):
        started = perf_counter()
        repeated_count, repeated_rows = _prepare_per_panel(results, panels)
        repeated_timings.append(perf_counter() - started)

        started = perf_counter()
        shared_count, shared_rows = _prepare_once(results, panels)
        shared_timings.append(perf_counter() - started)

        if repeated_rows != shared_rows:
            raise RuntimeError("benchmark strategies consumed different data")

    repeated_seconds = median(repeated_timings)
    shared_seconds = median(shared_timings)
    return {
        "rows_per_method": rows,
        "methods": methods,
        "panels": panels,
        "repeat": repeat,
        "repeated_preparations": repeated_count,
        "shared_preparations": shared_count,
        "repeated_seconds": repeated_seconds,
        "shared_seconds": shared_seconds,
        "speedup": repeated_seconds / shared_seconds,
    }


def main(argv: Sequence[str] | None = None) -> int:
    """Parse benchmark dimensions, run it, and emit JSON."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--rows", type=int, default=50_000)
    parser.add_argument("--methods", type=int, default=3)
    parser.add_argument("--panels", type=int, default=4)
    parser.add_argument("--repeat", type=int, default=5)
    parser.add_argument(
        "--json-output",
        type=Path,
        help="optional path receiving the same JSON result",
    )
    args = parser.parse_args(argv)
    result = run_benchmark(
        rows=args.rows,
        methods=args.methods,
        panels=args.panels,
        repeat=args.repeat,
    )
    rendered = json.dumps(result, indent=2, sort_keys=True)
    print(rendered)
    if args.json_output is not None:
        args.json_output.parent.mkdir(parents=True, exist_ok=True)
        args.json_output.write_text(rendered + "\n", encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
