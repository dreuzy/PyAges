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
python scripts/launcher.py --params examples/templates/quickstart_single.yaml
python scripts/launcher_temporal.py --params examples/templates/quickstart_temporal.yaml
python scripts/run_system_check.py
python scripts/run_system_check.py --params configs/system_check.yaml
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
- `new_component.py`
  Template generator for creating new LPMs or tracers.

---

## Add a New Data File (choose LPM + tracers)

1) Put your data file under a folder you control (e.g. `examples/my_site/data/`).
   The file must contain columns: `element`, `concentration`, `error`, `unit`, `date`.

2) Choose an LPM model with parameters in `data_core/data_lpm/<model>/params.yaml`.

3) Create a YAML config and run the launcher:

```bash
python scripts/launcher.py --params examples/my_site/my_config.yaml
```

Minimal YAML:
```yaml
dataset:
  name: my_site_2010.txt
  year: 2010
  data_dir: examples/my_site/data

lpm:
  model_name: exp_shifted
  data_directory: data_core/data_lpm
```

4) If the data contains multiple dates, use the temporal launcher:

```bash
python scripts/launcher_temporal.py --params examples/my_site/my_temporal.yaml
```

```yaml
dataset:
  file: examples/my_site/data/ori_my_site_2005_2024.txt
  error_rel: 0.2

lpm_models:
  list: ["exp_shifted", "ig"]
  directory: data_core/data_lpm

workflow:
  mode: span
```

5) Tracer names come from the `element` column. If you need new tracers,
   add them under `data_core/data_tracer/<tracer>/` (see `docs/user-guide/adding-tracer.md`).

---

## Creating New Components

The `new_component.py` script generates boilerplate files for new LPMs and tracers,
following project conventions automatically.

### Create a New LPM

```bash
python scripts/new_component.py lpm <name> [--params <p1,p2,...>] [--scipy <dist>]
```

**Options:**
- `--params`, `-p`: Comma-separated parameter names (default: `mu,sigma`)
- `--scipy`, `-s`: Scipy.stats distribution name (default: `norm`)

**Examples:**

```bash
# Weibull distribution with shape (k) and scale (lambda) parameters
python scripts/new_component.py lpm weibull --params k,lambda --scipy weibull_min

# Log-normal distribution
python scripts/new_component.py lpm lognormal --params mu,sigma --scipy lognorm

# Pareto distribution with single parameter
python scripts/new_component.py lpm pareto --params alpha --scipy pareto
```

**Generated files:**
- `pyage/lpm/models/LPM_<name>.py` — Python class with `@register_lpm` decorator
- `data_core/data_lpm/<name>/params.yaml` — Parameter bounds, init values, MCMC settings

**After creation:**
1. Edit the Python file to configure `_scipy_params()` for your distribution
2. Adjust parameter bounds and initial values in the YAML file
3. Run `python scripts/run_system_check.py` to verify

### Create a New Tracer

```bash
python scripts/new_component.py tracer <name> [options]
```

**Options:**
- `--unit`, `-u`: Concentration unit (default: `pptv`)
- `--decay`, `-d`: Enable radioactive decay section
- `--production`, `-g`: Enable geoproduction section
- `--no-recharge`: Use constant concentration instead of chronicle file

**Examples:**

```bash
# Standard tracer with recharge chronicle
python scripts/new_component.py tracer krypton85 --unit "Bq/L"

# Radioactive tracer (e.g., Argon-39)
python scripts/new_component.py tracer argon39 --unit "atoms/L" --decay

# Tracer with both decay and geoproduction (e.g., Carbon-14)
python scripts/new_component.py tracer carbon14 --unit pmC --decay --production

# Constant concentration tracer (no chronicle file)
python scripts/new_component.py tracer synthetic --unit pptv --no-recharge
```

**Generated files:**
- `data_core/data_tracer/<name>/<name>.yaml` — Tracer configuration
- `data_core/data_tracer/<name>/recharge.csv` — Sample recharge chronicle (replace with real data)

**After creation:**
1. Edit the YAML to set correct `decay_time` or `production_rate` if applicable
2. Replace `recharge.csv` with your actual atmospheric concentration data
3. Run `python scripts/run_system_check.py` to verify

### Notes

- **Reserved words**: Python reserved words (e.g., `lambda`) are automatically
  handled by adding a trailing underscore in the code (`lambda_`).
- **Conflict detection**: The script will error if files already exist.
- **Auto-discovery**: New LPMs are automatically registered via the `@register_lpm`
  decorator — no manual registration needed.

---

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
  - Optional config override: `python scripts/run_system_check.py --params <file.yaml>`
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
