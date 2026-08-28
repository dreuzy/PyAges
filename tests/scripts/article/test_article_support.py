# Copyright (c) 2021-2026 Centre national de la recherche scientifique (CNRS)
# Contributor: Jean-Raynald de Dreuzy
# SPDX-License-Identifier: CECILL-2.1

import hashlib
import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

from scripts.article import build_article_non_ploemeur_report as non_ploemeur_report
from scripts.article import postprocess_holten_prior_sensitivity as prior_postprocess
from scripts.article import run_ploemeur_shifted_exponential_final as ploemeur_runner
from scripts.article import run_ploemeur_targeted_ig_reproduction as ig_runner
from scripts.common.mcmc_diagnostics import ess, mcse_mean, split_rhat
from scripts.common.reporting import markdown_table
from scripts.release import build_article_package as package


def _summary():
    baseline = {
        "groups": 1,
        "max_split_rhat": 1.0,
        "min_ess": 1000.0,
        "all_converged": True,
    }
    return {
        "thresholds": {"split_rhat_lt": 1.01, "ess_gte": 300.0},
        "pyages_tracerlpm": {
            "paired_cases": 480,
            "pyages_successful": 480,
            "tracerlpm_successful": 480,
        },
        "forward_verification": {
            "case_count": 270,
            "status": "measured_not_yet_qualified",
        },
        "shifted_exponential": baseline,
        "holten_h4": baseline,
        "holten_prior_dirichlet1": baseline,
        "ploemeur_shifted_exponential": baseline,
        "ploemeur_physical_ig": {
            "posterior_sets": 1,
            "max_split_rhat": 1.0,
            "min_bulk_ess": 1000.0,
            "min_tail_ess": 1000.0,
            "all_converged": True,
            "stabilized_campaign_converged": True,
        },
    }


def test_shared_mcmc_diagnostics_distinguish_mixed_and_shifted_chains():
    rng = np.random.default_rng(12345)
    mixed = rng.normal(size=(4, 2000))
    shifted = mixed.copy()
    shifted[0] += 3.0

    assert split_rhat(mixed) < 1.01
    assert ess(mixed) > 1000
    assert split_rhat(shifted) > 1.1


def test_mcse_mean_uses_ess_and_preserves_constant_limit():
    values = np.asarray([1.0, 2.0, 3.0, 4.0])

    assert mcse_mean(values, 4.0) == pytest.approx(np.std(values, ddof=1) / 2.0)
    assert mcse_mean(np.ones(10), 3.0) == 0.0
    with pytest.raises(ValueError, match="effective_sample_size"):
        mcse_mean(values, 0.0)


def test_markdown_table_rounds_and_escapes_without_tabulate():
    frame = pd.DataFrame({"label": ["a|b"], "value": [1.234567]})

    rendered = markdown_table(frame, numeric_round=3)

    assert "a\\|b" in rendered
    assert "1.235" in rendered


def test_article_boolean_diagnostics_treat_missing_values_as_false():
    values = pd.Series([True, " TRUE ", False, "no", None, pd.NA])

    assert package._true_mask(values).tolist() == [
        True,
        True,
        False,
        False,
        False,
        False,
    ]


def test_tracerlpm_report_rejects_missing_model_names(monkeypatch, tmp_path):
    generated = tmp_path / "generated" / "robustness-study"
    generated.mkdir(parents=True)
    pd.DataFrame(
        {
            "model": ["exp", None],
            "noise_relative_sd": [0.0, 0.01],
        }
    ).to_csv(generated / "results.csv", index=False)
    monkeypatch.setattr(non_ploemeur_report, "TRACERLPM", tmp_path)

    with pytest.raises(RuntimeError, match="missing model names"):
        non_ploemeur_report._tracerlpm_summary(tmp_path / "absent-run")


