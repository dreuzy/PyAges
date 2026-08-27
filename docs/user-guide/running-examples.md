# Running Examples

PyAge includes several example workflows demonstrating different use cases. This guide walks through each example and explains what they do.

## Available Examples

| Example | Description | Script |
|---------|-------------|--------|
| Synthetic recovery | Known-truth parameter recovery | `run_lpm_recovery_single_date.py` |
| Ploemeur | Single-date calibration | `pyage run` |
| Fontainebleau | Single-date calibration (different site) | `run_fontainebleau.py` |
| Holten | Example-local preparation, benchmark, and calibration reuse | `run_holten.py` |
| Ploemeur Temporal | Multi-date time series analysis | `pyage run --transient` |
| Albuquerque | Mixed young/old field example | `pyage run` |

For a minimal, fast run, use the templates under `examples/templates/`.

## Example 1: Ploemeur (Single-Date Calibration)

The Ploemeur example demonstrates a complete calibration workflow for a single sampling date.

### Run the Example

```bash
pyage run examples/natural/ploemeur/exemple_ploemeur.yaml
```

### What It Does

1. **Reachable Concentrations**: Explores which concentrations are physically achievable with the chosen LPM
2. **Objective Function Mapping**: Evaluates the misfit across the parameter space
3. **Metropolis-Hastings Calibration**: MCMC sampling to estimate parameter distributions
4. **Simplex Calibration**: Optimization-based calibration with forward uncertainty quantification

### Configuration File

```yaml
# examples/natural/ploemeur/exemple_ploemeur.yaml

dataset:
  name: ploemeur_F09_2010.txt      # Input data file
  year: 2010                        # Reference year
  data_dir: examples/natural/ploemeur/data  # Data directory
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

Results are saved to `~/results/PyAge/test_cases/ploemeur_F09_2010.txt/` by
default because the dataset filename is the result-directory identifier:

| File | Description |
|------|-------------|
| `concentrations.txt` | Normalized copy of the input observations |
| `reachable_concentrations/c_reach.txt` | Reachable tracer concentrations when that analysis is enabled |
| `objective_function_grid.txt` | Sampled objective surface when that analysis is enabled |
| `<method>/parameters_calibration.txt` | Effective sampler or optimizer settings |
| `<method>/results_calibration.txt` | Timing and acceptance or termination information |
| `<method>/lpm_dist_calibrated.txt` | Retained samples for non-simplex calibration methods |
| `<method>/lpm_stats_calibrated.txt` | Descriptive sample statistics, not convergence diagnostics |
| `01_*.png`, `02_*.png`, `03_*.png` | Optional summary figures for enabled analyses |
| `result_manifest.json` | Completion status, provenance, and artifact hashes |

See {doc}`../reference/results` for the complete output contract and temporal
layout.

---

## Example 2: Fontainebleau

Fontainebleau now follows the same local-example style as Holten: a dedicated
runner orchestrates a lightweight pre-model benchmark for the site, then
delegates the calibration itself to the standard single-date launcher.

### Run the Example

```bash
python -m examples.natural.fontainebleau.run_fontainebleau
```

### Key Differences

- Different geographic site with different tracer measurements
- A local benchmark summary is written under `examples/natural/fontainebleau/generated/benchmark/`
- You can override the dataset or the LPM directly from the example runner

### Useful Options

```bash
python -m examples.natural.fontainebleau.run_fontainebleau --mode benchmark_only
python -m examples.natural.fontainebleau.run_fontainebleau --dataset fontainebleau_IMR
python -m examples.natural.fontainebleau.run_fontainebleau --lpm ig
```

---

## Example 3: Holten

Holten keeps its site-specific preparation and article comparison logic in the
example directory, but reuses the validated single-date launcher core for the
calibration itself. The prepared tracer directory is passed explicitly through
generated launcher YAML files instead of patching global paths at runtime. Its
tracer sources can be mixed per tracer: for example, `3H` and `kr85` can stay
example-local while `39Ar` comes from `data_core/data_tracer/39Ar`.

### Run the Example

```bash
python examples/natural/holten/run_holten.py
```

### Useful Options

```bash
python examples/natural/holten/run_holten.py --mode prepare_only
python examples/natural/holten/run_holten.py --mode calibration_only
python examples/natural/holten/run_holten.py --wells 59-05,73-29
```

### Outputs

- Prepared datasets and tracer histories under `examples/natural/holten/generated/benchmark/prepared/`
- Pre-model figures under `examples/natural/holten/generated/benchmark/pre_model/`
- Local 4-bin comparison tables and figures under `examples/natural/holten/generated/benchmark/four_bin/`
- Standard calibration outputs under the configured results root via `pyage run`

---

## Example 4: Ploemeur Temporal (Multi-Date Analysis)

The temporal example demonstrates calibration across multiple sampling dates.
`span` fits one stationary LPM to the complete record; `successive` performs
separate fits by observation date and can be used to investigate apparent
changes, subject to the assumptions and diagnostics of each fit.

### Run the Example

```bash
python -m examples.natural.ploemeur_temporal.run_ploemeur_temporal
```

### Configuration File

```yaml
# examples/natural/ploemeur_temporal/ploemeur_temporal.yaml

