# Copyright (c) 2021-2026 Centre national de la recherche scientifique (CNRS)
# SPDX-License-Identifier: CECILL-2.1

import json

import pytest

from scripts.release import build_article_package, build_reproduction_archive
from scripts.release import promote_article_campaign as promotion


def _campaign(tmp_path, monkeypatch):
    repository = tmp_path / "repository"
    repository.mkdir()
    monkeypatch.setattr(promotion, "ROOT", repository)
    campaign = tmp_path / "campaign"
    stages = {}
    for name, relative in promotion.NUMERICAL_STAGES.items():
        root = campaign / relative
        root.mkdir(parents=True)
        (root / "result.txt").write_text(f"{name}\n", encoding="utf-8")
        stages[name] = {
            "status": "success",
            "git_head": "historical-head",
            "git_tags_at_head": [],
            "command": ["python", name],
            "expected": [str(root / "result.txt")],
        }
    for relative in promotion.SOURCE_MANIFESTS.values():
        (campaign / relative).write_text(
            json.dumps(
                {
                    "git_head": "historical-head",
                    "source_sha256": {},
                    "artifact_sha256": {},
                }
            ),
            encoding="utf-8",
        )
    (campaign / "campaign_manifest.json").write_text(
        json.dumps({"stages": stages}), encoding="utf-8"
    )

    def fake_git(*args):
        if args == ("status", "--short"):
            return ""
        if args == ("rev-parse", "HEAD"):
            return "release-head"
        if args == ("tag", "--points-at", "HEAD"):
            return "1.0"
        if args == ("cat-file", "-t", "refs/tags/1.0"):
            return "tag"
        raise AssertionError(args)

    monkeypatch.setattr(promotion, "_git", fake_git)
    return campaign


def test_promotion_freezes_retained_results_without_rewriting_history(
    tmp_path, monkeypatch
):
    campaign = _campaign(tmp_path, monkeypatch)
    historical = (campaign / "campaign_manifest.json").read_bytes()

    payload = promotion.build_promotion(
        campaign,
        expected_tag="1.0",
        attestation="Maintainer reviewed non-functional changes.",
        attestation_source="test",
    )
    path = campaign / promotion.PROMOTION_NAME
    promotion.write_promotion(path, payload)

    validated = promotion.validate_promotion(
        campaign,
        path,
        expected_head="release-head",
        expected_tag="1.0",
    )
    assert validated["policy"]["numerical_recalculation_performed"] is False
    assert validated["historical_execution"]["commits"] == ["historical-head"]
    assert (campaign / "campaign_manifest.json").read_bytes() == historical


def test_promotion_rejects_modified_numerical_evidence(tmp_path, monkeypatch):
    campaign = _campaign(tmp_path, monkeypatch)
    payload = promotion.build_promotion(
        campaign,
        expected_tag="1.0",
        attestation="Maintainer reviewed non-functional changes.",
        attestation_source="test",
    )
    path = campaign / promotion.PROMOTION_NAME
    promotion.write_promotion(path, payload)
    (campaign / "forward/result.txt").write_text("changed\n", encoding="utf-8")

    with pytest.raises(RuntimeError, match="forward"):
        promotion.validate_promotion(campaign, path)


def test_campaign_package_includes_optional_promotion(tmp_path):
    campaign = tmp_path / "campaign"
    campaign.mkdir()
    promotion_path = campaign / promotion.PROMOTION_NAME
    promotion_path.write_text("{}\n", encoding="utf-8")

    artifacts = build_article_package.artifacts_for_campaign(campaign)
    selected = {item.identifier: item for item in artifacts}

    assert selected["release_promotion"].source == promotion_path
    assert selected["release_promotion"].destination.as_posix() == (
        "provenance/release_promotion.json"
    )


def test_archive_requires_promotion_for_historical_numerical_commits(
    tmp_path, monkeypatch
):
    campaign = tmp_path / "campaign"
    campaign.mkdir()
    stages = {
        name: {"status": "success", "git_head": "historical-head"}
        for name in promotion.NUMERICAL_STAGES
    }
    (campaign / "campaign_manifest.json").write_text(
        json.dumps({"stages": stages}), encoding="utf-8"
    )

    def fake_git(*args):
        if args == ("status", "--short"):
            return ""
        if args == ("tag", "--points-at", "HEAD"):
            return "1.0"
        if args == ("cat-file", "-t", "refs/tags/1.0"):
            return "tag"
        if args == ("rev-parse", "HEAD"):
            return "release-head"
        raise AssertionError(args)

    monkeypatch.setattr(build_reproduction_archive, "_git", fake_git)

    with pytest.raises(RuntimeError, match="release_promotion.json"):
        build_reproduction_archive.build_archive(
            campaign, tmp_path / "archive", expected_tag="1.0"
        )


def test_reuse_archive_requires_current_release_identity(tmp_path, monkeypatch):
    campaign = tmp_path / "campaign"
    campaign.mkdir()
    (campaign / "campaign_manifest.json").write_text(
        json.dumps(
            {
                "stages": {
                    name: {"git_head": "release-head"}
                    for name in promotion.NUMERICAL_STAGES
                }
            }
        ),
        encoding="utf-8",
    )

    def fake_git(*args):
        if args == ("status", "--short"):
            return ""
        if args == ("tag", "--points-at", "HEAD"):
            return "1.0"
        if args == ("cat-file", "-t", "refs/tags/1.0"):
            return "tag"
        if args == ("rev-parse", "HEAD"):
            return "release-head"
        raise AssertionError(args)

    monkeypatch.setattr(build_reproduction_archive, "_git", fake_git)
    monkeypatch.setattr(
        build_reproduction_archive,
        "validate_archive",
        lambda unused: {
            "git_head": "old-head",
            "git_tags_at_head": [],
            "numerical_provenance_mode": "single-release-commit",
        },
    )

    with pytest.raises(RuntimeError, match="does not match HEAD"):
        build_reproduction_archive.reuse_archive(
            campaign, tmp_path / "archive", expected_tag="1.0"
        )
