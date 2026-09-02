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
  burn_in: 0.2                      # Fraction discarded before retention
  nskip: 10                         # Retain every tenth post-burn-in state
  seed: 12345                       # Seed used by the one-chain mode
  prior_option: false               # Use prior in likelihood
  likelihood: true                  # Use likelihood (should be true)
  monitor: false                    # Track acceptance statistics
  display_traj: false               # Plot parameter trajectories
  multichain: null                  # Optional ensemble; see the next section
```

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `nstep` | integer | 5000 | Number of production transitions per chain; at least 11 |
| `burn_in` | number | 0.2 | Fraction in `[0, 1)` discarded by the strict retention rule |
| `nskip` | integer | 10 | Retain iterations divisible by this value after strict burn-in; at least 1 |
| `seed` | non-negative integer | 12345 | Random seed for the one-chain mode |
| `prior_option` | boolean | false | Include prior probability in acceptance |
| `likelihood` | boolean | true | Use likelihood function |
| `monitor` | boolean | false | Monitor and display acceptance rates |
| `display_traj` | boolean | false | Generate trajectory plots (slow) |
| `multichain` | object or null | null | Optional multi-chain controls; omitted or `null` preserves the one-chain workflow |

These launcher fields do not by themselves demonstrate MCMC convergence.
Acceptance, retention, prior, and proposal equations are given in
{doc}`../scientific-methods`; article results additionally require the
multiple-chain diagnostics described in {doc}`../science/inference`.
The operational calibration checklist is in {doc}`calibration`.

(optional-multi-chain-mh-configuration)=
### Optional Multi-chain MH Configuration

```{note}
This section documents an **Unreleased** development-branch feature. It is not
implemented by the `pyages==1.0.1` package from PyPI. Until the next release,
use an editable source installation and record its exact Git commit.
```

The same optional `multichain` mapping is accepted below
`calibration_metropolis_hastings` in a single-date file and below `calibration`
in a temporal file. Omitting it or setting it to `null` preserves the existing
one-chain execution. The presence of a mapping activates the ensemble because
`enabled` defaults to `true`; set `enabled: false` explicitly to keep a
temporarily retained block inactive. A production ensemble can be written as
follows:

```yaml
multichain:
  enabled: true
  chains: 4
  master_seed: 12345
  initialization:
    strategy: bounds_stratified
    explicit_starts: null
    max_attempts: 100
  pilot:
    enabled: true
    nstep: 2000
    burn_in: 0.5
    covariance_mode: pooled_within_chain
    relative_ridge: 1.0e-6
    proposal_multiplier: auto
    save_samples: false
  diagnostics:
    max_rhat: 1.01
    min_bulk_ess: 300.0
    min_tail_ess: 300.0
    require_convergence: true