dataset:
  file: examples/natural/ploemeur_temporal/data/ori_ploemeur_F09_2005_2024.txt
  error_rel: 0.2                    # 20% relative error

lpm_models:
  list: ["exp_shifted", "ig", "ig_shifted"]  # Models to compare
  directory: data_core/data_lpm

workflow:
  mode: span                        # 'span' or 'successive'

calibration:
  explo_res: 20                     # Systematic sampling resolution
  mh_nsteps: 3000                   # MCMC steps
  burn_in: 0.2                      # Burn-in fraction
  nskip: 10                         # Thinning interval
  lpm_number: 0                     # Automatic plotted-posterior sample count
  seed_enabled: true
  seed: 12345                       # For reproducibility

figures:
  temporal: true                    # Generate time series plots
  distributions: true               # Generate distribution plots
  concentrations_2d: false          # Disable 2D concentration pair plots

results:
  study_name: ploemeur_temporal
  use_default: true
  directory: ""
```

### Workflow Modes

- **`span`**: Single calibration using all dates simultaneously
- **`successive`**: Separate calibration for each observation date

### Output Structure

Results depend on the selected workflow mode:

```
~/results/PyAge/ploemeur_temporal/
\\-- ori_ploemeur_F09_2005_2024/
    +-- span/
    |   \\-- span_full/
    |       +-- 00_observations_overview.png
    |       +-- exp_shifted/
    |       +-- ig/
    |       \\-- ig_shifted/
    \\-- successive/
        +-- date_2005/
        +-- date_2010/
        \\-- ...
```

The example notebook is `examples/natural/ploemeur_temporal/exemple_ploemeur_temporal.ipynb`.

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

Run `pyage list lpms` for the installed registry. The current source tree
contains `dirac`, `dirac_double`, `dirac_double_1_set`, `exp`, `exp_shifted`,
`gamma`, `ig`, `ig_shifted`, `mix_exp_shifted`, `shapefree_n_oldbin`,
`uniform`, and `weibull`.

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
pyage run examples/my_site/my_config.yaml
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
pyage run --transient examples/my_site/my_temporal.yaml
```

### 5) Add or update tracers (if needed)

If your `element` names are not available in `data_core/data_tracer/`, create a
new tracer configuration (see {doc}`adding-tracer`) and point your data file to
those tracer names.

### Adjust MCMC Settings

For more accurate results (slower):

```yaml
calibration_metropolis_hastings:
  nstep: 20000      # More iterations
  monitor: true     # Enable trajectory/acceptance monitoring
```

Treat this as a candidate run, not as a convergence certificate. For
publication, use independent chains and report split-$\hat R$, ESS, and Monte
Carlo uncertainty as described in {doc}`../science/inference`.

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
1. The `data_dir` path is correct (relative to the detected checkout root for
   repository examples, or to the configuration directory for a standalone
   project)
2. The input file exists in the specified location

### "Unknown LPM type"

Run `pyage list lpms` to see available LPM models.

### "Tracer not found"

Ensure the tracer name in your data file matches a directory in `data_core/data_tracer/`.

### Results not appearing

Check the results directory:
- Default: `~/results/PyAge/`
- Override with: `PYAGE_RESULTS_DIR` environment variable
