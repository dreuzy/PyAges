# Getting started

PyAge supports Python 3.12 through 3.14. Conda is convenient for a qualified
source environment; pip is sufficient for an installed release.

## Install from a source checkout

```bash
git clone https://gitlab.com/dreuzy/pyage.git
cd pyage
conda env create -f install/environment.yml
conda activate pyage
python -m pip install -e .
```

The reference Conda environment uses Python 3.12 and includes the dependencies
needed by examples and notebooks. Contributors should add the test,
documentation, and release tools:

```bash
python -m pip install -c install/constraints.txt -e ".[dev,docs,examples]"
```

The exact environment policy is in {doc}`../reference/install`.

## Verify the installation

```bash
pyage check
pyage list lpms
pyage list tracers
```

`pyage check` validates package data, the LPM registry, and tracer definitions.

## Run a small example

The templates avoid interactive figures and are suitable for a first check:

```bash
pyage run examples/templates/quickstart_single.yaml
pyage run --transient examples/templates/quickstart_temporal.yaml
```

For a configuration located inside a PyAge source checkout, relative paths are
resolved from the detected checkout root (the nearest parent containing both
`pyproject.toml` and `data_core`). For a standalone configuration outside a
checkout, they are resolved from the configuration directory. Absolute paths
are accepted in both cases.

Each workflow creates a structured result directory containing tabular results
and `result_manifest.json`; figures are optional. Continue with
{doc}`configuration` to adapt a dataset or {doc}`running-examples` for complete
study examples.
