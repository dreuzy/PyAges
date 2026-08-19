# -*- coding: utf-8 -*-
"""Run the Ploemeur workflow through the canonical single-date launcher."""

from pathlib import Path

from pyage.workflows.single_date import run_workflow

# Repository root is three levels up from this file (examples/natural/ploemeur/)
REPO_ROOT = Path(__file__).resolve().parents[3]


def main():
    params = REPO_ROOT / "examples" / "natural" / "ploemeur" / "exemple_ploemeur.yaml"
    output_path = run_workflow(params)
    print(f"Results written to: {output_path}")


if __name__ == "__main__":
    main()
