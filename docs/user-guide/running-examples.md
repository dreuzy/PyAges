# Running Examples

PyAge includes several example workflows demonstrating different use cases. This guide walks through each example and explains what they do.

## Available Examples

| Example | Description | Script |
|---------|-------------|--------|
| Ploemeur | Single-date calibration | `launcher.py` |
| Fontainebleau | Single-date calibration (different site) | `launcher.py` |
| Ploemeur Temporal | Multi-date time series analysis | `launcher_temporal.py` |

For a minimal, fast run, use the templates under `examples/templates/`.

## Example 1: Ploemeur (Single-Date Calibration)

The Ploemeur example demonstrates a complete calibration workflow for a single sampling date.

### Run the Example

```bash
python scripts/launcher.py --params examples/ploemeur/exemple_ploemeur.yaml
```

### What It Does

1. **Reachable Concentrations**: Explores which concentrations are physically achievable with the chosen LPM
2. **Objective Function Mapping**: Evaluates the misfit across the parameter space
3. **Metropolis-Hastings Calibration**: MCMC sampling to estimate parameter distributions
4. **Simplex Calibration**: Optimization-based calibration with forward uncertainty quantification

### Configuration File

```yaml
# examples/ploemeur/exemple_ploemeur.yaml

dataset:
  name: ploemeur_F09_2010.txt      # Input data file
  year: 2010                        # Reference year
  data_dir: examples/ploemeur/data  # Data directory
  verbose: true

lpm:
  model_name: dirac_double          # LPM model to use
  data_directory: data_core/data_lpm

run:
  reachable_concentrations: true    # Explore feasible domain
  objective_function: true          # Map objective function
  calibration_metropolis_hastings: true  # Run MCMC
  calibration_simplex: true         # Run simplex optimization

reachable_concentrations:
  nmodels: 5000                     # Number of samples

objective_function:
  nmodels: 10000                    # Grid resolution

calibration_metropolis_hastings:
  nstep: 5000                       # MCMC iterations
  prior_option: false
  likelihood: true
  monitor: false
  display_traj: false

calibration_simplex:
  init_multiples_n: 3               # Initial simplex size
  fuq_n: 30                         # Forward UQ samples
```

### Output Files

Results are saved to `~/results/PyAge/test_cases/ploemeur_F09_2010/`:

| File | Description |
|------|-------------|
| `parameters_calibration.txt` | Calibrated parameter values |
| `results_calibration.txt` | Calibration summary statistics |
| `lpm_dist_calibrated.txt` | Calibrated age distribution |
| `lpm_stats_calibrated.txt` | Distribution statistics (mean, std, quartiles) |
| `concentration_times.png` | Concentration vs age plot |
| `concentrations_all_models.txt` | Model predictions for all tracers |

---

## Example 2: Fontainebleau

Similar to Ploemeur but with a different dataset.

### Run the Example

```bash
python scripts/launcher.py --params examples/fontainebleau/exemple_fontainebleau.yaml
```

### Key Differences

- Different geographic site with different tracer measurements
- May use different LPM models depending on the hydrogeological context

---

## Example 3: Ploemeur Temporal (Multi-Date Analysis)

The temporal example demonstrates calibration across multiple sampling dates, useful for studying temporal variations in groundwater age.

### Run the Example

```bash
python scripts/launcher_temporal.py --params examples/ploemeur_temporal/ploemeur_temporal.yaml
```

### Configuration File

```yaml
# examples/ploemeur_temporal/ploemeur_temporal.yaml

dataset:
  file: examples/ploemeur_temporal/data/ori_ploemeur_F09_2005_2024.txt
  error_rel: 0.2                    # 20% relative error

lpm_models:
  list: ["exp_shifted", "ig", "ig_shifted"]  # Models to compare
  directory: data_core/data_lpm

workflow:
  mode: span                        # 'span' or 'successive'

calibration:
  explo_res: 20                     # Systematic sampling resolution
  mh_nsteps: 1000                   # MCMC steps
  burn_in: 0.2                      # Burn-in fraction
  nskip: 10                         # Thinning interval
  seed_enabled: true
  seed: 12345                       # For reproducibility

figures:
  temporal: true                    # Generate time series plots
  distributions: true               # Generate distribution plots
  concentrations_2d: false          # Disable 2D concentration pair plots
```

### Workflow Modes

- **`span`**: Single calibration using all dates simultaneously
- **`successive`**: Separate calibration for each observation date

### Output Structure

Results are organized by date and model:

