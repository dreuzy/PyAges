# Configuration Reference

PyAges uses YAML configuration files to control workflows. This reference
documents all available options.

All user-facing configuration models are strict: an unknown section or field
is rejected rather than ignored. Type errors and violated numeric bounds are
reported before the scientific workflow starts.

PyAges 2.0 uses configuration schema 3. It uses common section names in
both workflows and always resolves relative paths from the YAML file's
directory. Generate a complete example with:

```bash
pyages new config quickstart
```

A schema-3 file starts with an explicit discriminator and uses the following
canonical sections:

```yaml
schema_version: 3
workflow:
  kind: single_date
data: {}
lpm:
  models: [exp_shifted]
calibration:
  metropolis_hastings: {}
output: {}
```

The configuration schema number is independent of both the PyAges package
version (`2.0.0`) and the result-manifest schema; it versions only YAML syntax.
All maintained workflow files under `examples/` use schema 3 and are current
starting points. Older layouts and former field names are no longer part of
PyAges: there is no implicit conversion and no compatibility alias. To update
an old study, generate a fresh schema-3 file, then copy and review its scientific
values field by field. Runtime loading rejects unknown sections instead of
guessing what they mean.

For the complete section and field mappings, path rules, random-seed changes,
and Python API replacements, follow {doc}`migrating-to-2.0`.

## Single-date workflow configuration

Used with `pyages run <config.yaml>`.

### Workflow Section

```yaml
workflow:
  kind: single_date
```

`kind` is required. It is the sole workflow discriminator used by the CLI.

### Data Section

```yaml
data:
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
  models: [dirac_double]            # Exactly one LPM for this workflow
```

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `models` | one-item array | No | One LPM identifier as a path component; default `[dirac_double]` |
| `directory` | path | No | Optional directory containing `<model>/params.yaml`; when omitted, PyAges uses the data packaged with the installed distribution |

Omitting `directory` is the portable choice for standard LPMs: the same file
then works in a source checkout and after wheel installation. Set it only for
custom parameter files. A relative override is resolved beside the YAML file,
so `directory: custom_lpm` means a `custom_lpm/` directory in the quickstart
project, not in the Python installation.

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
  metropolis_hastings: true  # Run MCMC calibration
  simplex: true         # Run simplex/FUQ calibration
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
calibration:
  metropolis_hastings:
    nsteps: 5000                    # Production transitions per chain
    burn_in: 0.2                    # Fraction discarded before retention
    thinning: 10                    # Retain every tenth post-burn-in state
    seed: 12345                     # null creates and records a fresh seed
    chains: 1                       # The same runner accepts every value >= 1
    initialization: {}
    pilot: {}
    diagnostics: {}
    prior_option: false             # Include the configured prior
    likelihood: true
    display_traj: false
```

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `nsteps` | integer | 5000 | Number of production transitions per chain; at least 1, with the complete schedule required to retain at least one draw |
| `burn_in` | number | 0.2 | Fraction in `[0, 1)` discarded by the strict retention rule |
| `thinning` | integer | 10 | Retain iterations divisible by this value after strict burn-in; at least 1 |
| `seed` | non-negative integer or null | 12345 | Seed for the entire run; `null` generates a fresh recorded seed |
| `chains` | integer | 1 | Number of production chains; inter-chain diagnostics apply from 2 upward |
| `initialization` | object | `{}` | Initial-state policy described below |
| `pilot` | object | `{}` | Optional proposal-tuning phase described below |
| `diagnostics` | object | `{}` | Inter-chain qualification thresholds described below |
| `prior_option` | boolean | false | Include prior probability in acceptance |
| `likelihood` | boolean | true | Use likelihood function |
| `display_traj` | boolean | false | Generate trajectory plots inside each production-chain directory (slow) |

These launcher fields do not by themselves demonstrate MCMC convergence.
Acceptance, retention, prior, and proposal equations are given in
{doc}`../scientific-methods`; article results additionally require the
multiple-chain diagnostics described in {doc}`../science/inference`.
The operational calibration checklist is in {doc}`calibration`.

(one-to-many-chain-mh-configuration)=
### One-to-many-chain MH controls

There is no separate "single-chain mode" or `multichain.enabled` switch. One
chain is simply `chains: 1`; increasing that integer asks the same runner to
create more independent chains. This removes three formerly overlapping ways
of selecting the execution path.

```yaml
metropolis_hastings:
  nsteps: 5000
  thinning: 1
  chains: 4
  seed: 12345
  initialization:
    strategy: bounds_stratified
    explicit_starts: null
    max_attempts: 100
  pilot:
    enabled: true
    nsteps: 2000
    burn_in: 0.5
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
| `chains` | integer | 1 | Number of production chains; at least 1. Inter-chain diagnostics apply from 2 upward |
| `seed` | non-negative integer or null | 12345 | Root of independent initialization, pilot, and production streams; `null` generates a fresh seed that is recorded for replay |
| `initialization` | object | see below | Policy used to construct one bounded start per chain |
| `pilot` | object | see below | Pilot phase used to estimate a common, fixed production proposal covariance |
| `diagnostics` | object | see below | Production-chain qualification thresholds |

