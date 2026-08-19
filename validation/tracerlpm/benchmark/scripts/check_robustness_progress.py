"""Report exact completion of the expected robustness-study case set."""

from __future__ import annotations

import json

import yaml

from .generate_inputs import BENCHMARK_ROOT
from .generate_inversion_pilot import expanded_cases


CONFIGS = (
    BENCHMARK_ROOT / "configs" / "robustness-width-noise.yaml",
    BENCHMARK_ROOT / "configs" / "robustness-age-noise.yaml",
)
RUN_OUTPUT = BENCHMARK_ROOT.parent / "output" / "robustness-study"


def check() -> dict:
    expected_by_model: dict[str, set[str]] = {"EPM": set(), "DM": set()}
    for path in CONFIGS:
        config = yaml.safe_load(path.read_text(encoding="utf-8"))
        for case in expanded_cases(config):
            expected_by_model[case["model"]].add(f"{case['case_id']}-tracerlpm")
    latest: dict[str, tuple[float, dict]] = {}
    for path in RUN_OUTPUT.glob("robust-*-tracerlpm-*.json"):
        try:
            report = json.loads(path.read_text(encoding="utf-8-sig"))
        except (OSError, json.JSONDecodeError):
            continue
        case_id = report.get("caseId")
        if case_id and (case_id not in latest or path.stat().st_mtime > latest[case_id][0]):
            latest[case_id] = (path.stat().st_mtime, report)
    expected = set().union(*expected_by_model.values())
    present = expected.intersection(latest)
    invalid = sorted(
        case_id for case_id in present if latest[case_id][1].get("status") != "success"
    )
    return {
        "expected": len(expected),
        "present": len(present),
        "valid": len(present) - len(invalid),
        "invalid": len(invalid),
        "epm_present": len(expected_by_model["EPM"].intersection(latest)),
        "dm_present": len(expected_by_model["DM"].intersection(latest)),
        "missing": sorted(expected - present),
        "invalid_case_ids": invalid,
        "complete": present == expected and not invalid,
    }


if __name__ == "__main__":
    print(json.dumps(check(), ensure_ascii=False))
