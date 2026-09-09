# Copyright (c) 2021-2026 Centre national de la recherche scientifique (CNRS)
# Contributor: Jean-Raynald de Dreuzy
# SPDX-License-Identifier: CECILL-2.1

"""Reject imports that invert the documented PyAges package dependencies."""

from __future__ import annotations

import ast
from collections.abc import Iterator
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]

# These rules protect the stable direction documented in ``docs/architecture.md``.
# Workflows may compose every lower layer and the CLI may call workflows.  Lower
# layers must not reach back into either orchestration layer, and reporting must
# not control workflow execution.
FORBIDDEN_TARGETS = {
    "config": frozenset({"calibration", "cli", "reporting", "workflows"}),
    "concentrations": frozenset({"cli", "reporting", "workflows"}),
    "tracer": frozenset({"cli", "reporting", "workflows"}),
    "lpm": frozenset({"cli", "reporting", "workflows"}),
    "convolution": frozenset({"cli", "reporting", "workflows"}),
    "calibration": frozenset({"cli", "reporting", "workflows"}),
    "data_io": frozenset({"cli", "reporting", "workflows"}),
    "reporting": frozenset({"cli", "workflows"}),
}


def _source_area(path: Path, root: Path) -> str | None:
    """Return the top-level PyAges package containing ``path``."""
    relative = path.relative_to(root / "pyages")
    return relative.parts[0] if len(relative.parts) > 1 else None


def _module_parts(path: Path, root: Path) -> tuple[str, ...]:
    """Return the dotted module components represented by ``path``."""
    parts = list(path.relative_to(root).with_suffix("").parts)
    if parts[-1] == "__init__":
        parts.pop()
    return tuple(parts)


def _from_imports(
    node: ast.ImportFrom,
    *,
    package_parts: tuple[str, ...],
) -> Iterator[str]:
    """Yield absolute candidate modules referenced by one ``from`` import."""
    if node.level:
        parents_to_remove = node.level - 1
        if parents_to_remove > len(package_parts):
            return
        base_parts = package_parts[: len(package_parts) - parents_to_remove]
        if node.module:
            base_parts += tuple(node.module.split("."))
        base = ".".join(base_parts)
    else:
        base = node.module or ""

    if base:
        yield base
        for alias in node.names:
            yield f"{base}.{alias.name}"


def _imported_modules(path: Path, root: Path) -> Iterator[tuple[int, str]]:
    """Yield line numbers and absolute import candidates from one Python file."""
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    module_parts = _module_parts(path, root)
    package_parts = module_parts if path.name == "__init__.py" else module_parts[:-1]

    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                yield node.lineno, alias.name
        elif isinstance(node, ast.ImportFrom):
            for target in _from_imports(node, package_parts=package_parts):
                yield node.lineno, target


def _target_area(module: str) -> str | None:
    """Return the top-level package for an absolute ``pyages`` module."""
    parts = module.split(".")
    if len(parts) < 2 or parts[0] != "pyages":
        return None
    return parts[1]


def find_violations(root: Path = ROOT) -> list[str]:
    """Return deterministic descriptions of forbidden package imports."""
    violations: list[str] = []
    for path in sorted((root / "pyages").rglob("*.py")):
        source = _source_area(path, root)
        if source not in FORBIDDEN_TARGETS:
            continue
        forbidden = FORBIDDEN_TARGETS[source]
        reported: set[tuple[int, str]] = set()
        for line, module in _imported_modules(path, root):
            target = _target_area(module)
            if target not in forbidden or (line, target) in reported:
                continue
            reported.add((line, target))
            relative = path.relative_to(root).as_posix()
            violations.append(
                f"{relative}:{line}: {source} must not import pyages.{target}"
            )
    return violations


def main() -> int:
    """Check the repository and report every inverted dependency."""
    violations = find_violations()
    if violations:
        print("Forbidden PyAges package dependencies:")
        for violation in violations:
            print(f"- {violation}")
        return 1
    print("Architecture dependency rules passed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