def test_article_package_is_atomic_and_hash_validated(monkeypatch, tmp_path):
    source = tmp_path / "source.txt"
    source.write_text("article result\n", encoding="utf-8")
    artifact = package.Artifact(
        "result",
        "report",
        source,
        Path("reports/result.txt"),
        "test result",
    )
    monkeypatch.setattr(package, "scientific_summary", _summary)
    monkeypatch.setattr(package, "_git", lambda *unused: "test-git-state")
    monkeypatch.setattr(package, "_execution_source_snapshots", lambda unused: ([], {}))
    output = tmp_path / "package"

    package.build_package(output, (artifact,))
    payload = package.validate_package(output)

    assert len(payload["artifacts"]) == 1
    assert (output / "README.md").is_file()
    assert (output / "CHECKSUMS.sha256").is_file()
    source.write_text("updated article result\n", encoding="utf-8")
    package.replace_package(output, (artifact,))
    assert (output / "reports" / "result.txt").read_text(encoding="utf-8") == (
        "updated article result\n"
    )
    (output / "reports" / "result.txt").write_text("corrupted\n", encoding="utf-8")
    with pytest.raises(RuntimeError, match="hash"):
        package.validate_package(output)


def test_replace_article_package_builds_when_output_is_absent(monkeypatch, tmp_path):
    source = tmp_path / "source.txt"
    source.write_text("article result\n", encoding="utf-8")
    artifact = package.Artifact(
        "result",
        "report",
        source,
        Path("reports/result.txt"),
        "test result",
    )
    monkeypatch.setattr(package, "scientific_summary", _summary)
    monkeypatch.setattr(package, "_git", lambda *unused: "test-git-state")
    monkeypatch.setattr(package, "_execution_source_snapshots", lambda unused: ([], {}))
    output = tmp_path / "package"

    package.replace_package(output, (artifact,))

    payload = package.validate_package(output)
    assert len(payload["artifacts"]) == 1
    assert (output / "reports" / "result.txt").read_text(encoding="utf-8") == (
        "article result\n"
    )


def _write_completed_prior_campaigns(baseline, dirichlet):
    posterior_rows = []
    alternative_rows = []
    baseline_medians = (0.1, 0.2, 0.3, 0.4)
    alternative_medians = (0.12, 0.18, 0.29, 0.41)
    for well in prior_postprocess.WELL_ORDER:
        for parameter, baseline_median, alternative_median in zip(
            prior_postprocess.AGE_PARAMETERS,
            baseline_medians,
            alternative_medians,
            strict=True,
        ):
            posterior_rows.append(
                {
                    "well": well,
                    "parameter": parameter,
                    "median": baseline_median,
                    "q10": baseline_median - 0.01,
                    "q90": baseline_median + 0.01,
                }
            )
            alternative_rows.append(
                {
                    "well": well,
                    "parameter": parameter,
                    "median": alternative_median,
                    "q10": alternative_median - 0.01,
                    "q90": alternative_median + 0.01,
                }
            )
    pd.DataFrame(posterior_rows).to_csv(
        baseline / "posterior_summaries.csv", index=False
    )
    pd.DataFrame(alternative_rows).to_csv(
        dirichlet / "posterior_summaries_dirichlet1.csv", index=False
    )

    residual_rows = [
        {
            "prior": prior,
            "well": well,
            "tracer": tracer,
            "standardized_residual": residual,
        }
        for prior, residual in (("uniform_z", 0.5), ("dirichlet_1", 0.4))
        for well in prior_postprocess.WELL_ORDER
        for tracer in ("CFC11", "CFC12", "SF6", "H3")
    ]
    pd.DataFrame(residual_rows).to_csv(
        dirichlet / "standardized_residuals.csv", index=False
    )
    convergence_rows = [
        {
            "prior": "dirichlet_1",
            "well": well,
            "parameter": parameter,
            "split_rhat": 1.001,
            "ess_sum_chains": 500.0,
            "converged": True,
        }
        for well in prior_postprocess.WELL_ORDER
        for parameter in range(7)
    ]
    pd.DataFrame(convergence_rows).to_csv(
        dirichlet / "convergence_diagnostics.csv", index=False
    )
    prior_rows = [
        {
            "prior": prior,
            "fraction": parameter,
            "mean": 0.25,
            "median": 0.25,
            "q10": 0.1,
            "q90": 0.4,
        }
        for prior in ("uniform_z", "dirichlet_1_truncated_to_z_bounds")
        for parameter in prior_postprocess.AGE_PARAMETERS
    ]
    pd.DataFrame(prior_rows).to_csv(
        dirichlet / "prior_only_comparison.csv", index=False
    )
    pd.DataFrame(
        {
            "analytical_abs_det": np.ones(256),
            "finite_difference_abs_det": np.ones(256),
            "relative_error": np.zeros(256),
        }
    ).to_csv(dirichlet / "jacobian_validation.csv", index=False)


