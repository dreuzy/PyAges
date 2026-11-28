# Complete external LPM plugin example

This directory is a standalone Python package. It provides `bounded_power`, a
bounded power-law transit-time distribution implemented directly with NumPy,
without `scipy.stats`. The example keeps the model code, packaged parameter
schema, entry point, and scientific tests together.

## Try the example

From this directory, run:

```console
python -m pip install -e .
pyages list lpms
pyages check lpm bounded_power
pytest
```

The editable installation records the `pyages.lpms` entry point from
`pyproject.toml`. Listing models reads that metadata without importing the
plugin. PyAges imports `model:definition` only when `bounded_power` is built or
checked.

## Read the files in this order

1. `pyproject.toml` declares the package, dependencies, entry point, and YAML
   package data.
2. `src/pyages_lpm_bounded_power/model.py` contains every probability method and
   the small `LpmDefinition` registration object.
3. `src/pyages_lpm_bounded_power/data_lpm/bounded_power/params.yaml` defines
   domains, calibration ranges, initial values, proposal steps, and priors.
4. `tests/test_model.py` checks exact analytical values and the partial moment
   required by continuous convolution.

## Start a different plugin

Generate a fresh project instead of copying names by hand:

```console
pyages new lpm my_model --layout plugin --base root
```

Use `--base scipy` when a suitable `scipy.stats` distribution already exists.
Whichever base you choose, replace the starter formulas, parameter ranges, and
tests with scientifically justified values before using the model in a study.

See `docs/user-guide/external-lpm-quickstart.md` for the shortest guided path
and `docs/user-guide/external-lpm-models.md` for the complete plugin contract.
