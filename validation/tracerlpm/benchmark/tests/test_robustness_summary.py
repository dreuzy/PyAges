"""Unit contracts for robustness-study aggregation."""

from __future__ import annotations

import pytest

from validation.tracerlpm.benchmark.scripts.summarize_robustness_study import (
    _summarize_groups,
)


def _row(seed: int) -> dict:
    return {
        "model": "EPM",
        "true_tau": 20.0,
        "secondary_name": "r",
        "true_secondary": 1.0,
        "noise_relative_sd": 0.05,
        "pyage_tau": 20.0 + seed / 10.0,
        "pyage_secondary": 1.0,
        "pyage_success": True,
        "pyage_boundary_hit": False,
        "pyage_maximum_concentration_relative_error": 0.01,
        "tracerlpm_tau": 20.5 + seed / 10.0,
        "tracerlpm_secondary": 1.1,
        "tracerlpm_success": True,
        "tracerlpm_boundary_hit": False,
        "tracerlpm_maximum_concentration_relative_error": 0.02,
    }


def test_group_summary_keeps_tool_and_paired_statistics() -> None:
    summaries = _summarize_groups([_row(seed) for seed in range(10)])

    assert len(summaries) == 1
    summary = summaries[0]
    assert summary["count"] == 10
    assert summary["tools"]["pyage"]["successful"] == 10
    assert summary["tools"]["tracerlpm"]["boundary_hits"] == 0
    assert summary["paired_tracerlpm_minus_pyage"]["tau_mean"] == pytest.approx(0.5)
    assert summary["paired_tracerlpm_minus_pyage"]["secondary_mean"] == pytest.approx(
        0.1
    )


def test_group_summary_rejects_an_incomplete_seed_group() -> None:
    with pytest.raises(ValueError, match="Groupe incomplet"):
        _summarize_groups([_row(seed) for seed in range(9)])
