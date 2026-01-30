# Configuration Reference

PyAge uses YAML configuration files to control workflows. This reference documents all available options.

## Workflow Configuration (launcher.py)

Used with `python scripts/launcher.py --params <config.yaml>`

### Dataset Section

```yaml
dataset:
  name: ploemeur_F09_2010.txt      # Required: input data filename
  year: 2010                        # Optional: reference year for labels
  data_dir: examples/ploemeur/data  # Required: path to data directory
  verbose: true                     # Optional: print diagnostics (default: false)
```

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `name` | string | Yes | Input data filename |
| `year` | number | No | Reference year for metadata |
| `data_dir` | string | Yes | Path to data directory (relative to repo root) |
| `verbose` | boolean | No | Enable verbose output (default: false) |

**Tracer selection rule:** the `element` column in your data file determines
which tracers are used. Each element must match a tracer folder under
`data_core/data_tracer/` (or a site-specific tracer directory).

### LPM Section

```yaml
lpm:
  model_name: dirac_double          # Required: LPM model identifier
  data_directory: data_core/data_lpm  # Required: LPM parameters directory
```

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `model_name` | string | Yes | LPM model name (see available models below) |
| `data_directory` | string | Yes | Directory containing `<model>/params.yaml` files |

Tip: for quick overrides without editing YAML, you can use CLI options:
`pyage run --lpm <name> --mh-nsteps <n> --data-name <file> --data-dir <dir> config.yaml`

**Available LPM models:**

| Model | Parameters | Description |
|-------|------------|-------------|
| `dirac` | `tau` | Single age (piston flow) |
| `dirac_double` | `mu1`, `mu2`, `rate` | Binary mixing of two ages |
| `exp` | `mu` | Exponential distribution |
| `exp_shifted` | `mu`, `shift` | Shifted exponential |
| `ig` | `mu`, `sigma` | Inverse Gaussian |
| `ig_shifted` | `mu`, `sigma`, `shift` | Shifted inverse Gaussian |
| `gamma` | `mu`, `sigma` | Gamma distribution |
| `uniform` | `a`, `b` | Uniform distribution |

### Run Section

```yaml
run:
  reachable_concentrations: true    # Explore feasible concentration domain
  objective_function: true          # Map objective function on parameter grid
  calibration_metropolis_hastings: true  # Run MCMC calibration
  calibration_simplex: true         # Run simplex/FUQ calibration
```

All fields are boolean, default `false`. Enable only the analyses you need.

### Reachable Concentrations Section

```yaml
reachable_concentrations:
  nmodels: 5000                     # Number of random samples
```

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `nmodels` | integer | 5000 | Number of parameter samples for exploration |

### Objective Function Section

```yaml
objective_function:
  nmodels: 10000                    # Grid resolution
```

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `nmodels` | integer | 10000 | Number of points in parameter grid |

### Metropolis-Hastings Section

```yaml
calibration_metropolis_hastings:
  nstep: 5000                       # MCMC iterations
  prior_option: false               # Use prior in likelihood
  likelihood: true                  # Use likelihood (should be true)
  monitor: false                    # Track acceptance statistics
  display_traj: false               # Plot parameter trajectories
```

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `nstep` | integer | 5000 | Number of MCMC iterations |
| `prior_option` | boolean | false | Include prior probability in acceptance |
| `likelihood` | boolean | true | Use likelihood function |
| `monitor` | boolean | false | Monitor and display acceptance rates |
| `display_traj` | boolean | false | Generate trajectory plots (slow) |

### Simplex Section

```yaml
calibration_simplex:
  init_multiples_n: 3               # Initial simplex multiplier
  fuq_n: 30                         # Forward UQ sample count
```

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `init_multiples_n` | integer | 3 | Number of initial simplex configurations |
| `fuq_n` | integer | 30 | Number of samples for forward uncertainty |

---

## Temporal Workflow Configuration (launcher_temporal.py)

Used with `python scripts/launcher_temporal.py --params <config.yaml>`

### Dataset Section

```yaml
dataset:
  file: examples/ploemeur_temporal/data/ori_ploemeur_F09_2005_2024.txt
  error_rel: 0.2                    # Relative error (20%)
```

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `file` | string | Yes | Path to multi-date concentration file |
| `error_rel` | number | No | Relative error to apply if error column is zero |

### LPM Models Section

```yaml
lpm_models:
  list: ["exp_shifted", "ig", "ig_shifted"]
  directory: data_core/data_lpm
```

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `list` | array | Yes | List of LPM models to evaluate |
| `directory` | string | Yes | LPM parameters directory |

### Workflow Section

```yaml
workflow:
  mode: span                        # 'span' or 'successive'
```

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `mode` | string | span | `span` = single calibration; `successive` = per-date |

### Calibration Section