`initialization` has these controls:

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `strategy` | string | `bounds_stratified` | Applies one Latin-hypercube rule over the bounded parameter space for one or several chains |
| `explicit_starts` | array of mappings or null | null | Exactly one complete parameter mapping per chain; accepted only with `strategy: explicit` |
| `max_attempts` | integer | 100 | Maximum within-stratum retries for unresolved `bounds_stratified` candidates that fail the active-prior support check; currently unused by the other strategies; at least 1 |

The alternatives are `prior_sample`, which independently
draws each chain from the enabled and loaded prior, and `explicit`, which uses
the ordered mappings in `explicit_starts`. `prior_sample` requires
`prior_option: true` and a prior covering every parameter. Use `explicit` when
the exact start is part of the study protocol.
Every returned candidate is checked against the calibration ranges and, when the
prior is active, its support. `prior_sample` uses each prior marginal conditioned
on the operational interval through an exact bounded quantile. It does not
perform rejection sampling or consume `max_attempts`.

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
| `enabled` | boolean | false | Run separate pilot chains before production |
| `nsteps` | integer | 2000 | Transitions in each pilot chain; at least 4 and sufficient with `burn_in` to retain two draws |
| `burn_in` | number | 0.5 | Fraction in `[0, 1)` discarded from each pilot; at least two draws must remain |
| `relative_ridge` | number | 1.0e-6 | Non-negative, scale-aware diagonal regularization ensuring a usable covariance |
| `proposal_multiplier` | positive number or `auto` | `auto` | Scale applied to proposal standard deviations; `auto` uses $2.38/\sqrt{d}$ for $d$ parameters |
| `save_samples` | boolean | false | Persist pilot draws as tuning evidence; they never enter the production posterior |

The proposal covariance always uses the pooled-within-chain estimator: each
pilot chain is centered separately before their variations are combined. This
is not a prior covariance and it is not copied from the first chain. The
configured ridge is then added, and the resulting covariance is held fixed for
every production chain. Fixing it before production preserves the Markov-chain
target while still adapting proposal geometry in a separate tuning phase.

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
reached, increase `nsteps`, reduce `thinning`, or set
`require_convergence: false` for an explicitly exploratory short run.

The single `seed` field controls the whole run for every chain count. Separate
derived streams keep
initialization, pilot, and production randomness reproducible without making
the production chains share a random-number stream. The first production seed
is unchanged when `chains` grows from 1 to a larger value, so adding chains does
not silently replace the original trajectory.

`display_traj: true` creates trajectory figures separately inside every
`chains/chain_<N>/` directory. Per-chain sample tables remain the stable input
for trace diagnostics; trajectory figures are a visual aid, not convergence
qualification. Direct Python callers may use `record_trajectory` to retain an
in-memory trajectory without creating a figure. This lower-level control and
`display_text` are not part of the YAML workflow.

### Simplex Section

```yaml
calibration:
  simplex:
    init_multiples_n: 3             # Initial simplex multiplier
    fuq_n: 30                       # Forward UQ sample count
```

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `init_multiples_n` | integer | 3 | Number of initial simplex configurations; at least 1 |
| `fuq_n` | integer | 30 | Number of samples for forward uncertainty; at least 1 |

### Output Section

