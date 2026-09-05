# Copyright (c) 2021-2026 Centre national de la recherche scientifique (CNRS)
# Contributor: Jean-Raynald de Dreuzy
# SPDX-License-Identifier: CECILL-2.1

"""Keep example notebooks executable against the current public API.

The fast tests parse every code cell and compare keyword arguments passed to
imported PyAges callables with their live signatures.  This catches stale
notebook calls without repeating the scientific calculations in ordinary CI.
The opt-in extensive test executes every cell in an isolated repository copy.
"""

from __future__ import annotations

import ast
import importlib
import inspect
import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
NOTEBOOK_PATHS = tuple(sorted(ROOT.glob("examples/**/*.ipynb")))


def _notebook_code(path: Path) -> list[tuple[int, str]]:
    """Return code cells with IPython-only command lines removed."""
    notebook = json.loads(path.read_text(encoding="utf-8"))
    assert notebook["nbformat"] == 4

    cells = []
    for cell_index, cell in enumerate(notebook["cells"]):
        if cell["cell_type"] != "code":
            continue
        source = "".join(cell["source"])
        python_lines = [
            line
            for line in source.splitlines()
            if not line.lstrip().startswith(("%", "!"))
        ]
        cells.append((cell_index, "\n".join(python_lines)))
    return cells


def _pyages_bindings(trees: list[ast.Module]) -> dict[str, object]:
    """Resolve the PyAges names imported by a notebook."""
    bindings: dict[str, object] = {}
    for tree in trees:
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for imported in node.names:
                    if imported.name.startswith("pyages"):
                        name = imported.asname or imported.name.split(".")[0]
                        bindings[name] = importlib.import_module(imported.name)
            elif (
                isinstance(node, ast.ImportFrom)
                and node.module is not None
                and node.module.startswith("pyages")
            ):
                module = importlib.import_module(node.module)
                for imported in node.names:
                    if imported.name != "*":
                        name = imported.asname or imported.name
                        bindings[name] = getattr(module, imported.name)
    return bindings


def _resolve_binding(node: ast.expr, bindings: dict[str, object]) -> object | None:
    """Resolve a direct name or attribute rooted in an imported PyAges name."""
    if isinstance(node, ast.Name):
        return bindings.get(node.id)
    if isinstance(node, ast.Attribute):
        parent = _resolve_binding(node.value, bindings)
        if parent is not None:
            return getattr(parent, node.attr, None)
    return None


@pytest.mark.parametrize(
    "notebook_path",
    NOTEBOOK_PATHS,
    ids=lambda path: str(path.relative_to(ROOT)),
)
def test_notebook_code_compiles_and_matches_pyages_signatures(
    notebook_path: Path,
) -> None:
    """Detect syntax errors and unsupported PyAges keyword arguments quickly."""
    trees = [
        ast.parse(source, filename=f"{notebook_path}:{cell_index}")
        for cell_index, source in _notebook_code(notebook_path)
    ]
    bindings = _pyages_bindings(trees)
    incompatibilities = []

    for tree in trees:
        for node in ast.walk(tree):
            if not isinstance(node, ast.Call):
                continue
            target = _resolve_binding(node.func, bindings)
            if target is None or not callable(target):
                continue
            try:
                signature = inspect.signature(target)
            except (TypeError, ValueError):
                continue
            if any(
                parameter.kind is inspect.Parameter.VAR_KEYWORD
                for parameter in signature.parameters.values()
            ):
                continue

            accepted = {
                name
                for name, parameter in signature.parameters.items()
                if parameter.kind
                not in (
                    inspect.Parameter.POSITIONAL_ONLY,
                    inspect.Parameter.VAR_POSITIONAL,
                )
            }
            unsupported = sorted(
                keyword.arg
                for keyword in node.keywords
                if keyword.arg is not None and keyword.arg not in accepted
            )
            if unsupported:
                incompatibilities.append(
                    f"{ast.unparse(node.func)} at line {node.lineno}: "
                    f"unsupported {unsupported}; signature {signature}"
                )

    assert not incompatibilities, "\n".join(incompatibilities)


@pytest.fixture(scope="module")
def isolated_notebook_repository(tmp_path_factory: pytest.TempPathFactory) -> Path:
    """Copy the notebook runtime inputs so executions cannot alter the checkout."""
    target = tmp_path_factory.mktemp("notebook-repository")
    shutil.copy2(ROOT / "pyproject.toml", target / "pyproject.toml")
    for directory in ("pyages", "data_core", "examples"):
        shutil.copytree(ROOT / directory, target / directory)
    (target / "scripts").mkdir()
    shutil.copy2(ROOT / "scripts/__init__.py", target / "scripts/__init__.py")
    shutil.copytree(ROOT / "scripts/common", target / "scripts/common")
    return target


_NOTEBOOK_RUNNER = r"""
import json
import os
from pathlib import Path
import sys

from IPython.core.interactiveshell import InteractiveShell

repository = Path(sys.argv[1]).resolve()
notebook_path = repository / sys.argv[2]
os.chdir(repository)
notebook = json.loads(notebook_path.read_text(encoding="utf-8"))
shell = InteractiveShell.instance()

for cell_index, cell in enumerate(notebook["cells"]):
    if cell["cell_type"] != "code":
        continue
    source = "".join(cell["source"])
    source = "\n".join(
        line for line in source.splitlines()
        if not line.lstrip().startswith(("%", "!"))
    )
    # InteractiveShell has no GUI event-loop integration. A Jupyter kernel does,
    # so only this frontend-specific call is neutralized in the headless runner.
    source = source.replace("plt.ion()", "")
    result = shell.run_cell(source, store_history=False, silent=False)
    error = result.error_before_exec or result.error_in_exec
    if error is not None:
        raise RuntimeError(
            f"Notebook {notebook_path} failed in cell {cell_index}"
        ) from error
"""


@pytest.mark.extensive
@pytest.mark.parametrize(
    "notebook_path",
    NOTEBOOK_PATHS,
    ids=lambda path: str(path.relative_to(ROOT)),
)
def test_notebook_executes_in_isolated_repository(
    notebook_path: Path,
    isolated_notebook_repository: Path,
) -> None:
    """Execute every scientific cell without writing into the source tree."""
    relative_path = notebook_path.relative_to(ROOT)
    environment = os.environ.copy()
    environment["MPLBACKEND"] = "Agg"
    environment["PYAGES_RESULTS_DIR"] = str(isolated_notebook_repository / "results")
    completed = subprocess.run(
        [
            sys.executable,
            "-c",
            _NOTEBOOK_RUNNER,
            str(isolated_notebook_repository),
            str(relative_path),
        ],
        cwd=isolated_notebook_repository,
        env=environment,
        capture_output=True,
        text=True,
        timeout=1_800,
        check=False,
    )

    assert completed.returncode == 0, (
        f"Notebook execution failed: {relative_path}\n"
        f"stdout:\n{completed.stdout}\n"
        f"stderr:\n{completed.stderr}"
    )
