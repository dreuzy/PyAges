# Copyright (c) 2021-2026 Centre national de la recherche scientifique (CNRS)
# Contributor: Jean-Raynald de Dreuzy
# SPDX-License-Identifier: CECILL-2.1

"""Cross-check prose contracts that are not exercised by Sphinx."""

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def _first_python_block(section: str) -> str:
    return section.split("```python", 1)[1].split("```", 1)[0].strip()


def test_article_evidence_roots_are_consolidated() -> None:
    assert not (ROOT / "audit").exists()
    assert not (ROOT / "submission_candidate").exists()
    assert (ROOT / "article/audit/README.md").is_file()
    assert (
        ROOT / "article/archive/submission-candidate-2026-08-26/README.md"
    ).is_file()

    repository_readme = (ROOT / "README.md").read_text(encoding="utf-8")
    article_readme = (ROOT / "article/README.md").read_text(encoding="utf-8")
    assert "editorial audits, and dated archives" in repository_readme
    assert "article/audit/" in article_readme
    assert "article/archive/" in article_readme


def test_lpm_extension_examples_include_the_continuous_convolution_contract() -> None:
    document = (ROOT / "docs/user-guide/adding-lpm.md").read_text(encoding="utf-8")
    manual_example = document.split("### Step 1: Create the Python Class", 1)[1].split(
        "### Step 2: Create the Parameter File", 1
    )[0]
    lognormal_example = document.split("### Python Class", 1)[1].split(
        "### Parameter File", 1
    )[0]

    assert "pyages/lpm/models/<name>.py" in document
    assert "def cdf_and_partial_first_moment" in manual_example
    assert "def cdf_and_partial_first_moment" in lognormal_example
    assert "np.trapezoid" in document
    assert "np.trapz" not in document
    compile(_first_python_block(manual_example), "adding-lpm:manual", "exec")
    compile(_first_python_block(lognormal_example), "adding-lpm:lognormal", "exec")


def test_readmes_describe_configurable_temporal_result_layout() -> None:
    for relative_path in ("README.md", "scripts/README.md"):
        document = (ROOT / relative_path).read_text(encoding="utf-8")
        assert "<study_name>" in document
        assert "Metropolis_Hastings/" in document
        assert "<results_root>/ploemeur_temporal" not in document


def test_reproduction_docs_distinguish_historical_and_fresh_evidence() -> None:
    guide = (ROOT / "docs/science/reproducibility.md").read_text(encoding="utf-8")
    report = (
        ROOT / "docs/reports/reproduction_campaign_status_2026-08-27.md"
    ).read_text(encoding="utf-8")

    assert "## Two evidence layers" in guide
    assert "scripts.reproduce_article validate" in guide
    assert "optional historical" in guide
    assert "**0/6**" in report
    assert "**9/9**" in report
    assert "270/270" in report
    assert "holten_prior_dirichlet1" in report

    forward = (ROOT / "docs/reports/forward_qualification_2026-08-27.md").read_text(
        encoding="utf-8"
    )
    assert "0,05 %" in forward
    assert "2\\times10^{-5}" in forward
    assert "270/270 cas passent" in forward


def test_active_forward_docs_state_the_historical_metric_without_a_floor() -> None:
    document = (ROOT / "article/s3_forward_verification/README.md").read_text(
        encoding="utf-8"
    )

    assert "abs(PyAges - reference) / abs(reference)" in document
    assert "stored `NaN` when it was zero" in document
    assert "did not apply a `1e-14` denominator floor" in document
    assert "checksum-protected historical report" in document


def test_workflow_output_reference_covers_stable_artifacts_and_manifest() -> None:
    document = (ROOT / "docs/reference/outputs.md").read_text(encoding="utf-8")

    required_artifacts = {
        "concentrations.txt",
        "parameters_calibration.txt",
        "results_calibration.txt",
        "lpm_dist_calibrated.txt",
        "lpm_histo_calibrated_<parameter>.txt",
        "lpm_stats_calibrated.txt",
        "objective_function_grid.txt",
        "concentrations_all_models.txt",
        "distributions.txt",
        "distributions_stats.txt",
        "result_manifest.json",
    }
    assert all(name in document for name in required_artifacts)
    assert "schema 2" in document
    assert "artifacts_sha256" in document
    assert "written only after success" in document


def test_configuration_reference_states_exact_temporal_constraints() -> None:
    document = (ROOT / "docs/user-guide/configuration.md").read_text(encoding="utf-8")

    assert "strictly greater than 100" in document
    assert "`[0, 0.5)`" in document
    assert "Relative error in `[0, 1)`" in document
    assert "iteration > burn_in * mh_nsteps" in document
    assert "unknown section or field" in document


def test_natural_notebooks_use_only_canonical_concentration_api() -> None:
    notebook_paths = (
        ROOT / "examples/natural/albuquerque/exemple_albuquerque.ipynb",
        ROOT / "examples/natural/ploemeur/exemple_ploemeur.ipynb",
        ROOT / "examples/natural/ploemeur_temporal/exemple_ploemeur_temporal.ipynb",
    )
    removed_api_markers = (
        "pyages.concentrations.concentrations",
        "concentrations_time",
        "pyages.observations.loader",
        "dataframe_load=",
        "file_load=",
        ".cv",
        ".names(",
        ".names_dates(",
        "error_affect_from_",
        "cdata=",
        "nmodels=resolution",
        "nmodels=objective_nmodels",
        "objfunc=",
        "reachconc=",
        "display_concentration_times",
    )

    for notebook_path in notebook_paths:
        notebook = notebook_path.read_text(encoding="utf-8")
        assert "from pyages.concentrations import Concentrations" in notebook
        assert all(marker not in notebook for marker in removed_api_markers)


def test_contributor_extension_contract_is_navigable_and_compilable() -> None:
    document = (ROOT / "docs/dev/extending-calibration-workflows.md").read_text(
        encoding="utf-8"
    )
    dev_index = (ROOT / "docs/dev/index.md").read_text(encoding="utf-8")

    assert "extending-calibration-workflows" in dev_index
    assert "write_result_manifest" in document
    assert "**last**" in document
    compile(_first_python_block(document), "extending-calibration-workflows", "exec")


def test_calibration_guide_covers_operational_and_scientific_gates() -> None:
    document = (ROOT / "docs/user-guide/calibration.md").read_text(encoding="utf-8")
    user_index = (ROOT / "docs/user-guide/index.md").read_text(encoding="utf-8")

    assert "calibration" in user_index
    assert "retained_sample_count" in document
    assert "result_manifest.json" in document
    assert "split-$\\hat R$" in document
    assert "Only `CalibrationProblem`" in document
