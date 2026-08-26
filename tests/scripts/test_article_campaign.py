import json

from scripts import build_article_package, reproduce_article
from scripts import run_ploemeur_shifted_exponential_final as ploemeur_shifted
from validation.tracerlpm.benchmark.scripts import generate_inputs


def test_fresh_campaign_rebases_every_generated_article_artifact(tmp_path):
    rebased = build_article_package.artifacts_for_campaign(tmp_path)
    by_id = {artifact.identifier: artifact.source for artifact in rebased}

    assert by_id["forward_results"] == tmp_path / "forward/case_results.csv"
    assert by_id["table3_cases"] == (
        tmp_path / "tracerlpm/benchmark/generated/robustness-study/results.csv"
    )
    assert by_id["figure2_pdf"] == (
        tmp_path / "shifted_exponential/figure2_shifted_exponential_final.pdf"
    )
    assert by_id["figure3_pdf"] == tmp_path / "holten_h4/figure3_holten_h4_final.pdf"
    assert by_id["figure4_pdf"] == (
        tmp_path / "ploemeur_shifted_exponential/figure4_ploemeur_shiftedexp_final.pdf"
    )
    assert by_id["ploemeur_ig_summary"] == (
        tmp_path / "ploemeur_physical_ig/ploemeur_ig_stabilized_results.csv"
    )


def test_campaign_resume_requires_status_and_expected_artifacts(monkeypatch, tmp_path):
    expected = tmp_path / "result.json"
    stage = reproduce_article.Stage("short", ("python", "short.py"), (expected,))
    manifest = {
        "schema_version": 1,
        "created_at": "test",
        "git_head": "test",
        "campaign_root": str(tmp_path),
        "stages": {"short": {"status": "success"}},
    }
    (tmp_path / "campaign_manifest.json").write_text(
        json.dumps(manifest), encoding="utf-8"
    )
    calls = []

    def fake_run(unused_stage, unused_log):
        calls.append(True)
        expected.write_text("{}", encoding="utf-8")
        return 0

    monkeypatch.setattr(reproduce_article, "_run_stage", fake_run)

    assert (
        reproduce_article.run_campaign(
            tmp_path, {"short": stage}, ("short",), resume=True, dry_run=False
        )
        == 0
    )
    assert calls == [True]


def test_campaign_manifest_tracks_revision_used_by_each_stage(monkeypatch, tmp_path):
    manifest = {
        "schema_version": 1,
        "git_head": "initial-revision",
        "stages": {"forward": {"status": "success"}},
    }
    path = tmp_path / "campaign_manifest.json"
    path.write_text(json.dumps(manifest), encoding="utf-8")
    monkeypatch.setattr(reproduce_article, "_git", lambda *unused: "current-revision")

    loaded = reproduce_article._load_manifest(path, tmp_path)

    assert loaded["initial_git_head"] == "initial-revision"
    assert loaded["git_head"] == "current-revision"
    assert loaded["stages"]["forward"]["git_head"] == "initial-revision"


def test_ploemeur_stabilized_cases_have_no_required_historical_outputs():
    assert all(not hasattr(case, "historical") for case in ploemeur_shifted.CASES)


def test_tracerlpm_source_inputs_are_independent_from_campaign_output(monkeypatch):
    monkeypatch.setenv("PYAGE_TRACERLPM_BENCHMARK_ROOT", r"C:\external\campaign")

    assert generate_inputs.SOURCE_REPOSITORY_ROOT == reproduce_article.ROOT