def test_holten_prior_postprocess_uses_completed_results_without_sampling(tmp_path):
    baseline = tmp_path / "baseline"
    dirichlet = tmp_path / "dirichlet"
    output = tmp_path / "postprocessed"
    baseline.mkdir()
    dirichlet.mkdir()
    _write_completed_prior_campaigns(baseline, dirichlet)
    baseline_before = (baseline / "posterior_summaries.csv").read_bytes()

    summary = prior_postprocess.postprocess(baseline, dirichlet, output)

    assert summary["maximum_split_rhat"] == pytest.approx(1.001)
    assert summary["minimum_ess"] == pytest.approx(500.0)
    assert summary["largest_age_class_change"]["percentage_points"] == pytest.approx(
        2.0
    )
    assert (baseline / "posterior_summaries.csv").read_bytes() == baseline_before
    assert {
        path.name for path in output.iterdir()
    } == {
        "figureC1_holten_prior_sensitivity.pdf",
        "figureC1_holten_prior_sensitivity.png",
        "posterior_age_fraction_prior_comparison.csv",
        "prior_sensitivity_by_well.csv",
        "prior_sensitivity_summary.json",
        "prior_sensitivity_summary.md",
        "tableC2_prior_sensitivity_by_well.csv",
        "tableC2_prior_sensitivity_by_well.md",
    }

    for protected_output, message in (
        (baseline, "canonical baseline campaign"),
        (baseline / "postprocessed", "canonical baseline campaign"),
        (dirichlet, "Dirichlet campaign"),
        (dirichlet / "postprocessed", "Dirichlet campaign"),
    ):
        with pytest.raises(ValueError, match=message):
            prior_postprocess.postprocess(baseline, dirichlet, protected_output)


def test_holten_prior_postprocess_default_output_is_separate_from_campaigns():
    assert prior_postprocess.DEFAULT_OUTPUT != prior_postprocess.DEFAULT_BASELINE
    assert (
        prior_postprocess.DEFAULT_BASELINE
        not in prior_postprocess.DEFAULT_OUTPUT.parents
    )
    assert prior_postprocess.DEFAULT_OUTPUT != prior_postprocess.DEFAULT_DIRICHLET
    assert (
        prior_postprocess.DEFAULT_DIRICHLET
        not in prior_postprocess.DEFAULT_OUTPUT.parents
    )


def test_execution_sources_can_be_recovered_from_an_exact_worktree(
    monkeypatch, tmp_path
):
    source_root = tmp_path / "old-worktree"
    relative = Path("data/params.yaml")
    exact = b"first: line\r\nsecond: line\n"
    source = source_root / relative
    source.parent.mkdir(parents=True)
    source.write_bytes(exact)
    manifest = tmp_path / "run-manifest.json"
    manifest.write_text(
        json.dumps(
            {
                "git_head": "unneeded-because-source-root-matches",
                "source_sha256": {
                    relative.as_posix(): hashlib.sha256(exact).hexdigest()
                },
            }
        ),
        encoding="utf-8",
    )
    monkeypatch.setattr(package, "SOURCE_MANIFESTS", {"run": manifest})
    monkeypatch.setattr(package, "EXECUTION_SOURCE_ROOTS", (source_root,))
    staging = tmp_path / "staging"

    entries, audit = package._execution_source_snapshots(staging)

    packaged = staging / entries[0]["packaged_path"]
    assert packaged.read_bytes() == exact
    assert entries[0]["source"] == "source_root:0"
    assert audit["run"]["recovered_from_source_root"] == 1


