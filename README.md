# PyAges

PyAges is a research codebase for groundwater age modeling and tracer-based
calibration using lumped-parameter models (LPMs), convolution operators, and
inference workflows (e.g., Metropolis-Hastings and simplex-based approaches).
It provides reusable scientific components in `pyages/` and site-specific
workflows in `sites/`, with examples and regression tests to support validation.

Project status: **beta** (`0.1.0b1`). Public interfaces are documented and
tested, but feedback may still lead to explicitly documented changes before
the first stable release.

Release maturity follows this policy:

- **alpha**: exploratory behavior; features and interfaces may be incomplete;
- **beta**: intended features are usable and tested, but pre-1.0 interfaces may
  still change with a changelog entry;
- **release candidate**: proposed final artifact, changed only for blocking
  defects;
- **stable**: supported public contract, with compatibility managed according
  to semantic versioning.

The current code is beta because the installable workflows and validation gates
are in place, while broader natural-dataset qualification and final user
feedback remain prerequisites for `1.0.0`.

## Quick start

Create a user environment and install the qualified dependency set:

```
python -m venv .venv
python -m pip install -c install/constraints.txt -e .
```

The separate `install/environment.yml` file records the Python 3.12 /
SciPy 1.14.1 direct scientific baseline used by the historical article
campaign; it is not a bit-for-bit lock or the PyAges 1.0 user environment. See
`install/README.md` for the two workflows.

Installing PyAges enables the `pyages` CLI:

```
pyages --version
```

The distribution, Python import, and command all use the single identifier
`pyages`. The wheel contains the reusable library, its CLI,
and core model data. Repository examples and site studies remain in the Git
source tree. Once a release is available from the configured package index,
install it with:

```
python -m pip install pyages
```

No PyAges distribution is currently published on PyPI. After a beta or release
candidate is uploaded, pip users must opt into prereleases:

