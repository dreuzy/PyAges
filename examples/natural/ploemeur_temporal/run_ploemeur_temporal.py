# -*- coding: utf-8 -*-
# Copyright (c) 2021-2026 Centre national de la recherche scientifique (CNRS)
# Contributor: Jean-Raynald de Dreuzy
# SPDX-License-Identifier: CECILL-2.1

"""Run the temporal Ploemeur example through the canonical workflow."""

from pathlib import Path

from pyages.workflows.temporal import run_temporal

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
