"""Contracts for the synthetic recovery example entry point."""

from pathlib import Path
from types import SimpleNamespace

import pandas as pd

from examples.synthetic.lpm_recovery_single_date import (
    run_lpm_recovery_single_date as runner,
)


def test_default_runner_reuses_versioned_inputs(tmp_path: Path, monkeypatch) -> None:
    paths = SimpleNamespace(
        params_path=tmp_path / "case.yaml",
        dataset_path=tmp_path / "observations.txt",
        truth_path=tmp_path / "truth.yaml",
    )
    paths.params_path.write_text("case: synthetic\n", encoding="utf-8")
    paths.dataset_path.write_text("element\tconcentration\n", encoding="utf-8")
    paths.truth_path.write_text("lpm: {}\n", encoding="utf-8")
    output = tmp_path / "results"
    calls = []

    monkeypatch.setattr(runner, "case_paths", lambda: paths)
    monkeypatch.setattr(runner, "load_ground_truth", lambda _path: {"lpm": {}})
    monkeypatch.setattr(
        runner,
        "generate_synthetic_case",
        lambda: (_ for _ in ()).throw(AssertionError("unexpected regeneration")),
    )
    monkeypatch.setattr(
        runner,
        "run_single_date",
        lambda params, force_inline: calls.append((params, force_inline)) or output,
    )
    monkeypatch.setattr(
        runner,
        "build_truth_aware_figures",
        lambda **_kwargs: pd.DataFrame(
            [{"parameter": "mu", "true_value": 28.0, "estimated_mean": 28.1}]
        ),
    )

    result = runner.main(force_inline=True)

    assert result == output
    assert calls == [(paths.params_path, True)]