```

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `enabled` | boolean | true | Run the multi-chain path when the mapping is present; set false to disable that retained block |
| `chains` | integer | 4 | Number of pilot and production chains; at least 2 |
| `master_seed` | non-negative integer or null | 12345 | Root of independent initialization, pilot, and production streams; `null` generates a fresh root seed that is recorded for replay |
| `initialization` | object | see below | Policy used to construct one bounded start per chain |
| `pilot` | object | see below | Pilot phase used to estimate a common, fixed production proposal covariance |
| `diagnostics` | object | see below | Production-chain qualification thresholds |

`initialization` has these controls:

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `strategy` | string | `bounds_stratified` | Dispersed Latin-hypercube draws over calibration ranges, or effective marginal prior mass when a prior is active |
| `explicit_starts` | array of mappings or null | null | Exactly one complete parameter mapping per chain; accepted only with `strategy: explicit` |
| `max_attempts` | integer | 100 | Maximum within-stratum retries for unresolved `bounds_stratified` candidates that fail the active-prior support check; currently unused by the other strategies; at least 1 |

The other initialization strategies are `prior_sample`, which independently
draws each chain from the enabled and loaded prior; `explicit`, which uses the
ordered mappings in `explicit_starts`; `model_default`, which deliberately
starts every chain from the LPM defaults; and `prior_map`, which deliberately
starts every chain at a bounded prior mode. The two deterministic strategies
are compatibility tools, not dispersed convergence checks. `prior_sample` and
`prior_map` require `prior_option: true` and a prior covering every parameter.
Every returned candidate is checked against the calibration ranges and, when the
prior is active, its support. `prior_sample` uses each prior marginal conditioned
on the operational interval through an exact bounded quantile; `prior_map` uses a
bounded marginal mode. Neither strategy performs rejection sampling or consumes
`max_attempts`.

For `bounds_stratified`, one random permutation assigns a fixed marginal
stratum to each chain, while that chain's own initialization stream supplies
its within-stratum jitter. If a candidate fails the active-prior support check,
only unresolved chains redraw jitter inside their already assigned strata. A
successful result therefore remains a Latin hypercube; otherwise initialization
fails explicitly after `max_attempts`. Initialization never uses observations
or selects starts by likelihood.

`pilot` has these controls:

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `enabled` | boolean | true | Run separate pilot chains before production |
| `nstep` | integer | 2000 | Transitions in each pilot chain; at least 4 and sufficient with `burn_in` to retain two draws |
| `burn_in` | number | 0.5 | Fraction in `[0, 1)` discarded from each pilot; at least two draws must remain |
| `covariance_mode` | string | `pooled_within_chain` | Estimate one covariance after centering every pilot chain separately |
| `relative_ridge` | number | 1.0e-6 | Non-negative, scale-aware diagonal regularization ensuring a usable covariance |
| `proposal_multiplier` | positive number or `auto` | `auto` | Scale applied to proposal standard deviations; `auto` uses $2.38/\sqrt{d}$ for $d$ parameters |
| `save_samples` | boolean | false | Persist pilot draws as tuning evidence; they never enter the production posterior |

The proposal covariance is therefore not a prior covariance and is not copied
from the first chain. It pools the within-chain variation from all pilot
chains, excludes differences between their means, adds the configured ridge,
and is then held fixed for every production chain. Fixing it before production
preserves the Markov-chain target while still adapting proposal geometry in a
separate tuning phase.

`diagnostics` has these controls:

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `max_rhat` | number | 1.01 | Strict upper qualification limit for rank-normalized split-$\hat R$; greater than 1 |
| `min_bulk_ess` | number | 300.0 | Minimum bulk effective sample size; strictly positive |
| `min_tail_ess` | number | 300.0 | Minimum tail effective sample size; strictly positive |
| `require_convergence` | boolean | true | Require every applicable sampled or derived quantity to meet the gates before treating pooled draws as a qualified posterior; derived quantities that are constant across all retained production draws are reported but excluded |

When convergence is required, configuration validation also checks the
algorithmic ESS ceiling after splitting the retained chains. Following Stan,
antithetic chains may have ESS greater than their raw draw count, with a ceiling
of $N\log_{10}(N)$ for $N$ split draws. If a requested ESS cannot possibly be
reached, increase `nstep`/`mh_nsteps`, reduce thinning, or set
`require_convergence: false` for an explicitly exploratory short run.

In multi-chain mode, `master_seed` controls the whole ensemble and the
one-chain `seed` is not reused. In a temporal file, `seed_enabled` and `seed`
likewise apply only to the one-chain mode. Separate derived streams keep
initialization, pilot, and production randomness reproducible without making
the production chains share a random-number stream.

The single-date `monitor` and `display_traj` switches are one-chain options and
cannot be combined with an enabled ensemble. Multi-chain runs persist every
raw chain under `chains/`, which is the stable input for trace diagnostics and
avoids transient plots being confused with convergence qualification. The
direct Python `MultiChainMetropolisHastings` API enforces the same restriction
instead of silently changing those options. Its lower-level `display_text`
option remains valid and logs a separate summary for each pilot or production
sampler; it is not exposed by the YAML launcher.

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
  multichain: null                  # Optional ensemble; same block as above
```

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `explo_res` | integer | 20 | Preparation sampling resolution; at least 1 |
| `mh_nsteps` | integer | 1000 | MCMC transitions; strictly greater than 100 |
| `burn_in` | number | 0.2 | Burn-in fraction in `[0, 0.5)` |
| `nskip` | integer | 10 | Keep iterations divisible by this value after strict burn-in; at least 1 |
| `lpm_number` | integer | 10 | Posterior draws used for distribution and concentration plots; non-negative, with 0 selecting an automatic count |
| `seed_enabled` | boolean | false | Use the configured fixed one-chain seed; otherwise generate and record a fresh seed for that run |
| `seed` | non-negative integer or null | null | Required when `seed_enabled: true`; ignored otherwise |
| `multichain` | object or null | null | Optional multi-chain controls; omitted or `null` preserves the one-chain workflow |