```
~/results/PyAge/ploemeur_temporal/
└── ori_ploemeur_F09_2005_2024/
    └── span/
        ├── 2005.0/
        │   ├── exp_shifted/
        │   ├── ig/
        │   └── ig_shifted/
        ├── 2010.0/
        │   └── ...
        └── ...
```

---

## Data Input Format

### Single-Date Format

The input file should be a tab or space-separated text file:

```
element     concentration   error   unit    date
cfc11       245.5          10.0    pptv    2010.0
cfc12       520.3          15.0    pptv    2010.0
sf6         8.2            0.5     pptv    2010.0
```

Required columns:
- `element`: Tracer name (must match names in `data_core/data_tracer/`)
- `concentration`: Measured value
- `error`: Measurement uncertainty (absolute)
- `unit`: Concentration unit
- `date`: Sampling date (decimal year)

### Multi-Date Format

Same format but with multiple dates:

```
element     concentration   error   unit    date
cfc11       250.0          10.0    pptv    2005.0
cfc11       245.5          10.0    pptv    2010.0
cfc11       240.0          10.0    pptv    2015.0
sf6         7.5            0.5     pptv    2005.0
sf6         8.2            0.5     pptv    2010.0
sf6         9.0            0.5     pptv    2015.0
```

---

## Customizing Examples

### Change the LPM Model

Edit the `lpm.model_name` field:

```yaml
lpm:
  model_name: ig  # Use inverse Gaussian instead
```

Available models: `dirac`, `dirac_double`, `exp`, `exp_shifted`, `ig`, `ig_shifted`, `gamma`, `uniform`

---

## Add Your Own Data File (choose LPM + tracers)

This is the recommended workflow to analyze a new dataset with a chosen LPM
and tracer set.

### 1) Prepare your data file

Create a tab- or space-separated file with the required columns:

```
element     concentration   error   unit    date
cfc11       245.5          10.0    pptv    2010.0
cfc12       520.3          15.0    pptv    2010.0
sf6         8.2            0.5     pptv    2010.0
```

Each `element` value must match a tracer name found under
`data_core/data_tracer/` (or a site-specific tracer directory).

### 2) Choose your LPM model

Pick a model name from the registry (e.g., `exp`, `ig`, `exp_shifted`) and
ensure its parameter files exist under `data_core/data_lpm/<model>/params.yaml`.

### 3) Create a YAML config (single-date)

```
dataset:
  name: my_site_2010.txt
  year: 2010
  data_dir: examples/my_site/data

lpm:
  model_name: exp_shifted
  data_directory: data_core/data_lpm

run:
  reachable_concentrations: true
  calibration_metropolis_hastings: true
  calibration_simplex: false
```

Run:
```
python scripts/launcher.py --params examples/my_site/my_config.yaml
```

### 4) Multi-date variant (temporal)

If your file contains multiple dates, use the temporal launcher:

```
dataset:
  file: examples/my_site/data/ori_my_site_2005_2024.txt
  error_rel: 0.2

lpm_models:
  list: ["exp_shifted", "ig"]
  directory: data_core/data_lpm

workflow:
  mode: span
```

Run:
```
python scripts/launcher_temporal.py --params examples/my_site/my_temporal.yaml
```

### 5) Add or update tracers (if needed)

If your `element` names are not available in `data_core/data_tracer/`, create a
new tracer configuration (see `adding-tracer.md`) and point your data file to
those tracer names.

### Adjust MCMC Settings

For more accurate results (slower):

```yaml
calibration_metropolis_hastings:
  nstep: 20000      # More iterations
  monitor: true     # Enable trajectory monitoring
```

For quick testing (faster):

```yaml
calibration_metropolis_hastings:
  nstep: 1000       # Fewer iterations
```

### Disable Specific Analyses

```yaml
run:
  reachable_concentrations: false   # Skip this step
  objective_function: false         # Skip this step
  calibration_metropolis_hastings: true
  calibration_simplex: false        # Skip this step
```

---

## Troubleshooting

### "FileNotFoundError: data file not found"

Check that:
1. The `data_dir` path is correct (relative to repo root)
2. The input file exists in the specified location

### "Unknown LPM type"

Run `python scripts/run_system_check.py` to see available LPM models.

### "Tracer not found"

Ensure the tracer name in your data file matches a directory in `data_core/data_tracer/`.

### Results not appearing

Check the results directory:
- Default: `~/results/PyAge/`
- Override with: `PYAGE_RESULTS_DIR` environment variable
