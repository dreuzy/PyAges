# Copyright (c) 2021-2026 Centre national de la recherche scientifique (CNRS)
# Contributor: Jean-Raynald de Dreuzy
# SPDX-License-Identifier: CECILL-2.1

"""Post-process the final shifted-exponential MTT posterior summaries.

This script deliberately never imports or runs PyAges simulation/sampling code.  When
the compact 19-case summary is present, it reuses its canonical posterior summaries
and only inventories/hashes the final chain artifacts for provenance checks.
"""

from __future__ import annotations

import argparse
import csv
import json
import math
import re
import statistics
from pathlib import Path

from scripts.common.provenance import sha256_file as sha256

EXPECTED_CASES = [
    (1, 1.0, 1.0),
    (2, 1.0, 10.0),
    (3, 1.0, 20.0),
    (4, 1.0, 30.0),
    (5, 1.0, 40.0),
    (6, 10.0, 1.0),
    (7, 10.0, 10.0),
    (8, 10.0, 20.0),
    (9, 10.0, 30.0),
    (10, 10.0, 40.0),
    (11, 20.0, 1.0),
    (12, 20.0, 10.0),
    (13, 20.0, 20.0),
    (14, 20.0, 30.0),
    (15, 30.0, 1.0),
    (16, 30.0, 10.0),
    (17, 30.0, 20.0),
    (18, 40.0, 1.0),
    (19, 40.0, 10.0),
]
EXPECTED_TRACERS = ["cfc11", "cfc12", "cfc113", "sf6"]
COMPACT_REQUIRED = [
    "case",
    "target_mu",
    "target_t0",
    "target_mtt",
    "posterior_mtt_mean",
    "posterior_mtt_median",
    "posterior_mtt_sd",
    "posterior_mtt_q10",
    "posterior_mtt_q90",
    "posterior_mtt_q025",
    "posterior_mtt_q975",
    "min_ess",
    "max_split_rhat",
]
OUTPUT_COLUMNS = [
    "case",
    "target_mu",
    "target_t0",
    "target_MTT",
    "MTT_mean",
    "MTT_median",
    "MTT_sd",
    "MTT_q10",
    "MTT_q90",
    "MTT_q025",
    "MTT_q975",
    "U80",
    "U95",
    "CV_MTT",
    "min_ESS",
    "max_split_Rhat",
]
CHAIN_RE = re.compile(r"case_(\d{2})_chain_([1-5])_n10000\.npz$")


def read_csv(path: Path) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        return list(csv.DictReader(handle))


def close(a: float, b: float, *, atol: float = 1e-12) -> bool:
    return math.isclose(a, b, rel_tol=1e-12, abs_tol=atol)


def find_unique(root: Path, filename: str, predicate=lambda path: True) -> Path:
    candidates = sorted(
        path.resolve() for path in root.rglob(filename) if predicate(path)
    )
    if len(candidates) != 1:
        rendered = "\n".join(f"  - {path}" for path in candidates) or "  (none)"
        raise RuntimeError(
            f"Expected exactly one valid {filename}, found {len(candidates)}:\n{rendered}"
        )
    return candidates[0]


def load_final_manifest(root: Path) -> tuple[Path, dict]:
    valid: list[tuple[Path, dict]] = []
    for path in root.rglob("manifest.json"):
        if path.parent.name != "shifted_exponential":
            continue
        try:
            manifest = json.loads(path.read_text(encoding="utf-8"))
            protocol = manifest["protocol"]
            cases = [(int(c[0]), float(c[1]), float(c[2])) for c in protocol["cases"]]
            steps = {int(k): int(v) for k, v in protocol["final_steps_by_case"].items()}
            if (
                cases == EXPECTED_CASES
                and protocol["tracers"] == EXPECTED_TRACERS
                and close(float(protocol["relative_error"]), 0.08)
                and protocol["synthetic_noise_added"] is False
                and int(protocol["chains"]) == 5
                and close(float(protocol["burn_in"]), 0.2)
                and steps == {case: 10_000 for case, _, _ in EXPECTED_CASES}
            ):
                valid.append((path.resolve(), manifest))
        except (KeyError, TypeError, ValueError, json.JSONDecodeError):
            continue
    if len(valid) != 1:
        rendered = "\n".join(f"  - {path}" for path, _ in valid) or "  (none)"
        raise RuntimeError(
            f"Expected exactly one manifest matching the final campaign, found {len(valid)}:\n"
            f"{rendered}"
        )
    return valid[0]


def artifact_hash(manifest: dict, suffix: str) -> str:
    matches = [
        value
        for key, value in manifest["artifact_sha256"].items()
        if key.replace("\\", "/").endswith(suffix)
    ]
    if len(matches) != 1:
        raise AssertionError(f"Manifest has {len(matches)} hashes ending in {suffix!r}")
    return matches[0]


