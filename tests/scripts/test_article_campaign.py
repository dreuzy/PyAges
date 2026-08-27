# Copyright (c) 2021-2026 Centre national de la recherche scientifique (CNRS)
# Contributor: Jean-Raynald de Dreuzy
# SPDX-License-Identifier: CECILL-2.1

import json

from scripts import (
    build_article_package,
    build_reproduction_archive,
    reproduce_article,
)
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


def test_forward_stage_uses_the_versioned_qualification_config(tmp_path):
    stages = reproduce_article._stage_map(
        tmp_path,
        workers=1,
        tracer_config=tmp_path / "tracerlpm.yaml",
        allow_dirty=False,
    )
    command = stages["forward"].command

    assert command[command.index("--config") + 1] == str(
        reproduce_article.ROOT / "validation/tracerlpm/benchmark/configs/campaign.yaml"
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


def test_validate_campaign_accepts_successful_fresh_stage(tmp_path):
    expected = tmp_path / "forward" / "summary.json"
    expected.parent.mkdir()
    expected.write_text("{}", encoding="utf-8")
    manifest = {
        "schema_version": 1,
        "git_head": "campaign-revision",
        "stages": {
            "forward": {
                "status": "success",
                "returncode": 0,
                "git_head": "execution-revision",
            }
        },
    }
    (tmp_path / "campaign_manifest.json").write_text(
        json.dumps(manifest), encoding="utf-8"
    )
    stage = reproduce_article.Stage("forward", ("python", "forward.py"), (expected,))

    report = reproduce_article.validate_campaign(
        tmp_path, {"forward": stage}, ("forward",)
    )

    assert report["status"] == "valid"
    assert report["stages"]["forward"] == {
        "status": "valid",
        "recorded_git_head": "execution-revision",
        "expected_file_count": 1,
        "missing_expected": [],
    }
    assert report["errors"] == []


def test_validate_campaign_rejects_missing_expected_file(tmp_path):
    expected = tmp_path / "forward" / "summary.json"
    manifest = {
        "schema_version": 1,
        "stages": {"forward": {"status": "success", "returncode": 0}},
    }
    (tmp_path / "campaign_manifest.json").write_text(
        json.dumps(manifest), encoding="utf-8"
    )
    stage = reproduce_article.Stage("forward", ("python", "forward.py"), (expected,))

    report = reproduce_article.validate_campaign(
        tmp_path, {"forward": stage}, ("forward",)
    )

    assert report["status"] == "invalid"
    assert report["stages"]["forward"]["status"] == "invalid"
    assert any("missing expected files" in error for error in report["errors"])


def test_validate_campaign_hash_checks_package_and_archive(monkeypatch, tmp_path):
    package_manifest = (
        tmp_path / "article_package" / "provenance" / "article_package_manifest.json"
    )
    archive_root = tmp_path.with_name(f"{tmp_path.name}-gmd-archive")
    archive_manifest = archive_root / "ARCHIVE_MANIFEST.json"
    archive_checksums = archive_root / "CHECKSUMS.sha256"
    for path in (package_manifest, archive_manifest, archive_checksums):
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text("{}", encoding="utf-8")
    manifest = {
        "schema_version": 1,
        "stages": {
            "package": {"status": "success", "returncode": 0},
            "archive": {"status": "success", "returncode": 0},
        },
    }
    (tmp_path / "campaign_manifest.json").write_text(
        json.dumps(manifest), encoding="utf-8"
    )
    stages = {
        "package": reproduce_article.Stage("package", (), (package_manifest,)),
        "archive": reproduce_article.Stage(
            "archive", (), (archive_manifest, archive_checksums)
        ),
    }
    monkeypatch.setattr(
        build_article_package,
        "validate_package",
        lambda unused: {"artifacts": [{}, {}]},
    )
    monkeypatch.setattr(
        build_reproduction_archive,
        "validate_archive",
        lambda unused: {"files": [{}, {}, {}]},
    )

    report = reproduce_article.validate_campaign(
        tmp_path, stages, ("package", "archive")
    )

    assert report["status"] == "valid"
    assert report["package_artifacts"] == 2
    assert report["archive_files"] == 3
    assert report["stages"]["package"]["checksum_status"] == "valid"
    assert report["stages"]["archive"]["checksum_status"] == "valid"


def test_validate_campaign_reports_checksum_failure(monkeypatch, tmp_path):
    package_manifest = (
        tmp_path / "article_package" / "provenance" / "article_package_manifest.json"
    )
    package_manifest.parent.mkdir(parents=True)
    package_manifest.write_text("{}", encoding="utf-8")
    manifest = {
        "schema_version": 1,
        "stages": {"package": {"status": "success", "returncode": 0}},
    }
    (tmp_path / "campaign_manifest.json").write_text(
        json.dumps(manifest), encoding="utf-8"
    )
    stage = reproduce_article.Stage("package", (), (package_manifest,))

    def fail_validation(unused):
        raise RuntimeError("hash: results.csv")

    monkeypatch.setattr(build_article_package, "validate_package", fail_validation)

    report = reproduce_article.validate_campaign(
        tmp_path, {"package": stage}, ("package",)
    )

    assert report["status"] == "invalid"
    assert report["stages"]["package"]["status"] == "invalid"
    assert report["stages"]["package"]["checksum_status"] == "invalid"
    assert report["errors"] == ["package checksum validation: hash: results.csv"]


def test_archive_validate_only_does_not_require_build_arguments(
    monkeypatch, tmp_path, capsys
):
    monkeypatch.setattr(
        build_reproduction_archive,
        "validate_archive",
        lambda path: {"files": [{"path": str(path)}]},
    )

    assert build_reproduction_archive.main(["--validate-only", str(tmp_path)]) == 0
    assert "Validated 1 archived files" in capsys.readouterr().out


def test_ploemeur_stabilized_cases_have_no_required_historical_outputs():
    assert all(not hasattr(case, "historical") for case in ploemeur_shifted.CASES)


def test_tracerlpm_source_inputs_are_independent_from_campaign_output(monkeypatch):
    monkeypatch.setenv("PYAGES_TRACERLPM_BENCHMARK_ROOT", r"C:\external\campaign")

    assert generate_inputs.SOURCE_REPOSITORY_ROOT == reproduce_article.ROOT
