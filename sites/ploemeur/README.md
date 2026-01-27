Ploemeur workflow - quick run

Run the main workflow with the default parameters:

```
python sites/ploemeur/scripts/ploemeur_driver.py
```

Run with a specific YAML (example: F09 only):

```
python sites/ploemeur/scripts/ploemeur_driver.py --params sites/ploemeur/params/ploemeur_F09.yaml
```

Run with the positional YAML path:

```
python sites/ploemeur/scripts/ploemeur_driver.py sites/ploemeur/params/ploemeur_full.yaml
```


Overview

This directory contains the Ploemeur site workflow, inputs, and postprocessing tools.
The workflow is driven by YAML files and executed via `ploemeur_driver.py`.


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
  - `temp/`: intermediate files produced by the workflow (recreated each run)
- `params_LPM/`: site-level LPM parameter files (optional alternative to `data_core/data_LPM`)
- `postprocessing/`: plotting and comparison utilities
- `docs/`: site-specific notes (if any)


Typical workflow (data)

```
Excel / raw files -> data/brut
data/brut + manual edits -> data/ori
workflow generates -> data/temp (intermediate)
```

See `sites/ploemeur/data/README.md` for details about data provenance.


Choosing LPM parameter files

In `params/ploemeur_full.yaml`, set:

```
lpm_models:
  directory: data_core/data_LPM
```

or point to the site-specific parameters:

```
lpm_models:
  directory: sites/ploemeur/params_LPM
```


Notes

- Results are written under the global results directory configured by
  `PYAGE_RESULTS_DIR` (see the root `README.md`).