def verify_campaign(manifest_path: Path, manifest: dict) -> tuple[Path, Path]:
    campaign = manifest_path.parent
    table3 = campaign / "table3_final.csv"
    chains_dir = campaign / "chains"
    if not table3.is_file() or not chains_dir.is_dir():
        raise AssertionError("Final table3 or chains directory is missing")

    seed_rule = str(manifest["protocol"].get("seed_rule", ""))
    if "420000+100*case+zero_based_chain" not in seed_rule or "12345" in seed_rule:
        raise AssertionError(f"Unexpected production seed rule: {seed_rule!r}")

    chain_paths = sorted(chains_dir.glob("*.npz"))
    expected_pairs = {
        (case, chain) for case, _, _ in EXPECTED_CASES for chain in range(1, 6)
    }
    actual_pairs: set[tuple[int, int]] = set()
    for path in chain_paths:
        match = CHAIN_RE.fullmatch(path.name)
        if match is None:
            raise AssertionError(f"Unexpected chain filename: {path.name}")
        actual_pairs.add((int(match.group(1)), int(match.group(2))))
    if len(chain_paths) != 95 or actual_pairs != expected_pairs:
        raise AssertionError(
            f"Expected the 95 final multi-chain files, found {len(chain_paths)}"
        )

    if sha256(table3) != artifact_hash(manifest, "/table3_final.csv"):
        raise AssertionError("table3_final.csv does not match its manifest SHA-256")
    for path in chain_paths:
        if sha256(path) != artifact_hash(manifest, f"/chains/{path.name}"):
            raise AssertionError(
                f"Chain does not match its manifest SHA-256: {path.name}"
            )
    return table3.resolve(), chains_dir.resolve()


def verify_compact_against_table3(
    compact_path: Path, compact_rows: list[dict[str, str]], table3_path: Path
) -> None:
    if len(compact_rows) != 19:
        raise AssertionError(f"Compact CSV has {len(compact_rows)} rows instead of 19")
    missing = [name for name in COMPACT_REQUIRED if name not in compact_rows[0]]
    if missing:
        raise AssertionError(f"Compact CSV is missing columns: {missing}")

    table_rows = read_csv(table3_path)
    if len(table_rows) != 19:
        raise AssertionError(
            f"table3_final.csv has {len(table_rows)} rows instead of 19"
        )
    by_case = {int(row["case"]): row for row in table_rows}

    compare_columns = [
        "target_mu",
        "target_t0",
        "target_mtt",
        "posterior_mtt_mean",
        "posterior_mtt_median",
        "posterior_mtt_sd",
        "posterior_mtt_q10",
        "posterior_mtt_q90",
        "posterior_mtt_q025",
        "posterior_mtt_q975",
    ]
    expected_source = table3_path.relative_to(compact_path.parents[2]).as_posix()
    for row in compact_rows:
        case = int(row["case"])
        canonical = by_case[case]
        for column in compare_columns:
            if not close(float(row[column]), float(canonical[column])):
                raise AssertionError(
                    f"Compact/table3 mismatch for case {case}, {column}"
                )
        expected_min_ess = min(
            float(canonical[f"{p}_ess"]) for p in ("mu", "t0", "mtt")
        )
        expected_max_rhat = max(
            float(canonical[f"{p}_split_rhat"]) for p in ("mu", "t0", "mtt")
        )
        if not close(float(row["min_ess"]), expected_min_ess):
            raise AssertionError(f"Non-canonical minimum ESS for case {case}")
        if not close(float(row["max_split_rhat"]), expected_max_rhat):
            raise AssertionError(f"Non-canonical maximum split-Rhat for case {case}")
        if "canonical_source" in row and row["canonical_source"] != expected_source:
            raise AssertionError(
                f"Unexpected canonical_source for case {case}: {row['canonical_source']!r}"
            )


def build_output(compact_rows: list[dict[str, str]]) -> list[dict[str, float | int]]:
    output: list[dict[str, float | int]] = []
    expected_targets = {case: (mu, t0) for case, mu, t0 in EXPECTED_CASES}
    for source in compact_rows:
        case = int(source["case"])
        target_mu = float(source["target_mu"])
        target_t0 = float(source["target_t0"])
        target_mtt = float(source["target_mtt"])
        mean = float(source["posterior_mtt_mean"])
        median = float(source["posterior_mtt_median"])
        sd = float(source["posterior_mtt_sd"])
        q10 = float(source["posterior_mtt_q10"])
        q90 = float(source["posterior_mtt_q90"])
        q025 = float(source["posterior_mtt_q025"])
        q975 = float(source["posterior_mtt_q975"])
        min_ess = float(source["min_ess"])
        max_rhat = float(source["max_split_rhat"])

        if (
            case not in expected_targets
            or (target_mu, target_t0) != expected_targets[case]
        ):
            raise AssertionError(f"Unexpected target configuration for case {case}")
        if not close(target_mtt, target_mu + target_t0):
            raise AssertionError(f"target_MTT != target_mu + target_t0 for case {case}")
        if not q025 <= q10 <= median <= q90 <= q975:
            raise AssertionError(f"Invalid MTT quantile ordering for case {case}")
        if q90 - q10 <= 0 or q975 - q025 <= 0 or sd <= 0:
            raise AssertionError(f"Non-positive uncertainty width for case {case}")
        if not all(
            math.isfinite(value) for value in (mean, median, sd, q025, q10, q90, q975)
        ):
            raise AssertionError(f"Non-finite posterior summary for case {case}")

        output.append(
            {
                "case": case,
                "target_mu": target_mu,
                "target_t0": target_t0,
                "target_MTT": target_mtt,
                "MTT_mean": mean,
                "MTT_median": median,
                "MTT_sd": sd,
                "MTT_q10": q10,
                "MTT_q90": q90,
                "MTT_q025": q025,
                "MTT_q975": q975,
                "U80": (q90 - q10) / (2.0 * target_mtt),
                "U95": (q975 - q025) / (2.0 * target_mtt),
                "CV_MTT": sd / mean,
                "min_ESS": min_ess,
                "max_split_Rhat": max_rhat,
            }
        )
    output.sort(key=lambda row: int(row["case"]))
    if len(output) != 19 or len({row["case"] for row in output}) != 19:
        raise AssertionError("Output does not contain exactly 19 unique cases")
    if max(float(row["max_split_Rhat"]) for row in output) >= 1.01:
        raise AssertionError("At least one canonical split-Rhat is not below 1.01")
    return output


