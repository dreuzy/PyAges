# Copyright (c) 2021-2026 Centre national de la recherche scientifique (CNRS)
# Contributor: Jean-Raynald de Dreuzy
# SPDX-License-Identifier: CECILL-2.1

"""Prepare the four-tracer TracerLPM case files for the robustness study."""

from __future__ import annotations

from pathlib import Path

import yaml

from .generate_inputs import BENCHMARK_ROOT
from .prepare_noisy_tracerlpm_campaign import prepare

CONFIGS = (
    BENCHMARK_ROOT / "configs" / "robustness-width-noise.yaml",
    BENCHMARK_ROOT / "configs" / "robustness-age-noise.yaml",
)
OUTPUT_ALL = BENCHMARK_ROOT / "configs" / "tracerlpm-robustness-all.yaml"
OUTPUT_EPM = BENCHMARK_ROOT / "configs" / "tracerlpm-robustness-epm.yaml"
OUTPUT_DM = BENCHMARK_ROOT / "configs" / "tracerlpm-robustness-dm.yaml"
SHARD_SIZE = 80


def _write(path: Path, cases: list[dict], label: str) -> None:
    path.write_text(
        f"# Généré automatiquement pour {label}; ne pas modifier à la main.\n"
        + yaml.safe_dump(cases, sort_keys=False, allow_unicode=True),
        encoding="utf-8",
        newline="\n",
    )


def build() -> dict:
    cases: list[dict] = []
    for index, config in enumerate(CONFIGS, start=1):
        temporary = (
            BENCHMARK_ROOT / "configs" / f".tracerlpm-robustness-phase{index}.yaml"
        )
        cases.extend(prepare(config, temporary))
        temporary.unlink(missing_ok=True)
    identifiers = [case["case_id"] for case in cases]
    if len(identifiers) != len(set(identifiers)):
        raise ValueError(
            "La préparation a produit des identifiants TracerLPM en double"
        )
    epm = [case for case in cases if case["fit"]["model"] == "EPM"]
    dm = [case for case in cases if case["fit"]["model"] == "DM"]
    _write(OUTPUT_ALL, cases, "l'étude complète de robustesse")
    _write(OUTPUT_EPM, epm, "la branche EPM de l'étude de robustesse")
    _write(OUTPUT_DM, dm, "la branche DM de l'étude de robustesse")
    for model, selected in (("epm", epm), ("dm", dm)):
        for index, start in enumerate(range(0, len(selected), SHARD_SIZE), start=1):
            _write(
                BENCHMARK_ROOT
                / "configs"
                / f"tracerlpm-robustness-{model}-shard{index}.yaml",
                selected[start : start + SHARD_SIZE],
                f"le segment {index} de la branche {model.upper()}",
            )
    return {"total": len(cases), "EPM": len(epm), "DM": len(dm)}


if __name__ == "__main__":
    print(yaml.safe_dump(build(), sort_keys=False), end="")
