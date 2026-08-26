# Contributing to PyAge

PyAge welcomes bug reports, documentation improvements, tests, and scientific
or software contributions through GitHub issues and pull requests. Public
users can propose changes, but cannot push to or delete repository content.

## Development setup

```bash
git clone https://github.com/dreuzy/pyage.git
cd pyage
python -m pip install -c install/constraints.txt -e ".[dev,docs,examples]"
```

Create a topic branch and keep each pull request focused on one coherent
change. Describe the motivation, validation performed, and any effect on
numerical results, datasets, public interfaces, or reproducibility.

## Required checks

Run the checks relevant to the change before opening a pull request:

```bash
python -m ruff check .
python -m ruff format --check .
python -m pytest -q
python -m sphinx -W --keep-going -b html docs docs/_build/html
```

Changes to validation infrastructure should also run
`python -m pytest -q validation/tracerlpm/benchmark/tests`. Changes affecting
long scientific calculations must describe the corresponding extensive tests
and evidence rather than silently replacing golden values.

## Scientific and data changes

- Explain changes to equations, parameterizations, tolerances, priors, random
  seeds, or numerical outputs.
- Update tests, scientific documentation, and reproducibility manifests
  together when their contract changes.
- Do not commit generated result directories, local runner configurations,
  credentials, personal data, or third-party publications without an explicit
  redistribution review.
- Preserve source attribution and transformation notes for every dataset.

## Review and licensing

All changes are reviewed through GitHub. By contributing, you agree that your
contribution is distributed under the repository's CeCILL 2.1 license and that
you have the right to submit any included code, text, or data.
