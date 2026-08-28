# Configuration Reference

PyAges uses YAML configuration files to control workflows. This reference
documents all available options.

All user-facing configuration models are strict: an unknown section or field
is rejected rather than ignored. Type errors and violated numeric bounds are
reported before the scientific workflow starts.

Relative paths are resolved from the nearest checkout root containing both
`pyproject.toml` and `data_core` for configurations inside a source checkout.
For standalone configurations they are resolved from the configuration file's
directory. Absolute paths are unchanged.

## Single-date workflow configuration

Used with `pyages run <config.yaml>`.

### Dataset Section

```yaml
dataset:
  name: ploemeur_F09_2010.txt       # Input data filename
  label: Ploemeur F09               # Optional display label
  year: 2010                        # Reference year for labels/metadata
  data_dir: examples/natural/ploemeur/data  # Observation directory
  verbose: true                     # Print diagnostics
  missing_error_rel: 0.01           # Fill zero errors from tracer means
```

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `name` | string | No | Portable input filename as one path component (no separator, drive prefix, `.` or `..`); placeholder default `example_dataset` |
| `label` | string or null | No | Optional display label; default `null` |
| `year` | integer | No | Reference year for metadata; default `2010` |
| `data_dir` | path | No | Observation directory; placeholder default `examples/data` |
| `verbose` | boolean | No | Enable verbose output; default `true` |
| `missing_error_rel` | number | No | Fraction in `(0, 1)` of the tracer mean used only to replace zero input errors; default `0.01` |

The effective errors are written to `concentrations.txt`. The result manifest
also records `missing_error_rel` and every row changed by this policy; no
imputation occurs inside an optimization or MCMC loop.

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
| `model_name` | string | No | LPM model identifier as one path component; default `dirac_double` |
| `data_directory` | path | No | Directory containing `<model>/params.yaml`; default `data_core/data_lpm` |

### Tracer Data Override

The optional section below selects a site-specific tracer root. Omit it, or
leave the value null, to use the packaged `data_core/data_tracer` directory.

```yaml
tracers:
  data_directory: examples/natural/holten/prepared_tracers/data_tracer
```

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `data_directory` | path or null | `null` | Root containing one directory per tracer |

Tip: for quick overrides without editing YAML, you can use CLI options:
`pyages run --lpm <name> --mh-nsteps <n> --data-name <file> --data-dir <dir> config.yaml`

**Available LPM models:**

| Model | Parameters | Description |
|-------|------------|-------------|
| `dirac` | `mu` | Single age (piston flow) |
| `dirac_double` | `mu1`, `mu2`, `rate` | Binary mixing of two ages |
| `dirac_double_1_set` | `mufree`, `rate` | Constrained Double-Dirac variant with one free and one workflow-supplied fixed age |
| `exp` | `mu` | Exponential distribution |
| `exp_shifted` | `mu`, `shift` | Shifted exponential |
| `ig` | `mu`, `sigma` | Inverse Gaussian |
| `ig_shifted` | `mu`, `sigma`, `shift` | Shifted inverse Gaussian |
| `gamma` | `k`, `scale` | Gamma distribution |
| `uniform` | `tmin`, `delta` | Uniform distribution on `[tmin, tmin + delta]` |
| `weibull` | `k`, `lambda` | Weibull distribution |
| `mix_exp_shifted` | `rate`, `mu1`, `mu2`, `shift` | Dirac plus shifted-exponential mixture |
| `shapefree_n_oldbin` | `z1`, `z2`, `z3` by default | Bounded piecewise-uniform shape-free model |

The model-specific meaning of these parameters is defined in
{doc}`../science/lpm-reference`. The runtime registry remains authoritative:
use `pyages list lpms` to inspect the installed release.

### Run Section

```yaml
run:
  reachable_concentrations: true    # Explore feasible concentration domain
  objective_function: true          # Map objective function on parameter grid
  calibration_metropolis_hastings: true  # Run MCMC calibration
  calibration_simplex: true         # Run simplex/FUQ calibration
```

All four fields are boolean and currently default to `true` when the `run`
section or a field is omitted. Set unwanted analyses explicitly to `false`,
especially for a quick or non-interactive run.

### Reachable Concentrations Section

```yaml
reachable_concentrations:
  nmodels: 5000                     # Number of random samples
```

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `nmodels` | integer | 5000 | Number of parameter samples for exploration; at least 1 |

### Objective Function Section

```yaml
objective_function:
  nmodels: 10000                    # Grid resolution
```

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `nmodels` | integer | 10000 | Number of points in parameter grid; at least 1 |

