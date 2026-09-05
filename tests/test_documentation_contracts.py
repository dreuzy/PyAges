# Copyright (c) 2021-2026 Centre national de la recherche scientifique (CNRS)
# Contributor: Jean-Raynald de Dreuzy
# SPDX-License-Identifier: CECILL-2.1

"""Cross-check prose contracts that are not exercised by Sphinx."""

import ast
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


def test_site_studies_are_discoverable_without_becoming_packaged_api() -> None:
    """Keep the online index, local guides, and wheel boundary aligned."""
    index = (ROOT / "docs/index.md").read_text(encoding="utf-8")
    running = (ROOT / "docs/user-guide/running-examples.md").read_text(encoding="utf-8")
    studies = (ROOT / "docs/studies/index.md").read_text(encoding="utf-8")
    ploemeur = (ROOT / "docs/studies/ploemeur.md").read_text(encoding="utf-8")
    local = (ROOT / "sites/ploemeur/README.md").read_text(encoding="utf-8")

    assert "studies/index" in index
    assert "not copied into the installed" in running
    assert "not installed in the PyAges" in studies
    assert "sites/ploemeur/studies/HYP-26-0172/README.md" in ploemeur
    assert "not installed with the `pyages` wheel" in local


def test_reproduction_docs_distinguish_historical_and_fresh_evidence() -> None:
    guide = (ROOT / "docs/science/reproducibility.md").read_text(encoding="utf-8")
    report = (
        ROOT / "docs/reports/reproduction_campaign_status_2026-08-27.md"
    ).read_text(encoding="utf-8")

    assert "## Two evidence layers" in guide
    assert "scripts.article.reproduce_article validate" in guide
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
    assert "`complete` after success" in document
    assert "`failed` after rejection" in document


def test_configuration_reference_states_exact_temporal_constraints() -> None:
    document = (ROOT / "docs/user-guide/configuration.md").read_text(encoding="utf-8")

    assert "strictly greater than 100" in document
    assert "`[0, 0.5)`" in document
    assert "Relative error in `(0, 1)`" in document
    assert "iteration > burn_in * mh_nsteps" in document
    assert "unknown section or field" in document
    assert "exact bounded quantile" in document
    assert "perform rejection sampling or consume `max_attempts`" in document
    assert "currently always enables the parametric priors" in document
    assert "does not expose" in document


