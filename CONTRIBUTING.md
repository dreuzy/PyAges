# Contributing to PyAge

Install the project and development tools in an isolated environment:

```bash
python -m pip install -e ".[dev,docs]"
```

Before proposing a change, run:

```bash
python -m ruff check .
python -m pytest -q
python -m sphinx -W --keep-going -b html docs docs/_build/html
```

Keep reusable behavior under `pyage/`; keep site and article orchestration in
their dedicated directories. Do not commit generated results, local runner
configuration, credentials, or machine-specific paths.

Changes that intentionally affect scientific results must explain the reason,
update the relevant golden values, and include a migration or validation note.
Do not regenerate golden files merely to make a failing test pass.

Public interfaces are listed in `docs/reference/public-api.md`. Deprecate a
supported interface before removing it and record the change in `CHANGELOG.md`.
