# Editor and IDE setup

PyAges does not require a particular editor. Always select the repository's
`.venv` interpreter and let the editor discover pytest from `tests/`. The
tracked `.editorconfig` supplies UTF-8, line-ending, whitespace, and indentation
defaults to compatible editors.

## VS Code

Select **Python: Select Interpreter** and choose:

- Windows: `.venv/Scripts/python.exe`
- macOS/Linux: `.venv/bin/python`

The repository intentionally ignores `.vscode/` because debugger paths and
personal extensions vary by workstation. A useful local `settings.json` base
on Windows is:

```json
{
  "python.defaultInterpreterPath": "${workspaceFolder}/.venv/Scripts/python.exe",
  "python.terminal.activateEnvironment": true,
  "python.testing.pytestArgs": ["tests"],
  "python.testing.pytestEnabled": true,
  "python.testing.unittestEnabled": false
}
```

Use `.venv/bin/python` for `python.defaultInterpreterPath` on macOS/Linux. Do
not add source roots that do not exist: the editable installation and workspace
root already make `pyages`, `scripts`, and maintained site modules importable.

For a CLI debug configuration, launch the module `pyages.cli.main` with, for
example, these arguments:

```text
run examples/templates/quickstart_single.yaml
```

Set `MPLBACKEND=Agg` for non-interactive runs. Set `PYAGES_RESULTS_DIR` to an
external scratch directory when a debugging session should not use the normal
result root.

## Static feedback

Ruff is the authoritative formatter and linter; editor integrations are a
convenience and must use the version installed in `.venv`. Pyright is
progressive: a clean editor does not imply that every historical module is
already in the qualified type-checking set. The exact set is listed under
`[tool.pyright]` in `pyproject.toml`.

Run the repository commands before relying on editor status alone:

```bash
python -m scripts.maintenance.check_dev quick
python -m pytest -q tests/<area>
```
