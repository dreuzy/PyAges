"""Generate the maintained summary of pytest collection.

The detailed node IDs remain discoverable through ``pytest --collect-only``.
This script records stable module- and area-level counts, test types, and
purposes in the documentation and lets CI detect when that summary has not
been regenerated.
"""

from __future__ import annotations

import argparse
import subprocess
import sys
from collections import Counter
from pathlib import Path
from typing import NamedTuple

REPO_ROOT = Path(__file__).resolve().parents[1]
INVENTORY_PATH = REPO_ROOT / "docs" / "dev" / "test-inventory.md"
TRACERLPM_TESTS = "validation/tracerlpm/benchmark/tests"


class Collection(NamedTuple):
    core: tuple[str, ...]
    extensive: tuple[str, ...]
    tracerlpm: tuple[str, ...]


class AreaInfo(NamedTuple):
    label: str
    kind: str
    contract: str
    ci_scope: str


AREA_INFO = {
    "tests/(root)": AreaInfo(
        "Repository-wide contracts",
        "Contract / integration",
        "Public API, metadata, manifests, paths, and repository documentation",
        "Standard CI",
    ),
    "tests/calibration": AreaInfo(
        "Calibration and inference",
        "Unit / scientific",
        "Objectives, priors, proposals, parameter grids, and calibration APIs",
        "Standard CI; selected extensive cases",
    ),
    "tests/cli": AreaInfo(
        "Command-line interface",
        "Contract / integration",
        "Installed command behavior, validation, discovery, and user-facing errors",
        "Standard CI and package smoke test",
    ),
    "tests/concentrations": AreaInfo(
        "Concentration handling",
        "Unit / data contract",
        "Chronicle loading and concentration-series behavior",
        "Standard CI",
    ),
    "tests/config": AreaInfo(
        "Configuration",
        "Unit / contract",
        "Validated models, runtime options, and portable path resolution",
        "Standard CI",
    ),
    "tests/convolution": AreaInfo(
        "Convolution",
        "Analytical / scientific",
        "Concentration convolution, numerical identities, settings, and tracer coupling",
        "Standard CI",
    ),
    "tests/examples": AreaInfo(
        "Examples and case studies",
        "Integration / golden",
        "Runnable examples, helper contracts, reproduction modes, and accepted outputs",
        "Standard CI",
    ),
    "tests/io": AreaInfo(
        "Input/output",
        "Unit / data contract",
        "LPM parameter parsing and serialization",
        "Standard CI",
    ),
    "tests/lpm": AreaInfo(
        "Lumped-parameter models",
        "Analytical / unit / golden",
        "Distributions, moments, mixtures, registries, parameters, and generated values",
        "Standard CI",
    ),
    "tests/ploemeur": AreaInfo(
        "Ploemeur field case",
        "Field integration / golden",
        "Preparation, configuration, reference convolution, paths, and workflow outputs",
        "Standard CI; selected extensive cases",
    ),
    "tests/scripts": AreaInfo(
        "Scientific orchestration",
        "Integration / reproducibility",
        "Article campaigns, qualification scripts, and reproducible execution support",
        "Standard CI",
    ),
    "tests/tracer": AreaInfo(
        "Environmental tracers",
        "Scientific unit / contract",
        "Decay, distributed inputs, tracer configuration, and public tracer behavior",
        "Standard CI",
    ),
    "tests/workflows": AreaInfo(
        "Installed workflows",
        "Integration / contract",
        "Plotting runtime and single-date workflow behavior",
        "Standard CI and package smoke test",
    ),
    "validation/tracerlpm": AreaInfo(
        "TracerLPM cross-software validation",
        "Cross-software validation",
        "Mappings, reference inputs, observations, pilots, comparisons, and summaries",
        "TracerLPM validation job",
    ),
}

TOKEN_LABELS = {
    "api": "API",
    "cli": "CLI",
    "f09": "F09",
    "ig": "inverse Gaussian",
    "lpm": "LPM",
    "mh": "Metropolis-Hastings",
    "mcmc": "MCMC",
    "yaml": "YAML",
}


def _collect_nodeids(path: str, *, marker: str | None = None) -> tuple[str, ...]:
    command = [sys.executable, "-m", "pytest", "--collect-only", "-q"]
    if marker is not None:
        command.extend(["-m", marker])
    command.append(path)
    result = subprocess.run(
        command,
        cwd=REPO_ROOT,
        check=False,
        capture_output=True,
        text=True,
    )
    if result.returncode != 0:
        details = "\n".join(part for part in (result.stdout, result.stderr) if part)
        raise RuntimeError(f"pytest collection failed: {' '.join(command)}\n{details}")

    nodeids = tuple(
        line.strip()
        for line in result.stdout.splitlines()
        if "::" in line and not line.startswith(("=", " "))
    )
    if not nodeids:
        raise RuntimeError(f"pytest returned no node IDs for {path}")
    return nodeids


def collect_inventory() -> Collection:
    """Collect core, extensive, and TracerLPM pytest node IDs."""
    return Collection(
        core=_collect_nodeids("tests"),
        extensive=_collect_nodeids("tests", marker="extensive"),
        tracerlpm=_collect_nodeids(TRACERLPM_TESTS),
    )


def _module(nodeid: str) -> str:
    return nodeid.split("::", maxsplit=1)[0].replace("\\", "/")