```yaml
calibration:
  explo_res: 20                     # Systematic sampling resolution
  mh_nsteps: 1000                   # MCMC iterations
  burn_in: 0.2                      # Burn-in fraction (0-1)
  nskip: 10                         # Thinning interval
  lpm_number: 0                     # Output samples (0 = auto)
  seed_enabled: true                # Enable reproducible RNG
  seed: 12345                       # Random seed
```

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `explo_res` | integer | 20 | Grid resolution for systematic sampling |
| `mh_nsteps` | integer | 1000 | MCMC iterations |
| `burn_in` | number | 0.2 | Fraction of samples to discard |
| `nskip` | integer | 10 | Keep every nth sample (thinning) |
| `lpm_number` | integer | 0 | Number of output samples (0 = automatic) |
| `seed_enabled` | boolean | true | Use fixed random seed |
| `seed` | integer | 12345 | Random seed value |

### Figures Section

```yaml
figures:
  temporal: true                    # Time series plots
  distributions: true               # Parameter/concentration distributions
```

### Results Section

```yaml
results:
  use_default: true                 # Use default results directory
  directory: ""                     # Custom directory (if use_default: false)
```

---

## LPM Parameter Files (params.yaml)

Each LPM model has a `params.yaml` file in `data_core/data_lpm/<model>/`.

### Structure

```yaml
model: ig                           # Model identifier
version: 1                          # Configuration version

parameters:
  - name: mu                        # Parameter name (used in code)
    label: mean_age                 # Human-readable label
    unit: year                      # Physical unit
    description: "Mean of the distribution."
    bounds: [0.1, 70.0]            # Valid range [min, max]
    init: 10.0                      # Initial value for simplex
    step: 1.5                       # MH proposal step size
    prior:
      type: uniform                 # Prior distribution type
      min: 0.0                      # Prior minimum
      max: 100.0                    # Prior maximum
      unit: year

  - name: sigma
    label: std_age
    unit: year
    description: "Standard deviation parameter."
    bounds: [0.1, 70.0]
    init: 2.0
    step: 1.0
    prior:
      type: uniform
      min: 0.0
      max: 30.0
      unit: year

notes: "Optional notes about the model."
```

### Parameter Fields

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `name` | string | Yes | Internal parameter name |
| `label` | string | No | Display label |
| `unit` | string | No | Physical unit |
| `description` | string | No | Parameter description |
| `bounds` | array | Yes | `[min, max]` valid range |
| `init` | number | Yes | Initial value for optimization |
| `step` | number | Yes | MCMC proposal step size |
| `prior` | object | No | Prior distribution specification |

### Prior Distribution

```yaml
prior:
  type: uniform                     # Currently only 'uniform' supported
  min: 0.0                          # Prior minimum
  max: 100.0                        # Prior maximum
  unit: year                        # Unit (for documentation)
```

---

## Tracer Configuration (tracer.yaml)

Each tracer has a YAML file in `data_core/data_tracer/<tracer>/<tracer>.yaml`.

### Structure

```yaml
# Unit of concentration
unit: pptv

# Recharge configuration
recharge: true                      # Load from recharge.csv
# recharge_constant: 100.0          # Or use constant value

# Optional: Radioactive decay
# decay_time: 17.77                 # Half-life / ln(2) in years

# Optional: Geoproduction
# production_rate: 0.0              # In-situ production rate

# Date range (auto-detected from recharge.csv if recharge: true)
# datemin: 1940.0
# datemax: 2025.0
```

### Fields

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `unit` | string | Yes | Concentration unit (pptv, TU, pmC, etc.) |
| `recharge` | boolean | Yes* | Load from recharge.csv |
| `recharge_constant` | number | Yes* | Constant concentration (if no chronicle) |
| `decay_time` | number | No | Decay time constant (years) |
| `production_rate` | number | No | Geoproduction rate |
| `datemin` | number | No | Minimum valid date |
| `datemax` | number | No | Maximum valid date |

*Either `recharge: true` or `recharge_constant` must be specified.

### Recharge Chronicle (recharge.csv)

```csv
date,concentration
1940.0,0.01
1950.0,0.55
1960.0,10.20
...
```

- First column: decimal year
- Second column: atmospheric concentration

---

## Environment Variables

| Variable | Description | Default |
|----------|-------------|---------|
| `PYAGE_RESULTS_DIR` | Root directory for output files | `~/results/PyAge` |

Set on Windows:
```bash
setx PYAGE_RESULTS_DIR "D:\results\PyAge"
```

Set on Linux/macOS:
```bash
export PYAGE_RESULTS_DIR="/path/to/results"
```

---

## Tips

### Faster Runs (for Testing)

```yaml
reachable_concentrations:
  nmodels: 1000                     # Reduce samples

calibration_metropolis_hastings:
  nstep: 500                        # Fewer MCMC steps
```

### More Accurate Results (for Production)

```yaml
reachable_concentrations:
  nmodels: 20000                    # More samples

calibration_metropolis_hastings:
  nstep: 50000                      # More MCMC steps
  monitor: true                     # Check convergence
```

### Reproducible Results

```yaml
calibration:
  seed_enabled: true
  seed: 42                          # Fixed seed
```
