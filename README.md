# PyAge

PyAge is a research codebase for groundwater age modeling and tracer-based
calibration using lumped-parameter models (LPMs), convolution operators, and
inference workflows (e.g., Metropolis-Hastings and simplex-based approaches).
It provides reusable scientific components in `sources/` and site-specific
workflows in `sites/`, with examples and regression tests to support validation.

## Quick start

Create the conda environment:

```
conda env create -f install/environment.yml
conda activate pyage
```

Run the full test suite:

```
python run_tests.py
```

Update golden values (when intentionally changing outputs):

```
python run_tests.py update
```

## Results directory

By default, results are written under:

```
<home>/results/PyAge
```

You can override the output root with an environment variable:

```
setx PYAGE_RESULTS_DIR "D:\results\PyAge"
```

(On Windows, `setx` persists across shells; for the current shell, also set
`$env:PYAGE_RESULTS_DIR = "D:\results\PyAge"`.)

## Repository layout (high level)

- `sources/`: core library code (LPMs, tracers, convolution, calibration, config)
  - `sources/convolution/`: convolution algorithms and tracer helpers
  - `sources/concentrations/`: concentration data handling and time series helpers
  - `sources/config/`: shared configuration (paths, runtime helpers, bootstrap)
- `data_core/`: shared model data for LPMs and tracers (not observations)
  - `data_core/data_LPM/`: LPM parameter files (`params.yaml`, bounds, etc.)
  - `data_core/data_tracer/`: tracer chronologies and recharge series
- `sites/`: site-specific workflows, data, and scripts (e.g., `ploemeur/`)
- `examples/`: runnable examples and their data (e.g., `fontainebleau/`, `ploemeur/`)
- `scripts/`: entrypoints and orchestration scripts
- `tests/`: automated tests and fixtures
- `docs/`: architecture notes and refactoring plans
- `install/`: environment setup files

## Data locations

- Core model data: `data_core/` (LPM parameter files, tracer chronologies).
- Site observations: `sites/<site>/data/` (raw + curated datasets).
- Example datasets: `examples/<site>/data/`.
- Test fixtures: `tests/data/` (small files used by tests).

## Running site workflows (Ploemeur)

The Ploemeur workflow is parameterized by YAML files:

- `sites/ploemeur/params/ploemeur_full.yaml`
- `sites/ploemeur/params/ploemeur_observations.yaml`
- `sites/ploemeur/params/prior_pipeline_presets.yaml`

Run the workflow:

```
python sites/ploemeur/scripts/ploemeur_driver.py --params sites/ploemeur/params/ploemeur_full.yaml
```

Key YAML sections:

- `workflows`: which prior pipeline presets to execute
- `observations`: wells, date ranges, and relative concentration errors
- `calibration`: MH step counts, sampling resolution, output sampling count
- `execution`: parallel options
- `lpm_models`: LPM model lists, optional per‑well overrides, and LPM params directory

The LPM parameter directory can point to `data_core/data_LPM` or to a
site-specific directory such as `sites/ploemeur/params_LPM`.

## Running examples

Example runners live under `examples/<site>/` and read their own YAML configs.
For instance, see:

- `examples/ploemeur/exemple_ploemeur.yaml`
- `examples/fontainebleau/exemple_fontainebleau.yaml`
- `examples/ploemeur_temporal/ploemeur_temporal.yaml`

### Temporal MH launcher (multi-date concentrations)

There is a dedicated launcher that runs Metropolis-Hastings on a multi-date
concentration file (``ori_*.txt``) and produces temporal plots plus parameter
and concentration distributions:

```
python scripts/launcher_temporal.py --params examples/ploemeur_temporal/ploemeur_temporal.yaml
```

Supported modes:
- `span`: single calibration over the full time span
- `successive`: one calibration per observation date

Test data note:
- `tests/concentrations/test_concentration_chronicles_smoke.py` reads
  `examples/ploemeur_temporal/data/ori_ploemeur_F09_2005_2024.txt` as its
  input dataset.

## Tests and golden files

Tests are under `tests/`. Some checks are “golden” regressions that compare
aggregated outputs against stored values in `tests/golden/`.

Common commands:

```
python run_tests.py
python run_tests.py detail
python run_tests.py update
```

## Notes

This is a research codebase; outputs and workflows evolve. If you change
behaviour intentionally, update the associated tests and golden files to keep
the regression suite stable.