def test_natural_notebooks_use_only_canonical_public_apis() -> None:
    notebook_paths = (
        ROOT / "examples/natural/albuquerque/exemple_albuquerque.ipynb",
        ROOT / "examples/natural/ploemeur/exemple_ploemeur.ipynb",
        ROOT / "examples/natural/ploemeur_temporal/exemple_ploemeur_temporal.ipynb",
    )
    removed_api_markers = (
        "pyages.concentrations.concentrations",
        "pyages.concentrations.chronicles",
        "pyages.concentrations.utils",
        "pyages.calibration.utils",
        "pyages.calibration.methods.metropolis_hastings",
        "pyages.calibration.methods.prior",
        "pyages.calibration.methods.trajectory",
        "pyages.calibration.mh_proposals",
        "pyages.calibration.ig_parameterization",
        "concentrations_time",
        "pyages.observations.loader",
        "dataframe_load=",
        "file_load=",
        ".cv",
        ".names(",
        ".names_dates(",
        ".tracer_names(",
        "error_affect_from_",
        "cdata=",
        "nmodels=resolution",
        "nmodels=objective_nmodels",
        "objfunc=",
        "reachconc=",
        "display_concentration_times",
        ".proposal_step",
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
    assert "code-tour" in dev_index
    assert (ROOT / "docs/dev/code-tour.md").is_file()
    assert "write_result_manifest" in document
    assert "**last**" in document
    compile(_first_python_block(document), "extending-calibration-workflows", "exec")


def test_multichain_contributor_example_uses_the_canonical_dataclass_api() -> None:
    document = (ROOT / "docs/user-guide/multichain-mh.md").read_text(encoding="utf-8")
    section = document.split("(multichain-mh-python-contributor-interface)=", 1)[
        1
    ].split("## Interpret qualification and failure", 1)[0]
    example = _first_python_block(section)

    assert "from pyages.calibration.methods.mh import" in example
    assert "proposal_multiplier=None" in example
    assert 'proposal_multiplier="auto"' not in example
    assert ").prepare()" in example
    assert "record: MHRunRecord" in example
    assert "record.pooled_samples()" in example
    tree = ast.parse(example, filename="multichain-mh:contributor-interface")
    guards = [node for node in tree.body if isinstance(node, ast.If)]
    assert len(guards) == 1
    guard = guards[0]
    assert ast.unparse(guard.test) == "record.qualification_status == 'qualified'"
    assert any(
        isinstance(node, ast.Call)
        and isinstance(node.func, ast.Attribute)
        and node.func.attr == "pooled_samples"
        for statement in guard.body
        for node in ast.walk(statement)
    )
    assert not any(
        isinstance(node, ast.Call)
        and isinstance(node.func, ast.Attribute)
        and node.func.attr == "pooled_samples"
        for statement in guard.orelse
        for node in ast.walk(statement)
    )
    assert any(
        isinstance(node, ast.Attribute) and node.attr == "diagnostics"
        for statement in guard.orelse
        for node in ast.walk(statement)
    )


def test_multichain_failure_recovery_drill_preserves_the_evidence_contract() -> None:
    document = (ROOT / "docs/user-guide/multichain-mh.md").read_text(encoding="utf-8")
    section = document.split("(multichain-mh-failure-recovery-drill)=", 1)[1].split(
        "## Inspect chains and traces", 1
    )[0]
    python_blocks = [
        fragment.split("```", 1)[0].strip()
        for fragment in section.split("```python")[1:]
    ]

    assert len(python_blocks) == 3
    for index, block in enumerate(python_blocks, start=1):
        compile(block, f"multichain-mh:failure-recovery:{index}", "exec")

    assert "lpm_recovery_single_date_multichain.yaml" in python_blocks[0]
    assert "1.0000000000000002" in python_blocks[0]
    assert 'reviewed_gate["require_convergence"] is True' in python_blocks[0]
    assert 'manifest["status"] == "failed"' in python_blocks[1]
    assert 'manifest["failure"]["type"] == "MHConvergenceError"' in python_blocks[1]
    assert "copytree(evidence, archive)" in python_blocks[1]
    assert 'manifest["status"] == "complete"' in python_blocks[2]
    assert 'assert "failure" not in manifest' in python_blocks[2]
    assert "require_convergence: false" in section
    assert "would not repair the failed qualification" in section


def test_calibration_guide_covers_operational_and_scientific_gates() -> None:
    document = (ROOT / "docs/user-guide/calibration.md").read_text(encoding="utf-8")
    user_index = (ROOT / "docs/user-guide/index.md").read_text(encoding="utf-8")

    assert "calibration" in user_index
    assert "retained_sample_count" in document
    assert "result_manifest.json" in document
    assert "split-$\\hat R$" in document
    assert "Only `CalibrationProblem`" in document


def test_generic_multichain_archive_is_documented_outside_article_tooling() -> None:
    release = (ROOT / "docs/dev/releasing.md").read_text(encoding="utf-8")
    scripts = (ROOT / "scripts/README.md").read_text(encoding="utf-8")

    for document in (release, scripts):
        assert "scripts.qualification.build_multichain_archive" in document
        assert "scripts.qualification.build_ci_multichain_archive" in document
        assert "--mode draft" in document
        assert "--mode publishable" in document
        assert "--expected-tag" in document
        assert "CHECKSUMS.sha256" in document
    assert "independently of the historical article/tag-1.0" in release
    assert "output path must be outside the source repository" in release
    assert "not an origin signature" in release
    assert "exactly one wheel plus one sdist" in scripts