The mapped column ``half_log_chi_square`` is $\tfrac12\log(\chi^2)$, not the likelihood or
the normalized residual norm stored in calibration result tables. See
{doc}`../scientific-methods` for the exact objective conventions.

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
| `nstep` | integer | 5000 | Number of MCMC transitions; at least 11 so the fixed burn-in/thinning defaults retain a state |
| `prior_option` | boolean | false | Include prior probability in acceptance |
| `likelihood` | boolean | true | Use likelihood function |
| `monitor` | boolean | false | Monitor and display acceptance rates |
| `display_traj` | boolean | false | Generate trajectory plots (slow) |

These launcher fields do not by themselves demonstrate MCMC convergence.
Acceptance, retention, prior, and proposal equations are given in
{doc}`../scientific-methods`; article results additionally require the
multiple-chain diagnostics described in {doc}`../science/inference`.
The operational calibration checklist is in {doc}`calibration`.

### Simplex Section

```yaml
calibration_simplex:
  init_multiples_n: 3               # Initial simplex multiplier
  fuq_n: 30                         # Forward UQ sample count
```

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `init_multiples_n` | integer | 3 | Number of initial simplex configurations; at least 1 |
| `fuq_n` | integer | 30 | Number of samples for forward uncertainty; at least 1 |

---

## Temporal Workflow Configuration

Used with `pyages run --transient <config.yaml>`.

### Dataset Section

```yaml
dataset:
  file: examples/natural/ploemeur_temporal/data/ori_ploemeur_F09_2005_2024.txt
  error_rel: 0.2                    # Relative error (20%)
  missing_error_rel: 0.01           # Fallback for any remaining zero error
```

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `file` | non-empty string | Yes | Path to an existing multi-date concentration file |
| `error_rel` | number or null | No | Relative error in `(0, 1)` applied to all rows if any input error is zero; default `null` |
| `missing_error_rel` | number | No | Fraction in `(0, 1)` of the tracer mean used only for zero errors remaining after `error_rel`; default `0.01` |

Both transformations are applied before analysis. Their fractions, methods,
row indices, and counts are written under `details.observation_error_policy`
in the result manifest.

### LPM Models Section

```yaml
lpm_models:
  list: ["exp_shifted", "ig", "ig_shifted"]
  directory: data_core/data_lpm
```

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `list` | array or null | No | Unique, non-empty LPM identifiers without path separators; `null` selects `exp_shifted`, `ig`, and `ig_shifted`, while an explicit empty array is rejected |
| `directory` | path or null | No | Existing LPM parameters directory; defaults to packaged `data_core/data_lpm` |

### Workflow Section

```yaml
workflow:
  mode: span                        # 'span' or 'successive'
```

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `mode` | string | `span` | Exactly `span` (one joint calibration) or `successive` (one calibration per distinct date) |

### Calibration Section

```yaml
calibration:
  explo_res: 20                     # Systematic sampling resolution
  mh_nsteps: 1000                   # MCMC iterations
  burn_in: 0.2                      # Burn-in fraction (0-1)
  nskip: 10                         # Thinning interval
  lpm_number: 10                    # Posterior draws used in plotted outputs (0 = auto)
  seed_enabled: false               # Enable reproducible RNG explicitly
  seed: 12345                       # Random seed
```

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `explo_res` | integer | 20 | Preparation sampling resolution; at least 1 |
| `mh_nsteps` | integer | 1000 | MCMC transitions; strictly greater than 100 |
| `burn_in` | number | 0.2 | Burn-in fraction in `[0, 0.5)` |
| `nskip` | integer | 10 | Keep iterations divisible by this value after strict burn-in; at least 1 |
| `lpm_number` | integer | 10 | Posterior draws used for distribution and concentration plots; non-negative, with 0 selecting an automatic count |
| `seed_enabled` | boolean | false | Use the configured fixed random seed; otherwise generate a fresh seed for each chain and record it in `parameters_calibration.txt` |
| `seed` | non-negative integer or null | null | Required when `seed_enabled: true`; ignored otherwise |

The retention rule is zero-based and strict: a state is retained when
`iteration > burn_in * mh_nsteps` and `iteration % nskip == 0`. Rejected
proposals retain the repeated current state, as required for a valid Markov
chain.

### Figures Section

