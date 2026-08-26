"""Regenerate derived products without creating or extending MCMC chains."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def _protocol(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))["protocol"]


def _assert_files(paths: list[Path]) -> None:
    missing = [str(path.relative_to(ROOT)) for path in paths if not path.is_file()]
    if missing:
        raise FileNotFoundError(
            "Post-processing refused; missing existing output(s): " + ", ".join(missing)
        )


def shifted() -> None:
    from scripts import run_final_shifted_exponential as runner

    output = ROOT / "results/final_article_simulations/shifted_exponential"
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


def holten() -> None:
    from scripts import run_final_holten_h4 as runner

    output = ROOT / "results/final_article_simulations/holten_h4_final"
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


def ploemeur() -> None:
    from scripts import run_ploemeur_shifted_exponential_final as runner

    output = (
        ROOT / "results/final_article_simulations/ploemeur_shifted_exponential_final"
    )
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


def robustness() -> None:
    from scripts import run_holten_prior_robustness as runner

    output = ROOT / "results/robustness/holten_prior_dirichlet1"
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
    args = parser.parse_args()
    actions = {
        "s3_1_tracerlpm": report,
        "s3_2_shifted_exponential": shifted,
        "s4_1_holten": holten,
        "s4_2_ploemeur": ploemeur,
        "holten_prior_dirichlet1": robustness,
    }
    actions[args.case]()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
