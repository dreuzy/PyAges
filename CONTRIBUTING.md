# Contributing to PyAges

PyAges welcomes bug reports, documentation improvements, tests, and scientific
or software contributions through GitHub issues and pull requests. Public
users can propose changes, but cannot push to or delete repository content.

## Development setup

```bash
git clone https://github.com/dreuzy/PyAges.git
cd pyages
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
python -m pyright
python -m scripts.maintenance.check_qualified_docstrings
python -m pytest -q
python -m sphinx -W --keep-going -b html docs docs/_build/html
```

The dedicated Ruff command applies the NumPy docstring convention to the
qualified calibration and workflow-runtime surface. Its scope is intentionally
expanded progressively as legacy modules are brought under the same contract.

The [testing guide](https://pyage-gw.readthedocs.io/en/latest/dev/testing.html)
explains the standard, extensive, coverage, TracerLPM, collection, and golden
scopes. The [continuous-integration reference](https://pyage-gw.readthedocs.io/en/latest/dev/ci.html)
maps every GitHub Actions job to its local command, trigger, and artifact.

Changes to validation infrastructure should also run
`python run_tests.py validation`. Changes affecting long scientific
calculations should run `python run_tests.py extensive` and must describe the
corresponding evidence rather than silently replacing golden values. After
adding, moving, parametrizing, or re-marking tests, regenerate the committed
inventory with `python -m scripts.maintenance.generate_test_inventory`.

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
