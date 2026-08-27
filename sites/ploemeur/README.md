Ploemeur workflow - quick run

Run the main workflow with the default parameters:

```
python -m sites.ploemeur.scripts.ploemeur_driver
```

Run with a specific YAML (example: F09 only):

```
python -m sites.ploemeur.scripts.ploemeur_driver --params sites/ploemeur/params/ploemeur_F09.yaml
```

Overview

This directory contains the Ploemeur site workflow, inputs, and postprocessing tools.
The workflow is driven by YAML files and executed via `ploemeur_driver.py`.
The driver now calls the site API (`sites/ploemeur/site_api.py`), which implements
the shared `BaseSite` interface (`pyage/site/base_site.py`).


Directory map

- `params/`: main workflow configuration files (YAML)
  - `ploemeur_full.yaml`: full workflow configuration
  - `ploemeur_F09.yaml`: minimal example (F09 only)
  - `ploemeur_observations.yaml`: observation ranges per well
  - `prior_pipeline_presets.yaml`: shared pipeline definitions
- `workflows/`: workflow engine and helpers
  - `ploemeur_workflow.py`: main workflow logic
  - `job_builder.py`: builds job lists from YAML
  - `path_helpers.py`: common path utilities
- `scripts/`: entrypoints for running the workflow
  - `ploemeur_driver.py`: main launcher
- `data/`: observation data
  - `brut/`: raw inputs (including original Excel files)
  - `ori/`: cleaned/curated time series generated from brut
- Runtime observation selections are created in an isolated operating-system
  temporary directory and removed after each workflow execution.
- `params_lpm/`: site-level LPM parameter files (optional alternative to `data_core/data_lpm`)
- `studies/`: self-contained, reproducible scientific studies
  - `HYP-26-0172/`: long-term CFC article, including its matrix, configurations,
    figure builders, scientific map, and archived development material
- `docs/`: site-specific notes (if any)


Typical workflow (data)

```
Excel / raw files -> data/brut
data/brut + manual edits -> data/ori
workflow generates -> OS temp/pyage-ploemeur-* (removed after execution)
```

See `sites/ploemeur/data/README.md` for details about data provenance.

Article-specific configurations, journal export rules, figure numbers, and
scientific claims live in the corresponding `studies/` subdirectory.


Choosing LPM parameter files

In `params/ploemeur_full.yaml`, set:

```
lpm_models:
  directory: data_core/data_lpm
```

or point to the site-specific parameters:

```
lpm_models:
  directory: sites/ploemeur/params_lpm
```


Notes

- Results are written under the global results directory configured by
  `PYAGE_RESULTS_DIR` (see the root `README.md`).
