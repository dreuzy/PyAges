# Getting started

PyAges supports Python 3.12 through 3.14. The portable pip constraints are the
qualified user baseline; the Conda file intentionally preserves the distinct
Python 3.12 environment used by the historical article campaign.

## Install from a source checkout

```bash
git clone https://github.com/dreuzy/PyAges.git
cd pyages
python -m venv .venv
source .venv/bin/activate
python -m pip install -c install/constraints.txt -e .
```

On Windows PowerShell, activate the environment with
`.venv\\Scripts\\Activate.ps1`. Contributors should add the test,
documentation, and release tools:

```bash
python -m pip install -c install/constraints.txt -e ".[dev,docs,examples]"
```

The exact environment policy is in {doc}`../reference/install`.

To reproduce the historical article stack instead, use
`install/environment.yml` and activate `pyages-article-reproduction`. That
environment retains SciPy 1.14.1 and must not be described as the PyAges 1.0
user environment.

## Verify the installation

```bash
pyages check
pyages list lpms
pyages list tracers
```

`pyages check` validates package data, the LPM registry, and tracer definitions.

## Run a small example

The templates avoid interactive figures and are suitable for a first check:

```bash
pyages run examples/templates/quickstart_single.yaml
pyages run examples/templates/quickstart_temporal.yaml
```

For a configuration located inside a PyAges source checkout, relative paths are
resolved from the detected checkout root (the nearest parent containing both
`pyproject.toml` and `data_core`). For a standalone configuration outside a
checkout, they are resolved from the configuration directory. Absolute paths
are accepted in both cases.

Each workflow creates a structured result directory containing tabular results
and `result_manifest.json`; figures are optional. Continue with
{doc}`configuration` to adapt a dataset or {doc}`running-examples` for complete
study examples. The normative directory, table, and manifest schemas are in
{doc}`../reference/outputs`.
