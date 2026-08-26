import ast
import json
import subprocess
import sys
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[1]
ARTICLE = ROOT / "article"
REQUIRED_FIELDS = {
    "case_id",
    "manuscript_section",
    "description",
    "entrypoint",
    "config",
    "canonical_results",
    "figures",
    "tables",
    "manifest",
    "expected_runtime",
    "status",
}


def test_article_registry_has_complete_case_records():
    registry = yaml.safe_load((ARTICLE / "cases.yaml").read_text(encoding="utf-8"))

    assert set(registry) == {
        "s3_forward_verification",
        "s3_1_tracerlpm",
        "s3_2_shifted_exponential",
        "s4_1_holten",
        "s4_2_ploemeur",
        "holten_prior_dirichlet1",
    }
    for case_id, case in registry.items():
        assert REQUIRED_FIELDS <= set(case)
        assert case["case_id"] == case_id
        assert (ROOT / case["manifest"]).is_file()


def test_article_manifests_record_reproducibility_contract():
    registry = yaml.safe_load((ARTICLE / "cases.yaml").read_text(encoding="utf-8"))
    required = {
        "git_commit",
        "calculated_at",
        "environment",
        "seeds",
        "inputs",
        "scripts",
        "parameters",
        "canonical_outputs",
        "large_outputs",
    }

    for case in registry.values():
        manifest = json.loads((ROOT / case["manifest"]).read_text(encoding="utf-8"))
        assert required <= set(manifest)


def test_postprocess_wrapper_never_calls_sampling_or_extension_entrypoints():
    source = (ARTICLE / "common/postprocess_existing.py").read_text(encoding="utf-8")
    tree = ast.parse(source)
    forbidden = {"run_campaign", "run_pilots", "run_production", "analyze_and_extend"}
    calls = {
        node.func.attr
        for node in ast.walk(tree)
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute)
    }

    assert calls.isdisjoint(forbidden)


def test_article_runs_are_routed_to_common_guard():
    registry = yaml.safe_load((ARTICLE / "cases.yaml").read_text(encoding="utf-8"))

    for case_id in (
        "s3_1_tracerlpm",
        "s3_2_shifted_exponential",
        "s4_1_holten",
        "s4_2_ploemeur",
        "holten_prior_dirichlet1",
    ):
        command = registry[case_id]["commands"]["run"]
        assert command[1] == "article/common/run_full.py"
        assert command[2] == case_id


def test_nonportable_tracerlpm_full_run_is_refused():
    result = subprocess.run(
        [
            sys.executable,
            str(ARTICLE / "common/run_full.py"),
            "s3_1_tracerlpm",
        ],
        cwd=ROOT,
        capture_output=True,
        text=True,
        check=False,
    )

    assert result.returncode != 0
    assert "not yet portable" in result.stderr
