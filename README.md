# PyAge

PyAge is a research codebase for groundwater age modeling and tracer-based
calibration using lumped-parameter models (LPMs), convolutions, and inference
workflows (e.g., Metropolis-Hastings and simplex-based approaches).

## Repository layout (high level)

- `sources/`: core library code (LPMs, tracers, convolutions, calibration).
- `core_data/`: shared model data for LPMs and tracers (not observations).
- `sites/`: site-specific workflows, data, and scripts (e.g., `ploemeur/`,
  `fontainebleau/`).
- `scripts/`: entrypoints and orchestration scripts.
- `tests/`: automated tests.
- `scripts/`: entrypoints, orchestration scripts, and notebooks.
- `docs/`: project documentation.
- `install/`: environment setup files.

## Data locations

- Core model data: `core_data/` (LPM parameter files, tracer chronologies).
- Observations by site: `sites/<site>/data/`.

## Running

Create the conda environment:

```
conda env create -f install/environment.yml
```

Run tests (example):

```
pytest
```