```yaml
figures:
  temporal: false                   # Time series plots
  distributions: false              # Parameter/concentration distributions
  concentrations_2d: false          # Pairwise concentration plots
```

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `temporal` | boolean | false | Write modeled concentration chronicles |
| `distributions` | boolean | false | Write posterior parameter summaries |
| `concentrations_2d` | boolean | false | Write pairwise concentration plots when `distributions` is also true; otherwise it has no effect |

### Results Section

```yaml
results:
  use_default: true                 # Use default results directory
  directory: ""                     # Custom directory (if use_default: false)
  study_name: temporal              # Safe namespace below the results root
```

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `use_default` | boolean | true | Use `PYAGES_RESULTS_DIR` or the user-level default root |
| `directory` | path or null | null | Custom root, required and created when `use_default` is false |
| `study_name` | non-empty string | `temporal` | One result-directory component containing only letters, digits, `.`, `_`, or `-`; `.` and `..` are rejected |

The result layout and the exact meaning of every generated table are defined
in {doc}`../reference/outputs`.

---

## LPM Parameter Files (params.yaml)

Each LPM model has a `params.yaml` file in `data_core/data_lpm/<model>/`.
PyAges supports version `1`; omitting `version` is equivalent to declaring
`version: 1`. Any other value is rejected before model construction.

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
| `step` | number | Conditional | Proposal step used with `componentwise_source="model"` |
| `prior` | object | No | Prior distribution specification |

At LPM construction time, PyAges validates the runtime fields used by the
model: the YAML `model` identifier must match the requested LPM; parameter
names must be non-empty, unique, and exactly match the model constructor;
every `bounds` pair must contain finite numbers in ascending order; and each
finite `init` value must lie inside its inclusive bounds. The constructor's
parameter order remains the canonical order for calibration vectors even when
the entries appear in another order in YAML.

The shared YAML loader validates `version`, `name`, `bounds`, `init`, and any
supplied `step` or `prior`, then caches an immutable schema. Cache reuse is
based on the exact file content, so replacing a file while preserving its size
and timestamp cannot return stale parameters. `ParameterManager` binds that
schema to the constructor's parameter set and order. Descriptive fields remain
available in the defensive copy returned by the document loader; proposal
steps and priors are exposed through the immutable runtime schema.

`step` may be omitted when Metropolis-Hastings derives componentwise proposal
scales from parameter bounds (the default). It is required for every parameter
when `MHConfig(componentwise_source="model")` is selected. When present, it
must be finite and strictly positive.

### Prior Distribution

```yaml
prior:
  type: uniform                     # 'uniform' or 'normal'
  min: 0.0                          # Prior minimum
  max: 100.0                        # Prior maximum
  unit: year                        # Unit (for documentation)
```

For a normal prior, replace `min` and `max` with `mean` and `std`. A uniform
prior requires finite values with `min < max`; a normal prior requires a finite
mean and a finite, strictly-positive standard deviation. Unknown prior types
and incomplete prior mappings are rejected while loading `params.yaml`. When
parametric priors are enabled, every model parameter must define one.

Parameter bounds remain active independently of the prior and define the
admissible calibration domain. Scientific analyses should report both the
bounds and the prior actually used.

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
# half_life: 12.32                  # Published half-life in years
# decay_mean_lifetime: 17.77        # Alternative; do not set both

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
| `half_life` | number | No | Published radioactive half-life (years) |
| `decay_mean_lifetime` | number | No | Mean lifetime (years), alternative to `half_life` |
| `production_rate` | number | No | Geoproduction rate |
| `datemin` | number | No | Minimum valid date |
| `datemax` | number | No | Maximum valid date |

For a recharge contribution, use either `recharge: true` or
`recharge_constant`. A programmatic or production-only tracer can omit both,
but still needs a valid date range.
`half_life` and `decay_mean_lifetime` are mutually exclusive.

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
| `PYAGES_RESULTS_DIR` | Root directory for output files | `~/results/PyAges` |

Set on Windows:
```bash
setx PYAGES_RESULTS_DIR "D:\results\PyAges"
```

Set on Linux/macOS:
```bash
export PYAGES_RESULTS_DIR="/path/to/results"
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

### Longer Candidate Runs (for Production)

```yaml
reachable_concentrations:
  nmodels: 20000                    # More samples

calibration_metropolis_hastings:
  nstep: 50000                      # More MCMC steps
  monitor: true                     # Record trajectory/acceptance monitoring
```

More iterations do not by themselves establish convergence. Publication runs
should use multiple chains and the diagnostics in {doc}`../science/inference`.

### Reproducible Results

```yaml
calibration:
  seed_enabled: true
  seed: 42                          # Fixed seed
```
