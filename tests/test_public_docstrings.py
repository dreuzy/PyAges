# Copyright (c) 2021-2026 Centre national de la recherche scientifique (CNRS)
# Contributor: Jean-Raynald de Dreuzy
# SPDX-License-Identifier: CECILL-2.1

"""Regression guard for documentation on public package objects."""

from __future__ import annotations

import ast
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PACKAGE = ROOT / "pyages"
DOCUMENTED_MAGIC_METHODS = {"__call__", "__init__", "__post_init__"}


def _requires_docstring(node: ast.AST) -> bool:
    if isinstance(node, ast.ClassDef):
        return not node.name.startswith("_")
    if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
        return not node.name.startswith("_") or node.name in DOCUMENTED_MAGIC_METHODS
    return False


def test_public_package_objects_have_docstrings() -> None:
    missing = []
    for path in sorted(PACKAGE.rglob("*.py")):
        tree = ast.parse(path.read_text(encoding="utf-8-sig"), filename=str(path))
        if ast.get_docstring(tree) is None:
            missing.append(f"{path.relative_to(ROOT)}:1 module")
        for node in tree.body:
            if _requires_docstring(node) and ast.get_docstring(node) is None:
                missing.append(f"{path.relative_to(ROOT)}:{node.lineno} {node.name}")
            if not isinstance(node, ast.ClassDef):
                continue
            for member in node.body:
                if _requires_docstring(member) and ast.get_docstring(member) is None:
                    missing.append(
                        f"{path.relative_to(ROOT)}:{member.lineno} "
                        f"{node.name}.{member.name}"
                    )

    assert not missing, "Missing public docstrings:\n" + "\n".join(missing)
