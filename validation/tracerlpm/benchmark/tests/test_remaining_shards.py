import json

import pytest
import yaml

from validation.tracerlpm.benchmark.scripts.prepare_remaining_robustness_shards import (
    build,
    partition_cases,
    successful_case_ids,
)


def _cases(count: int) -> list[dict]:
    return [
        {"case_id": f"case-{index}", "fit": {"model": "EPM"}} for index in range(count)
    ]


def test_partition_cases_is_balanced_and_preserves_order():
    cases = _cases(10)
    shards = partition_cases(cases, {"case-1", "case-4", "case-8"}, 3)
    assert [len(shard) for shard in shards] == [3, 2, 2]
    assert [case["case_id"] for shard in shards for case in shard] == [
        "case-0",
        "case-2",
        "case-3",
        "case-5",
        "case-6",
        "case-7",
        "case-9",
    ]


def test_partition_cases_rejects_invalid_inputs():
    with pytest.raises(ValueError, match="supérieur"):
        partition_cases(_cases(1), set(), 0)
    duplicate = _cases(2)
    duplicate[1]["case_id"] = duplicate[0]["case_id"]
    with pytest.raises(ValueError, match="double"):
        partition_cases(duplicate, set(), 1)


def test_successful_case_ids_ignores_failed_and_malformed_reports(tmp_path):
    (tmp_path / "robust-a-tracerlpm-one.json").write_text(
        json.dumps({"caseId": "case-a", "status": "success"}), encoding="utf-8"
    )
    (tmp_path / "robust-b-tracerlpm-two.json").write_text(
        json.dumps({"caseId": "case-b", "status": "error"}), encoding="utf-8"
    )
    (tmp_path / "robust-c-tracerlpm-three.json").write_text("{", encoding="utf-8")
    assert successful_case_ids(tmp_path) == {"case-a"}


def test_build_writes_only_missing_cases_and_manifest(tmp_path):
    cases = _cases(5)
    all_cases = tmp_path / "all.yaml"
    all_cases.write_text(yaml.safe_dump(cases, sort_keys=False), encoding="utf-8")
    run_output = tmp_path / "runs"
    run_output.mkdir()
    (run_output / "robust-a-tracerlpm-one.json").write_text(
        json.dumps({"caseId": "case-1", "status": "success"}), encoding="utf-8"
    )
    config_directory = tmp_path / "configs"
    config_directory.mkdir()

    manifest = build(
        shard_count=2,
        prefix="test-missing",
        all_cases_path=all_cases,
        run_output=run_output,
        config_directory=config_directory,
    )

    assert manifest["expected"] == 5
    assert manifest["valid"] == 1
    assert manifest["remaining"] == 4
    assert [shard["count"] for shard in manifest["shards"]] == [2, 2]
    written = []
    for shard in manifest["shards"]:
        written.extend(yaml.safe_load(open(shard["path"], encoding="utf-8")))
    assert [case["case_id"] for case in written] == [
        "case-0",
        "case-2",
        "case-3",
        "case-4",
    ]
    assert (
        json.loads(open(manifest["manifest_path"], encoding="utf-8").read())[
            "remaining"
        ]
        == 4
    )