def write_output(path: Path, rows: list[dict[str, float | int]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=OUTPUT_COLUMNS, lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)


def print_case_table(
    rows: list[dict[str, float | int]], title: str = "19 cases"
) -> None:
    print(f"\n{title}")
    print(
        "case  target_mu  target_t0  target_MTT  MTT_median  q10        q90        U80"
    )
    for row in rows:
        print(
            f"{int(row['case']):>4d}  {float(row['target_mu']):>9.1f}  "
            f"{float(row['target_t0']):>9.1f}  {float(row['target_MTT']):>10.1f}  "
            f"{float(row['MTT_median']):>10.6f}  {float(row['MTT_q10']):>9.6f}  "
            f"{float(row['MTT_q90']):>9.6f}  {float(row['U80']):>9.6f}"
        )


def print_summary(
    rows: list[dict[str, float | int]],
    compact: Path,
    manifest: Path,
    table3: Path,
    chains: Path,
    output: Path,
) -> None:
    def stats(column: str) -> tuple[float, float, float]:
        values = [float(row[column]) for row in rows]
        return statistics.median(values), min(values), max(values)

    u80 = stats("U80")
    u95 = stats("U95")
    cv = stats("CV_MTT")
    best = sorted(rows, key=lambda row: float(row["U80"]))[:3]
    worst = sorted(rows, key=lambda row: float(row["U80"]), reverse=True)[:3]

    print("Sources effectivement utilisees")
    print(f"  compact : {compact}")
    print(f"  manifest: {manifest}")
    print(f"  table3  : {table3}")
    print(
        f"  chains  : {chains} (inventaire et SHA-256 seulement; echantillons non charges)"
    )
    print(f"Sortie     : {output}")
    print_case_table(rows)
    print("\nStatistiques globales (mediane, minimum, maximum)")
    print(f"  U80    : {u80[0]:.9f}, {u80[1]:.9f}, {u80[2]:.9f}")
    print(f"  U95    : {u95[0]:.9f}, {u95[1]:.9f}, {u95[2]:.9f}")
    print(f"  CV_MTT : {cv[0]:.9f}, {cv[1]:.9f}, {cv[2]:.9f}")
    print_case_table(best, "3 cas les mieux contraints (U80 croissant)")
    print_case_table(worst, "3 cas les moins bien contraints (U80 decroissant)")
    print("\nControles: OK")
    print(
        "  19 cas uniques; target_MTT=target_mu+target_t0; intervalles positifs et ordonnes"
    )
    print("  Diagnostics canoniques reutilises; tous les split-Rhat < 1.01")
    print(
        "  95 chaines finales manifestees et verifiees; aucune chaine seed=12345 seule"
    )
    print("  Aucune simulation, aucun sampler et aucun MCMC execute")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--root",
        type=Path,
        default=Path(__file__).resolve().parents[2],
        help="PyAges project root (default: inferred from this script)",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=None,
        help="Output CSV (default: alongside the compact audit CSV)",
    )
    args = parser.parse_args()
    root = args.root.resolve()

    manifest_path, manifest = load_final_manifest(root)
    table3_path, chains_dir = verify_campaign(manifest_path, manifest)
    compact_path = find_unique(root, "shifted_exponential_19_cases_compact.csv")
    compact_rows = read_csv(compact_path)
    verify_compact_against_table3(compact_path, compact_rows, table3_path)
    output_rows = build_output(compact_rows)
    output_path = (
        args.output.resolve()
        if args.output is not None
        else compact_path.with_name("shifted_exponential_MTT_uncertainty.csv")
    )
    write_output(output_path, output_rows)
    print_summary(
        output_rows, compact_path, manifest_path, table3_path, chains_dir, output_path
    )


if __name__ == "__main__":
    main()