```
python -m pip install --pre pyages
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

From a source checkout, use the minimal templates under `examples/templates/`:

```
pyages run examples/templates/quickstart_single.yaml
pyages run --transient examples/templates/quickstart_temporal.yaml
```

## Installation and execution

Recommended (installed package):

```
python -m pip install -e .
```

This makes `import pyages` work from any directory and enables the CLI:

```
pyages check
pyages list lpms
pyages run examples/natural/ploemeur/exemple_ploemeur.yaml
```

The supported entry point is the installed `pyages` command. Direct execution
of repository files is not part of the public interface.

## CLI (pyages)

The CLI provides quick access to common workflows once the package is installed.

Main commands:
- `pyages check` : validate installation, data paths, LPM registry, tracers.
- `pyages list lpms|tracers` : list available models or tracers.
- `pyages run <config.yaml>` : run a YAML-driven workflow (single-date by default).
- `pyages run --transient <config.yaml>` : run the multi-date temporal workflow.
- `pyages new lpm|tracer ...` : scaffold a new model or tracer template.

Examples:
```
pyages check
pyages list lpms
pyages run examples/natural/ploemeur/exemple_ploemeur.yaml
pyages run --transient examples/natural/ploemeur_temporal/ploemeur_temporal.yaml
pyages run --lpm exp_shifted --mh-nsteps 5000 --data-name mydata.txt --data-dir examples/my_site/data my_config.yaml
pyages run --transient --lpm ig --mh-nsteps 2000 --data-file examples/my_site/data/ori_my_site_2005_2024.txt my_temporal.yaml
```

## Results directory

By default, results are written under:

```
<home>/results/PyAges
```

You can override the output root with an environment variable:

```
setx PYAGES_RESULTS_DIR "D:\results\PyAges"
```

(On Windows, `setx` persists across shells; for the current shell, also set
`$env:PYAGES_RESULTS_DIR = "D:\results\PyAges"`.)

## Repository layout (high level)

- `pyages/`: core library code (LPMs, tracers, convolution, calibration, config)
  - `pyages/lpm/`: lumped-parameter models, core distributions, and parameter I/O
  - `pyages/tracer/`: tracer chronologies and root tracer definitions
  - `pyages/convolution/`: convolution algorithms and tracer helpers
  - `pyages/concentrations/`: concentration data handling and time series helpers
  - `pyages/calibration/`: calibration methods, workflows, and objective functions
  - `pyages/config/`: validated configuration models, paths, and runtime helpers
  - `pyages/tools/`: plotting and miscellaneous utilities used across modules
- `data_core/`: shared model data for LPMs and tracers (not observations)
  - `data_core/data_lpm/`: LPM parameter files (`params.yaml`, bounds, etc.)
  - `data_core/data_tracer/`: tracer chronologies and recharge series
- `sites/`: site-specific workflows, data, and scripts (e.g., `ploemeur/`)
- `examples/`: runnable examples and their data (e.g., `holten/`, `ploemeur/`)
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
python -m sites.ploemeur.scripts.ploemeur_driver --params sites/ploemeur/params/ploemeur_full.yaml
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

- `examples/natural/ploemeur/exemple_ploemeur.yaml`
- `examples/natural/ploemeur_temporal/ploemeur_temporal.yaml`
- `examples/natural/holten/run_holten.py`

### Temporal MH launcher (multi-date concentrations)

There is a dedicated launcher that runs Metropolis-Hastings on a multi-date
concentration file (``ori_*.txt``) and produces temporal plots plus parameter
and concentration distributions:

```
pyages run --transient examples/natural/ploemeur_temporal/ploemeur_temporal.yaml
```

Supported modes:
- `span`: single calibration over the full time span
- `successive`: one calibration per observation date

Test data note:
- `tests/concentrations/test_concentration_chronicles_smoke.py` reads
  `examples/natural/ploemeur_temporal/data/ori_ploemeur_F09_2005_2024.txt` as its
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

## Workflows and diagnostics

The supported workflow entrypoints are:

- `pyages run`: single-date workflow driven by YAML.
- `pyages.workflows.temporal`: canonical multi-date MH workflow, exposed by `pyages run --transient`.
- `pyages check`: quick installation and data sanity check.

Repository-only research and benchmark commands are catalogued in
`scripts/README.md`; they are not public package entry points.

Expected outputs (under `<results_root>`):

- single-date workflow: `test_cases/<dataset_name>/`; method-specific plots and
  tables, including `concentration_times.png`, are written below
  `Metropolis_Hastings/` or `forward_uncertainty_quantification/`;
- temporal workflow:
  `<study_name>/<dataset_stem>/<mode>/<span_full-or-date>/<lpm_type>/`, where
  `study_name` defaults to `temporal`; Metropolis-Hastings plots and tables are
  below `Metropolis_Hastings/`.

## Notes

This is a research codebase; outputs and workflows evolve. If you change
behaviour intentionally, update the associated tests and golden files to keep
the regression suite stable.

The supported public surface and compatibility policy are documented in
`docs/reference/public-api.md`. Release changes are recorded in
`CHANGELOG.md`.

## License

PyAges is distributed under the CeCILL 2.1 license. The complete authoritative
texts are included in French in
[`LICENSE`](https://github.com/dreuzy/pyages/blob/main/LICENSE) and in English in
[`LICENSE.en`](https://github.com/dreuzy/pyages/blob/main/LICENSE.en). Source
files carry the SPDX identifier `CECILL-2.1`.

Copyright (c) 2021-2026 Centre national de la recherche scientifique (CNRS).
Jean-Raynald de Dreuzy is the principal author and contributor. See
[`COPYRIGHT`](https://github.com/dreuzy/pyages/blob/main/COPYRIGHT) for the
complete authorship and rights notice,
[`LICENSE`](https://github.com/dreuzy/pyages/blob/main/LICENSE) and
[`LICENSE.en`](https://github.com/dreuzy/pyages/blob/main/LICENSE.en) for the
license terms,
[`NOTICE-DATA.md`](https://github.com/dreuzy/pyages/blob/main/NOTICE-DATA.md) for
the separate provenance and terms of the data distributed with the project,
and
[`THIRD_PARTY_NOTICES.md`](https://github.com/dreuzy/pyages/blob/main/THIRD_PARTY_NOTICES.md)
for the direct dependency licence audit.