The retention rule is zero-based and strict: a state is retained when
`iteration > burn_in * mh_nsteps` and `iteration % nskip == 0`. Rejected
proposals retain the repeated current state, as required for a valid Markov
chain.

For an ensemble, place the mapping from
{ref}`optional-multi-chain-mh-configuration` under `calibration`. Its
`master_seed` replaces the one-chain `seed_enabled`/`seed` controls and its
`chains` value sets the number of independent production chains.

The temporal workflow currently always enables the parametric priors declared
in each selected LPM's `params.yaml` (`prior_option=True`,
`prior_type="parametric"`). Unlike the single-date workflow, it does not expose
`prior_option` or `prior_type` in this YAML section. LPM calibration ranges remain
active and restrict the resulting target. Changing this behavior therefore
requires a workflow/API change, not an undocumented configuration key.

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
    domain:                         # Formula validity, independent of inference
      min: 0.0
      min_inclusive: false
      max: null
    calibration_range: [0.1, 70.0] # Finite operational search range
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
    domain: {min: 0.0, min_inclusive: false, max: null}
    calibration_range: [0.1, 70.0]
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
| `domain` | object | Yes for new files | Mathematical formula domain; `min` or `max` may be `null`, and endpoints are inclusive unless the corresponding `*_inclusive` flag is false |
| `calibration_range` | array | Yes for new files | Finite inclusive `[min, max]` used by optimizers and samplers |
| `init` | number | Yes | Initial value for optimization |
| `step` | number | Conditional | Proposal step used with `componentwise_source="model"` |
| `prior` | object | No | Prior distribution specification |

At LPM construction time, PyAges validates the runtime fields used by the
model: the YAML `model` identifier must match the requested LPM; parameter
names must be non-empty, unique, and exactly match the model constructor;
every `calibration_range` pair must contain finite numbers in ascending order
and lie inside `domain`; and each finite `init` value must lie inside its
inclusive calibration range. The constructor's
parameter order remains the canonical order for calibration vectors even when
the entries appear in another order in YAML.

The shared YAML loader validates `version`, `name`, `domain`,
`calibration_range`, `init`, and any supplied `step` or `prior`, then caches an
immutable schema. Cache reuse is
based on the exact file content, so replacing a file while preserving its size
and timestamp cannot return stale parameters. `ParameterManager` binds that
schema to the constructor's parameter set and order. Descriptive fields remain
available in the defensive copy returned by the document loader; proposal
steps and priors are exposed through the immutable runtime schema.

`step` may be omitted when Metropolis-Hastings derives componentwise proposal
scales from parameter calibration ranges (the default). It is required for every parameter
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

These fields answer three different questions:

1. `domain`: can the LPM formula be evaluated? For example, an exponential
   scale must be strictly positive, but it has no universal finite maximum.
2. `calibration_range`: what finite interval is this run allowed to search?
   It is a numerical and study-design choice inside the mathematical domain.
3. `prior`: how is probability weighted before seeing the observations?

The effective MH support is the intersection of the calibration range and the
prior support. A normal prior is therefore conditioned on the calibration
range; a uniform prior may narrow it further. Scientific analyses should
report all three choices. For compatibility, version-1 files may still use
`bounds` instead of `calibration_range`; when `domain` is absent, that legacy
range is also used as the mathematical domain. New files should use the
explicit fields.

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