def test_article_package_cli_passes_rebased_campaign_inventory(monkeypatch, tmp_path):
    artifact = package.Artifact(
        "fresh",
        "report",
        tmp_path / "fresh.txt",
        Path("reports/fresh.txt"),
        "fresh campaign result",
    )
    captured = []
    output = tmp_path / "package"
    monkeypatch.setattr(package, "ARTIFACTS", package.ARTIFACTS)
    monkeypatch.setattr(package, "SOURCE_MANIFESTS", package.SOURCE_MANIFESTS)
    monkeypatch.setattr(package, "artifacts_for_campaign", lambda unused: (artifact,))
    monkeypatch.setattr(package, "source_manifests_for_campaign", lambda unused: {})
    monkeypatch.setattr(
        package,
        "build_package",
        lambda selected_output, artifacts: (
            captured.append(tuple(artifacts)) or selected_output
        ),
    )
    monkeypatch.setattr(package, "validate_package", lambda unused: {"artifacts": []})
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "build_article_package.py",
            "--campaign-root",
            str(tmp_path),
            "--output",
            str(output),
        ],
    )

    assert package.main() == 0
    assert captured == [(artifact,)]


def test_publication_package_uses_current_table4_names():
    table_artifacts = {
        artifact.identifier: artifact
        for artifact in package.ARTIFACTS
        if artifact.identifier.startswith("table4_")
    }

    assert set(table_artifacts) == {"table4_csv", "table4_markdown"}
    assert table_artifacts["table4_csv"].source.name == "table4_final.csv"
    assert table_artifacts["table4_csv"].destination == Path("tables/table4.csv")
    assert table_artifacts["table4_markdown"].source.name == "table4_final.md"
    assert table_artifacts["table4_markdown"].destination == Path("tables/table4.md")
    assert all(
        "Table 4" in artifact.description for artifact in table_artifacts.values()
    )

    readme = package._readme(_summary())
    assert "| Table 4 | `tables/table4.md` | `tables/table4.csv` |" in readme
    assert "table3_final" not in readme


def test_article_package_keeps_reproduction_and_user_environments_distinct():
    environment_artifacts = {
        artifact.identifier: artifact
        for artifact in package.ARTIFACTS
        if artifact.category == "environment"
    }
    article_environment = environment_artifacts["article_reproduction_environment"]

    assert environment_artifacts["constraints"].source == (
        package.ROOT / "install/constraints.txt"
    )
    assert article_environment.source == package.ROOT / "install/environment.yml"
    assert article_environment.destination == (
        Path("provenance/environment/article-reproduction-environment.yml")
    )


def test_shifted_exponential_production_text_uses_current_table_number():
    runner = (
        Path(__file__).resolve().parents[3]
        / "scripts"
        / "article"
        / "run_final_shifted_exponential.py"
    ).read_text(encoding="utf-8")
    postprocessor = (
        Path(__file__).resolve().parents[3]
        / "scripts"
        / "article"
        / "postprocess_existing.py"
    ).read_text(encoding="utf-8")

    assert "Table 3" not in runner
    assert "# Table 4 — shifted exponential" in runner
    assert "runner._table4(" in postprocessor


def test_external_chain_paths_do_not_assume_repository_storage():
    repository = Path(__file__).resolve().parents[3]
    for name in ("run_final_shifted_exponential.py", "run_final_holten_h4.py"):
        runner = (repository / "scripts" / "article" / name).read_text(encoding="utf-8")
        assert ".relative_to(ROOT)" not in runner