def _area(module: str) -> str:
    parts = module.split("/")
    if parts[0] == "validation":
        return "validation/tracerlpm"
    if len(parts) == 2:
        return "tests/(root)"
    return "/".join(parts[:2])


def _area_info(area: str) -> AreaInfo:
    try:
        return AREA_INFO[area]
    except KeyError as error:
        raise ValueError(
            f"No test-area description for {area!r}; update AREA_INFO before "
            "regenerating the inventory."
        ) from error


def _module_topic(module: str) -> str:
    stem = Path(module).stem.removeprefix("test_")
    words = [TOKEN_LABELS.get(word, word) for word in stem.split("_")]
    topic = " ".join(words)
    return topic[:1].upper() + topic[1:]


def _module_kind(module: str, extensive_cases: int) -> str:
    if extensive_cases:
        return "Extensive scientific"
    if module.startswith("validation/"):
        return "Cross-software validation"
    if "golden" in Path(module).stem:
        return "Golden regression"
    return _area_info(_area(module)).kind


def _module_purpose(module: str) -> str:
    area = _area_info(_area(module))
    return f"{_module_topic(module)} within {area.label.lower()}."


def _table(
    lines: list[str], headers: tuple[str, ...], rows: list[tuple[object, ...]]
) -> None:
    lines.append("| " + " | ".join(headers) + " |")
    lines.append("|" + "|".join("---" for _ in headers) + "|")
    for row in rows:
        lines.append("| " + " | ".join(str(value) for value in row) + " |")


def render_inventory(collection: Collection) -> str:
    """Render a deterministic Markdown inventory from collected node IDs."""
    core_modules = Counter(_module(nodeid) for nodeid in collection.core)
    extensive_modules = Counter(_module(nodeid) for nodeid in collection.extensive)
    validation_modules = Counter(_module(nodeid) for nodeid in collection.tracerlpm)

    area_modules: dict[str, set[str]] = {}
    area_cases: Counter[str] = Counter()
    for module, count in sorted((core_modules + validation_modules).items()):
        area = _area(module)
        _area_info(area)
        area_modules.setdefault(area, set()).add(module)
        area_cases[area] += count

    lines = [
        "# Generated test inventory",
        "",
        "> Generated by `python -m scripts.generate_test_inventory`. Do not edit",
        "> counts or module rows manually; regenerate after changing collection.",
        "",
        "This is a module-level snapshot, not a record of test success. Parametrized",
        "tests produce multiple collected cases. Use `python run_tests.py collect` for",
        "the complete core node-ID list.",
        "",
        "## Summary",
        "",
    ]
    _table(
        lines,
        ("Scope", "Collected cases", "Modules"),
        [
            (
                "Standard selection",
                len(collection.core) - len(collection.extensive),
                len(core_modules),
            ),
            ("Extensive opt-in", len(collection.extensive), len(extensive_modules)),
            ("Core including extensive", len(collection.core), len(core_modules)),
            (
                "TracerLPM validation",
                len(collection.tracerlpm),
                len(validation_modules),
            ),
            (
                "All documented pytest scopes",
                len(collection.core) + len(collection.tracerlpm),
                len(set(core_modules) | set(validation_modules)),
            ),
        ],
    )
    lines.extend(["", "## Cases by area", ""])
    _table(
        lines,
        (
            "Area",
            "Location",
            "Primary type",
            "Contract",
            "CI scope",
            "Modules",
            "Cases",
        ),
        [
            (
                _area_info(area).label,
                f"`{area}/`",
                _area_info(area).kind,
                _area_info(area).contract,
                _area_info(area).ci_scope,
                len(area_modules[area]),
                area_cases[area],
            )
            for area in sorted(area_modules)
        ],
    )
    lines.extend(["", "## Modules", ""])
    _table(
        lines,
        ("Module", "Type", "Purpose", "Cases", "Extensive"),
        [
            (
                f"`{module}`",
                _module_kind(module, extensive_modules[module]),
                _module_purpose(module),
                core_modules[module],
                extensive_modules[module],
            )
            for module in sorted(core_modules)
        ]
        + [
            (
                f"`{module}`",
                _module_kind(module, 0),
                _module_purpose(module),
                validation_modules[module],
                0,
            )
            for module in sorted(validation_modules)
        ],
    )
    lines.extend(
        [
            "",
            "The standard pytest run skips the extensive cases through the repository",
            "hook unless `--run-extensive` is supplied. Non-pytest CI checks such as",
            "Ruff, Sphinx, Conda, package smoke tests, and the .NET build are documented",
            "in {doc}`ci` and intentionally excluded from these counts.",
            "",
        ]
    )
    return "\n".join(lines)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--check",
        action="store_true",
        help="fail instead of rewriting when the committed inventory is stale",
    )
    args = parser.parse_args(argv)

    rendered = render_inventory(collect_inventory())
    if args.check:
        current = (
            INVENTORY_PATH.read_text(encoding="utf-8")
            if INVENTORY_PATH.exists()
            else ""
        )
        if current != rendered:
            print(
                "Test inventory is stale. Run "
                "`python -m scripts.generate_test_inventory` and commit the result.",
                file=sys.stderr,
            )
            return 1
        print(f"Test inventory is current: {INVENTORY_PATH.relative_to(REPO_ROOT)}")
        return 0

    INVENTORY_PATH.write_text(rendered, encoding="utf-8")
    print(f"Updated {INVENTORY_PATH.relative_to(REPO_ROOT)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