```yaml
output:
  use_default: true                 # Use the configured PyAges result root
  directory: null                   # Required when use_default is false
  study_name: test_cases            # Namespace below the result root
```

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `use_default` | boolean | true | Use `PYAGES_RESULTS_DIR` or the user-level default root |
| `directory` | path or null | null | Custom root, required when `use_default` is false; a relative path is resolved beside this YAML file |
| `study_name` | non-empty string | `test_cases` | One safe result-directory component containing only letters, digits, `.`, `_`, or `-` |

The workflow creates `<root>/<study_name>/<data.name>/`. Keeping `study_name`
explicit in scientific profiles prevents a new run from replacing the public
result tree of a different study that happens to use the same data file.

---

## Temporal Workflow Configuration

Used with `pyages run <config.yaml>` and `workflow.kind: temporal`.

### Data Section

```yaml
data:
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

### LPM Section

```yaml
lpm:
  models: ["exp_shifted", "ig", "ig_shifted"]
  directory: data_core/data_lpm
```

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `models` | array or null | No | Unique, non-empty LPM identifiers without path separators; `null` selects `exp_shifted`, `ig`, and `ig_shifted`, while an explicit empty array is rejected |
| `directory` | path or null | No | Existing LPM parameters directory; defaults to packaged `data_core/data_lpm` |

Runtime schema 3 accepts only `lpm.models`; former spellings are rejected.

### Workflow Section

```yaml
workflow:
  kind: temporal
  mode: span                        # 'span' or 'successive'
```

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `kind` | string | Yes | Fixed discriminator `temporal` used by `pyages run` |
| `mode` | string | No (`span`) | Exactly `span` (one joint calibration) or `successive` (one calibration per distinct date) |

### Calibration Section

```yaml
calibration:
  exploration_resolution: 20       # Forward-model preparation sample count
  posterior_draw_count: 10         # Draws used in temporal plots; 0 = automatic
  metropolis_hastings:
    nsteps: 5000                    # Production transitions per chain
    burn_in: 0.2                    # Burn-in fraction
    thinning: 10                   # Retention interval
    seed: 12345                    # null creates and records a fresh seed
    chains: 1
    prior_option: true              # Explicitly include configured LPM priors
    initialization: {}
    pilot: {}
    diagnostics: {}
```

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `exploration_resolution` | integer | 20 | Sample count used while preparing the temporal forward problem; at least 1 |
| `posterior_draw_count` | integer | 10 | Posterior draws used for temporal outputs; 0 derives a bounded count from `nsteps` |
| `metropolis_hastings` | object | `{}` | The exact same MH model documented for the single-date workflow above |

The retention rule is zero-based and strict: a state is retained when
`iteration > burn_in * nsteps` and `iteration % thinning == 0`. Rejected
proposals retain the repeated current state, as required for a valid Markov
chain.

Every field nested below `metropolis_hastings` has exactly the same meaning and
default in both workflows. A one-chain run is therefore only `chains: 1`, not a
different execution mode. Temporal studies that use the priors declared in each
LPM's `params.yaml` must say `prior_option: true`; this scientific choice is
no longer injected silently by the workflow. LPM calibration ranges remain active
and restrict the target independently of that option.

### Reporting Section

```yaml
reporting:
  temporal: false                   # Time series plots
  distributions: false              # Parameter/concentration distributions
  concentrations_2d: false          # Pairwise concentration plots
```

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `temporal` | boolean | false | Write modeled concentration chronicles |
| `distributions` | boolean | false | Write posterior parameter summaries |
| `concentrations_2d` | boolean | false | Write pairwise concentration plots when `distributions` is also true; otherwise it has no effect |

### Output Section

```yaml
output:
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
report all three choices. Schema 3 requires `calibration_range`; the former
`bounds` spelling is rejected. See {doc}`migrating-to-2.0` before updating an
old parameter file.

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

calibration:
  metropolis_hastings:
    nsteps: 500                     # Fewer MCMC steps
```

### Longer Candidate Runs (for Production)

```yaml
reachable_concentrations:
  nmodels: 20000                    # More samples

calibration:
  metropolis_hastings:
    nsteps: 50000                   # More MCMC steps
    display_traj: true              # One figure set per production chain
```

More iterations do not by themselves establish convergence. Publication runs
should use multiple chains and the diagnostics in {doc}`../science/inference`.

### Reproducible Results

```yaml
calibration:
  metropolis_hastings:
    seed: 42                        # Fixed seed for one or many chains
```
