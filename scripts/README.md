# Scripts

Quick entrypoints for manual runs and sanity checks. These are **not** pytest
tests; they are intended for interactive use when validating workflows.

## Common usage

Activate the environment first:

```bash
conda activate pyage
```

Then run a script from the repository root, for example:

```bash
python scripts/launcher.py --params examples/ploemeur/exemple_ploemeur.yaml
python scripts/launcher_temporal.py --params examples/ploemeur_temporal/ploemeur_temporal.yaml
python scripts/run_system_check.py
python scripts/run_calibration_benchmark.py
```

### Example parameters

Single-date workflows (YAML-driven):

```bash
python scripts/launcher.py --params examples/ploemeur/exemple_ploemeur.yaml
python scripts/launcher.py --params examples/fontainebleau/exemple_fontainebleau.yaml
```

Temporal workflows (multi-date concentrations):

```bash
python scripts/launcher_temporal.py --params examples/ploemeur_temporal/ploemeur_temporal.yaml
```

## Output location

Results are written under the configured results root. By default:

```
<home>/results/PyAge
```

You can override this with `PYAGE_RESULTS_DIR` (see the root `README.md`).

## Script overview

- `launcher.py`  
  Single-date workflow launcher (systematic sampling + calibration) driven by YAML.
- `launcher_temporal.py`  
  Multi-date (chronicle) Metropolis-Hastings launcher driven by YAML.
- `run_system_check.py`  
  Lightweight end-to-end sanity check (LPM generation, tracers, and plotting).
- `run_calibration_benchmark.py`  
  Compare Metropolis-Hastings and forward-uncertainty quantification runs.

## Expected outputs

- `launcher.py`
  - Results under: `<results_root>/test_cases/<dataset_name>/`
  - Core calibration outputs:
    - `parameters_calibration.txt`
    - `results_calibration.txt`
    - `lpm_dist_calibrated.txt`
    - `lpm_histo_calibrated.txt`
    - `lpm_stats_calibrated.txt`
    - `lpm_param_dist_calibrated.txt`
  - Plots/tables from concentration time displays, including:
    - `concentration_times.png`
    - `concentrations_all_models.txt`
- `launcher_temporal.py`
  - Results under:
    `<results_root>/ploemeur_temporal/<dataset_stem>/<mode>/<date>/<lpm_type>/`
  - Core outputs:
    - `parameters_calibration.txt`
    - `results_calibration.txt`
    - `lpm_stats_calibrated.txt`
    - `lpm_param_dist_calibrated.txt`
    - `concentration_times.png`
    - `concentrations_all_models.txt`
    - `distributions.txt`
    - `distributions_stats.txt`
- `run_system_check.py`
  - Results under: `<results_root>/test/<check_name>/<timestamp>/`
  - Diagnostic plots + console summaries of generated models/tracers.
- `run_calibration_benchmark.py`
  - Results under:
    `<results_root>/test_calib_comp/<timestamp>/prec_<error>/<tracers>/<lpm>/<case>/`
  - Benchmark results comparing MH and FUQ runs (plots + tables).

## Troubleshooting

- **No figures appear**  
  Ensure the script enables plotting in the params and that your backend is
  available (e.g., run from a local session, not a headless environment).

- **Results are not written where expected**  
  Check the `PYAGE_RESULTS_DIR` environment variable. If unset, results go to
  `<home>/results/PyAge`.

- **`ModuleNotFoundError: global_parameters`**  
  Run scripts from the repository root so imports resolve correctly:
  `python scripts/<script>.py ...`

- **`FileNotFoundError` for data files**  
  Verify the YAML paths and that example datasets are present under
  `examples/<site>/data/`.