def test_ploemeur_figure_reuses_cached_predictions(monkeypatch, tmp_path):
    predictions = tmp_path / "figure4_rowwise_posterior_predictions.csv.gz"
    predictions.write_bytes(b"cached")
    intervals = pd.DataFrame(
        {
            "well": ["F09"],
            "calibration": ["full_record"],
            "tracer": ["cfc11"],
            "date": [2020.0],
            "median": [1.0],
            "q10": [0.8],
            "q90": [1.2],
        }
    )
    intervals.to_csv(tmp_path / "figure4_prediction_intervals.csv", index=False)
    insertion = tmp_path / "manuscript_insertion" / "final_figures"
    monkeypatch.setattr(ploemeur_runner, "INSERTION_OUTPUT", insertion)
    monkeypatch.setattr(
        ploemeur_runner,
        "_predict_draws",
        lambda *unused: pytest.fail("cached predictions should be reused"),
    )
    rendered = []
    monkeypatch.setattr(
        ploemeur_runner,
        "_render_figure4",
        lambda unused_output, frame: rendered.append(frame.copy()),
    )

    result = ploemeur_runner._figure4(tmp_path, {})

    assert insertion.is_dir()
    assert result.equals(intervals)
    assert len(rendered) == 1


def test_ig_resume_extends_only_failed_full_series_wells(monkeypatch, tmp_path):
    gate_path = tmp_path / "full_series_gate.json"
    gate_path.write_text(
        json.dumps(
            {
                "passed": False,
                "wells": {
                    "F09": {"passed": False},
                    "F11": {"passed": True},
                },
            }
        ),
        encoding="utf-8",
    )
    calls = []

    def extend(well, steps):
        calls.append((well, steps))
        gate_path.write_text(
            json.dumps(
                {
                    "passed": True,
                    "wells": {
                        "F09": {"passed": True},
                        "F11": {"passed": True},
                    },
                }
            ),
            encoding="utf-8",
        )
        return True

    monkeypatch.setattr(ig_runner, "OUTPUT", tmp_path)
    monkeypatch.setattr(ig_runner, "AUTO_EXTENSION_STEPS", 4000)
    monkeypatch.setattr(ig_runner, "MAX_AUTO_EXTENSIONS", 2)
    monkeypatch.setattr(ig_runner, "MAX_FULL_SERIES_RETAINED_DRAWS", 18000)
    monkeypatch.setattr(
        ig_runner,
        "_load_stage_chains",
        lambda unused_stage, unused_well: np.empty((5, 10000, 3)),
    )
    monkeypatch.setattr(ig_runner, "extend_full_series", extend)

    assert ig_runner._auto_extend_failed_full_series()
    assert calls == [("F09", 4000)]


def test_ig_resume_honors_total_retained_draw_limit(monkeypatch, tmp_path):
    (tmp_path / "full_series_gate.json").write_text(
        json.dumps(
            {
                "passed": False,
                "wells": {
                    "F09": {"passed": False},
                    "F11": {"passed": True},
                },
            }
        ),
        encoding="utf-8",
    )
    monkeypatch.setattr(ig_runner, "OUTPUT", tmp_path)
    monkeypatch.setattr(ig_runner, "MAX_AUTO_EXTENSIONS", 3)
    monkeypatch.setattr(ig_runner, "MAX_FULL_SERIES_RETAINED_DRAWS", 10000)
    monkeypatch.setattr(
        ig_runner,
        "_load_stage_chains",
        lambda unused_stage, unused_well: np.empty((5, 10000, 3)),
    )
    monkeypatch.setattr(
        ig_runner,
        "extend_full_series",
        lambda *unused: pytest.fail("extension limit should stop the run"),
    )

    assert not ig_runner._auto_extend_failed_full_series()
