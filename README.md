# PyAge

PyAge is a research codebase for groundwater age modeling and tracer-based
calibration using lumped-parameter models (LPMs), convolution operators, and
inference workflows (e.g., Metropolis-Hastings and simplex-based approaches).
It provides reusable scientific components in `pyage/` and site-specific
workflows in `sites/`, with examples and regression tests to support validation.

## Quick start

Create the conda environment:

```
conda env create -f install/environment.yml
conda activate pyage
```

Install PyAge (enables the `pyage` CLI):

```
pip install -e .
```

Run the full test suite:

```
python run_tests.py
```

Update golden values (when intentionally changing outputs):

```
python run_tests.py update
```

## Quickstart (fast, no interactive plots)

Use the minimal templates under `examples/templates/`:

```
python scripts/launcher.py --params examples/templates/quickstart_single.yaml
python scripts/launcher_temporal.py --params examples/templates/quickstart_temporal.yaml
```

## Execution modes (installed vs repo direct)

Recommended (installed package):

```
pip install -e .
```

This makes `import pyage` work from any directory and enables the CLI:

```
pyage check
pyage list lpms
pyage run examples/ploemeur/exemple_ploemeur.yaml
```

Repo-direct (no install):
- You can still run scripts from the repo (e.g. `python scripts/launcher.py ...`).
- Entry points include a small bootstrap fallback to add the repo root to `sys.path`
  when `pyage` is not installed.

## CLI (pyage)

The CLI provides quick access to common workflows once the package is installed.

Main commands:
- `pyage check` : validate installation, data paths, LPM registry, tracers.
- `pyage list lpms|tracers` : list available models or tracers.
- `pyage run <config.yaml>` : run a YAML-driven workflow (single-date by default).
- `pyage run --transient <config.yaml>` : run the multi-date temporal workflow.
- `pyage new lpm|tracer ...` : scaffold a new model or tracer template.

Examples:
```
pyage check
pyage list lpms
pyage run examples/ploemeur/exemple_ploemeur.yaml
pyage run --transient examples/ploemeur_temporal/ploemeur_temporal.yaml
pyage run --lpm exp_shifted --mh-nsteps 5000 --data-name mydata.txt --data-dir examples/my_site/data my_config.yaml
pyage run --transient --lpm ig --mh-nsteps 2000 --data-file examples/my_site/data/ori_my_site_2005_2024.txt my_temporal.yaml
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

- `pyage/`: core library code (LPMs, tracers, convolution, calibration, config)
  - `pyage/lpm/`: lumped-parameter models, core distributions, and parameter I/O
  - `pyage/tracer/`: tracer chronologies and root tracer definitions
  - `pyage/convolution/`: convolution algorithms and tracer helpers
  - `pyage/concentrations/`: concentration data handling and time series helpers
  - `pyage/calibration/`: calibration methods, workflows, and objective functions
  - `pyage/config/`: shared configuration (paths, runtime helpers, bootstrap)
  - `pyage/observations/`: generic dataset loaders and observation helpers
  - `pyage/tools/`: plotting and miscellaneous utilities used across modules
- `data_core/`: shared model data for LPMs and tracers (not observations)
  - `data_core/data_lpm/`: LPM parameter files (`params.yaml`, bounds, etc.)
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

If you omit `--params`, the driver defaults to
`sites/ploemeur/params/ploemeur_full.yaml`.

Key YAML sections:

- `workflows`: which prior pipeline presets to execute
- `observations`: wells, date ranges, and relative concentration errors
- `calibration`: MH step counts, sampling resolution, output sampling count
- `execution`: parallel options
- `lpm_models`: LPM model lists, optional per-well overrides, and LPM params directory

The LPM parameter directory can point to `data_core/data_lpm` or to a
site-specific directory such as `sites/ploemeur/params_lpm`.

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

Tests are under `tests/`. Some checks are "golden" regressions that compare
aggregated outputs against stored values in `tests/golden/`.

Common commands:

```
python run_tests.py
python run_tests.py detail
python run_tests.py update
```

Run extensive tests (opt-in):

```
pytest -q tests --run-extensive
```

## Scripts (manual entrypoints)

Manual scripts live under `scripts/` and are intended for interactive use
outside pytest. The main entrypoints are:

- `scripts/launcher.py`: single-date workflow launcher (YAML-driven).
- `scripts/launcher_temporal.py`: multi-date MH launcher (YAML-driven).
- `scripts/run_system_check.py`: quick end-to-end sanity check.
- `scripts/run_calibration_benchmark.py`: MH vs FUQ comparison run.

Expected outputs (under `<results_root>`):

- `launcher.py`: `test_cases/<dataset_name>/` (calibration files + `concentration_times.png`)
- `launcher_temporal.py`: `ploemeur_temporal/<dataset_stem>/<mode>/<date>/<lpm_type>/`
  (calibration files + temporal plots/tables)
- `run_system_check.py`: `test/<check_name>/<timestamp>/`
- `run_system_check.py` supports `--params <file.yaml>` to override defaults.
- `run_calibration_benchmark.py`: `test_calib_comp/<timestamp>/prec_<error>/<tracers>/<lpm>/<case>/`

See `scripts/README.md` for example commands and output locations.

## Notes

This is a research codebase; outputs and workflows evolve. If you change
behaviour intentionally, update the associated tests and golden files to keep
the regression suite stable.

## License

PyAge is distributed under the CeCILL license (Copyright CNRS).
