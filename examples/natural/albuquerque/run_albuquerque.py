# -*- coding: utf-8 -*-
"""Run the Albuquerque workflow through the canonical single-date launcher."""

from pathlib import Path

from scripts.launcher import run_workflow

# Repository root is three levels up from this file (examples/natural/albuquerque/)
REPO_ROOT = Path(__file__).resolve().parents[3]


def main():
    params = (
        REPO_ROOT
        / "examples"
        / "natural"
        / "albuquerque"
        / "exemple_albuquerque.yaml"
    )
    output_path = run_workflow(params)
    print(f"Results written to: {output_path}")


if __name__ == "__main__":
    main()
