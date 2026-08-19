# -*- coding: utf-8 -*-
"""Run the temporal Ploemeur example through the canonical workflow."""

from pathlib import Path

from pyage.workflows.temporal import run_temporal

REPO_ROOT = Path(__file__).resolve().parents[3]


def main():
    params = (
        REPO_ROOT
        / "examples"
        / "natural"
        / "ploemeur_temporal"
        / "ploemeur_temporal.yaml"
    )
    output_path = run_temporal(params)
    print(f"Results written to: {output_path}")


if __name__ == "__main__":
    main()
