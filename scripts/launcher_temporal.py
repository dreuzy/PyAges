# -*- coding: utf-8 -*-
"""Backward-compatible command-line entrypoint for temporal calibration."""

from __future__ import annotations

import argparse
from pathlib import Path

from pyage.workflows.temporal import run_temporal


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Temporal MH launcher (multi-date concentrations)."
    )
    parser.add_argument(
        "--params",
        required=True,
        help="Path to the YAML configuration file.",
    )
    return parser.parse_args()


if __name__ == "__main__":
    args = _parse_args()
    output_path = run_temporal(Path(args.params))
    print(f"Results written to: {output_path}")
