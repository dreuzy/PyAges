# Copyright (c) 2021-2026 Centre national de la recherche scientifique (CNRS)
# Contributor: Jean-Raynald de Dreuzy
# SPDX-License-Identifier: CECILL-2.1

import json

import pytest

from scripts.maintenance.benchmark_model_space import main, run_benchmark


def test_model_space_benchmark_counts_preparations_without_timing_threshold() -> None:
    result = run_benchmark(rows=20, methods=2, panels=4, repeat=1)

    assert result["repeated_preparations"] == 8
    assert result["shared_preparations"] == 2
    assert result["repeated_seconds"] > 0.0
    assert result["shared_seconds"] > 0.0
    assert result["speedup"] > 0.0


def test_model_space_benchmark_can_write_json(tmp_path) -> None:
    output = tmp_path / "benchmark.json"

    assert (
        main(
            [
                "--rows",
                "20",
                "--methods",
                "2",
                "--panels",
                "3",
                "--repeat",
                "1",
                "--json-output",
                str(output),
            ]
        )
        == 0
    )

    result = json.loads(output.read_text(encoding="utf-8"))
    assert result["repeated_preparations"] == 6
    assert result["shared_preparations"] == 2


@pytest.mark.parametrize("name", ["rows", "methods", "panels", "repeat"])
def test_model_space_benchmark_rejects_non_positive_dimensions(name: str) -> None:
    dimensions = {"rows": 1, "methods": 1, "panels": 1, "repeat": 1}
    dimensions[name] = 0

    with pytest.raises(ValueError, match=rf"{name} must be positive"):
        run_benchmark(**dimensions)
