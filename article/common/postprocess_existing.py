# Copyright (c) 2021-2026 Centre national de la recherche scientifique (CNRS)
# Contributor: Jean-Raynald de Dreuzy
# SPDX-License-Identifier: CECILL-2.1

"""Regenerate derived products without creating or extending MCMC chains."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def _protocol(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))["protocol"]


def _assert_files(paths: list[Path]) -> None:
    missing = []
    for path in paths:
        if path.is_file():
            continue
        try:
            label = path.relative_to(ROOT)
        except ValueError:
            label = path
        missing.append(str(label))
    if missing:
        raise FileNotFoundError(
            "Post-processing refused; missing existing output(s): " + ", ".join(missing)
        )


DEFAULT_OUTPUTS = {
    "s3_2_shifted_exponential": ROOT
    / "results/final_article_simulations/shifted_exponential",
    "s4_1_holten": ROOT / "results/final_article_simulations/holten_h4_final",
    "s4_2_ploemeur": ROOT
    / "results/final_article_simulations/ploemeur_shifted_exponential_final",
    "holten_prior_dirichlet1": ROOT / "results/robustness/holten_prior_dirichlet1",
}

CAMPAIGN_SUBDIRECTORIES = {
    "s3_2_shifted_exponential": "shifted_exponential",
    "s4_1_holten": "holten_h4",
    "s4_2_ploemeur": "ploemeur_shifted_exponential",
    "holten_prior_dirichlet1": "holten_prior_dirichlet1",
}


def shifted(output: Path) -> None:
    from scripts import run_final_shifted_exponential as runner

    lengths = {
        int(k): int(v)
        for k, v in _protocol(output / "manifest.json")["final_steps_by_case"].items()
    }
    chains = [
        runner._chain_path(output, case, chain, lengths[case])
        for case in lengths
        for chain in range(runner.NCHAINS)
    ]
    _assert_files(chains)
    tables = runner.collect_diagnostics(output, lengths)
    tables["summaries"].to_csv(output / "posterior_summaries.csv", index=False)
    tables["convergence"].to_csv(output / "convergence_diagnostics.csv", index=False)
    tables["runs"].to_csv(output / "chain_diagnostics.csv", index=False)
    tables["acf"].to_csv(
        output / "autocorrelation_functions.csv.gz", index=False, compression="gzip"
    )
    runner._table4(output, tables, lengths)
    runner._figure2(output, lengths)


def holten(output: Path) -> None:
    from scripts import run_final_holten_h4 as runner

    lengths = {
        str(k): int(v)
        for k, v in _protocol(output / "manifest.json")["final_steps_by_well"].items()
    }
    chains = [
        runner._chain_path(output, well, chain, lengths[well])
        for well in lengths
        for chain in range(runner.NCHAINS)
    ]
    _assert_files(chains)
    tables = runner.collect_diagnostics(output, lengths)
    tables["summaries"].to_csv(output / "posterior_summaries.csv", index=False)
    tables["convergence"].to_csv(output / "convergence_diagnostics.csv", index=False)
    tables["runs"].to_csv(output / "chain_diagnostics.csv", index=False)
    tables["acf"].to_csv(
        output / "autocorrelation_functions.csv.gz", index=False, compression="gzip"
    )
    runner._posterior_predictions(output, lengths, tables["convergence"]).to_csv(
        output / "posterior_modeled_concentrations.csv", index=False
    )
    comparison, _ = runner._comparison(tables["summaries"], output)
    runner._figure3(comparison, output)


def ploemeur(output: Path) -> None:
    from scripts import run_ploemeur_shifted_exponential_final as runner

    runner.OUTPUT = output
    runner.DATA_OUTPUT = output / "data_audit"
    runner.INSERTION_OUTPUT = output / "manuscript_insertion" / "final_figures"
    lengths = {
        str(k): int(v)
        for k, v in _protocol(output / "manifest.json")[
            "production_steps_by_case"
        ].items()
    }
    chains = [
        runner._chain_path(output, case, chain, lengths[case.key])
        for case in runner.CASES
        for chain in range(runner.NCHAINS)
    ]
    _assert_files(chains)
    diagnostics, summaries, chain_table = runner._diagnostics(output, lengths)
    diagnostics.to_csv(output / "convergence_diagnostics.csv", index=False)
    summaries.to_csv(output / "posterior_summaries.csv", index=False)
    chain_table.to_csv(output / "chain_diagnostics.csv", index=False)
    compact, quality = runner._compact_and_quality(
        output, lengths, diagnostics, summaries, chain_table
    )
    intervals = runner._figure4(output, lengths)
    tracer_fit = runner._tracer_fit_diagnostics(output, intervals)
    pairing = runner._pairing_effect_diagnostics(output)
    runner._report(output, compact, quality, tracer_fit, pairing)


def robustness(output: Path, canonical_holten: Path | None = None) -> None:
    from scripts import run_holten_prior_robustness as runner

    runner.OUTPUT = output
    if canonical_holten is not None:
        runner.CANONICAL = canonical_holten
    chains = [
        runner._chain_path(output, well, chain)
        for well in runner.FINAL_STEPS
        for chain in range(runner.NCHAINS)
    ]
    _assert_files(chains)
    runner.validate_jacobian(output)
    runner.compare_priors(output)
    convergence, chain_table, summaries = runner.collect_diagnostics(output)
    residuals = runner.posterior_predictions(output)
    comparison = runner.compare_posteriors(output, summaries)
    runner.global_metrics(output, comparison, convergence, chain_table, residuals)
    runner.make_figure(output, comparison)
    print(f"Post-processing complete (no sampler called): {output}")


def report() -> None:
    from scripts.build_article_non_ploemeur_report import build

    print(build(ROOT / "results/article_non_ploemeur_final"))


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "case",
        choices=(
            "s3_1_tracerlpm",
            "s3_2_shifted_exponential",
            "s4_1_holten",
            "s4_2_ploemeur",
            "holten_prior_dirichlet1",
        ),
    )
    location = parser.add_mutually_exclusive_group()
    location.add_argument(
        "--output",
        type=Path,
        help="Existing output directory for the selected case.",
    )
    location.add_argument(
        "--campaign-root",
        type=Path,
        help=(
            "Existing root produced by scripts.reproduce_article; the case "
            "subdirectory is selected automatically."
        ),
    )
    parser.add_argument(
        "--canonical-holten",
        type=Path,
        help="Canonical Holten output used by the prior-sensitivity case.",
    )
    args = parser.parse_args()
    if args.output is not None:
        output = args.output.resolve()
    elif args.campaign_root is not None:
        subdirectory = CAMPAIGN_SUBDIRECTORIES.get(args.case)
        output = (
            args.campaign_root.resolve() / subdirectory
            if subdirectory is not None
            else None
        )
    else:
        output = DEFAULT_OUTPUTS.get(args.case)
    actions = {
        "s3_1_tracerlpm": lambda: report(),
        "s3_2_shifted_exponential": lambda: shifted(output),
        "s4_1_holten": lambda: holten(output),
        "s4_2_ploemeur": lambda: ploemeur(output),
        "holten_prior_dirichlet1": lambda: robustness(
            output,
            args.canonical_holten.resolve()
            if args.canonical_holten is not None
            else None,
        ),
    }
    if output is None and args.case != "s3_1_tracerlpm":
        parser.error("an output directory is required for this case")
    actions[args.case]()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
