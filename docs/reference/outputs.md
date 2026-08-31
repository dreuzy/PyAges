# Workflow outputs and result manifests

This page defines the machine-readable files written by the installed
single-date and temporal workflows. Unless stated otherwise, text tables use
UTF-8 encoding and tab separators even though their historical extension is
`.txt`.

The result root is selected once when `pyages.config.paths` is imported:

1. `PYAGES_RESULTS_DIR`, when the environment variable is non-empty;
2. otherwise `~/results/PyAges`.

Temporal configurations can instead select an explicit root with
`results.use_default: false` and `results.directory`.

## Completion contract

Both public workflows write `result_manifest.json` **last** after success. A
required multi-chain convergence gate that rejects an otherwise completed
calculation writes the same file with `status: failed` after preserving the
chain and diagnostic evidence. Other execution failures can leave no
manifest. A directory without a manifest whose `status` is `complete` is not a
completed workflow result, even if it contains apparently usable intermediate
files.

Once a workflow has prepared its target result directory, it removes any
previous terminal manifest before writing new artifacts. A failed rerun can
therefore not leave an earlier `"status": "complete"` marker behind. Workflows
still reuse deterministic directories and retain other files from earlier
runs. For qualification or publication evidence, start from an empty result
directory or archive the preceding run first. A new success manifest hashes
every file present below the result directory, including retained files.

## Single-date layout

`pyages run <config.yaml>` writes below:

```text
<results_root>/test_cases/<dataset.name>/
```

The complete layout is conditional on the `run` flags:

```text
<dataset.name>/
|-- concentrations.txt
|-- reachable_concentrations/                 # if enabled
|   |-- parameters.txt
|   `-- c_reach.txt
|-- Metropolis_Hastings/                      # if enabled
|   |-- parameters_calibration.txt
|   |-- results_calibration.txt
|   |-- lpm_dist_calibrated.txt
|   |-- lpm_histo_calibrated_<parameter>.txt
|   |-- lpm_stats_calibrated.txt
|   |-- distributions.txt
|   `-- distributions_stats.txt
|-- forward_uncertainty_quantification/       # if enabled
|   |-- parameters_calibration.txt
|   |-- results_calibration.txt
|   |-- lpm_dist_calibrated.txt
|   |-- lpm_histo_calibrated_<parameter>.txt
|   |-- lpm_stats_calibrated.txt
|   |-- distributions.txt
|   `-- distributions_stats.txt
|-- objective_function_grid.txt               # if enabled
|-- 01_data_model_space.png                   # reachable + calibration
|-- 02_parameter_summary.png                  # at least one calibration
|-- 03_objective_summary.png                  # objective map enabled
`-- result_manifest.json                      # success or rejected convergence gate
```

`concentrations.txt` is always written. It is the normalized long-form
observation table used by the workflow and follows the schema in
{doc}`../user-guide/concentrations`. Its `error` column contains the effective
strictly positive uncertainties after zero placeholders have been resolved.

The `reachable_concentrations` directory contains:

- `parameters.txt`: key/value metadata (`date`, `lpm`, tracer names, and
  requested model count);
- `c_reach.txt`: the sampled reachable concentrations, with one column per
  tracer/date observation. Column keys use the lossless `tracer@date` form,
  for example `cfc11@2010.0`.

`objective_function_grid.txt` contains the sampled LPM parameters followed by
`half_log_chi_square`. That objective is
$0.5\log(\chi^2)$; it is not the `obj_function` value stored in calibration
sample tables. See {doc}`../scientific-methods` for the normative equations.

## Temporal layout

`pyages run --transient <config.yaml>` writes below:

```text
<results_root>/<study_name>/<dataset_stem>/<mode>/
```

`span` creates one `span_full` case. `successive` creates one
`date_<decimal-year>` case per distinct observation date; the decimal point is
replaced by an underscore. The shortest round-trip decimal representation is
used, so distinct floating-point dates cannot be merged by fixed rounding.

```text
<mode>/
|-- concentrations.txt                         # effective normalized observations
|-- span_full/ or date_<year>/
|   |-- 00_observations_overview.png          # if any figures are enabled
|   `-- <lpm_type>/
|       |-- parameters_calibration.txt
|       |-- results_calibration.txt
|       |-- lpm_dist_calibrated.txt
|       |-- lpm_histo_calibrated_<parameter>.txt
|       |-- lpm_stats_calibrated.txt
|       |-- parameter_summary.png              # distributions enabled
|       |-- comp2D_*.png                        # optional concentration diagnostics
|       `-- Metropolis_Hastings/                # temporal figures enabled
|           |-- concentration_times.png
|           |-- concentrations_all_models.txt
|           |-- distributions.txt
|           `-- distributions_stats.txt
`-- result_manifest.json                       # success or rejected convergence gate
```

The root `concentrations.txt` contains the exact effective errors used by all
cases. The manifest belongs to the `<mode>` directory and covers every date/LPM
case below it. `figures.concentrations_2d` has an effect only when
`figures.distributions` is also true. The `Metropolis_Hastings` presentation
subdirectory is produced only when `figures.temporal` is true; it is distinct
from the LPM directory that holds the calibration tables.

## Multi-chain MH artifacts

```{note}
These artifacts belong to the **Unreleased** multi-chain feature on the
development branch and are not produced by `pyages==1.0.1` from PyPI.
```

When a present `multichain` block is enabled (the default for that block), the
MH calibration directory keeps every production chain separate before any
pooling. For a single-date run this is
the existing `Metropolis_Hastings/` directory; for a temporal run it is the
LPM directory shown above.

```text
<mh_calibration_directory>/
|-- parameters_calibration.txt
|-- results_calibration.txt
|-- ensemble_provenance.txt
|-- mcmc_diagnostics.tsv
|-- proposal_covariance.tsv                    # pilot enabled
|-- chains/
|   |-- chain_001/
|   |   |-- chain_metadata.txt
|   |   `-- lpm_dist_calibrated.txt
|   `-- chain_<N>/...
|-- pilot/                                     # pilot enabled
|   |-- pilot_metadata.txt
|   `-- chain_<N>_samples.tsv                  # save_samples: true only
|-- lpm_dist_calibrated.txt                    # pooled only after the gate
|-- lpm_histo_calibrated_<parameter>.txt       # pooled only after the gate
`-- lpm_stats_calibrated.txt                   # pooled only after the gate
```

The individual chain tables are written even when convergence qualification
fails or a diagnostic cannot be calculated. With
`diagnostics.require_convergence: true`, a failed or unavailable gate prevents
the pooled root tables and stops the workflow, so no successful result manifest
is written. Instead, the workflow writes a failure manifest with hashes of the
preserved evidence and the `MHConvergenceError` message. With
`require_convergence: false`, the root tables are exploratory pooled output and
`results_calibration.txt` records their qualification status and any diagnostic
error message; the workflow manifest is then complete.

`qualification_status` has exactly these meanings:

| Value | Meaning and pooling consequence |
|---|---|
| `qualified` | All applicable diagnostic rows pass; qualified root pooling is allowed. |
| `not_qualified` | Diagnostics exist but at least one applicable row fails; pooling is blocked unless `require_convergence: false` explicitly selects exploratory output. |
| `diagnostics_unavailable` | No complete diagnostic table could be calculated; the reason is stored in `diagnostics_message`, and qualified pooling is impossible. |

The generic gate covers a strict R-hat limit, minimum bulk/tail ESS, and a
finite MCSE. It does not impose an acceptance interval, relative-MCSE limit,
residual criterion, parameter-recovery criterion, or model-adequacy decision.
Those checks must be registered by a case-specific scientific protocol.

`ensemble_provenance.txt` is a key/value table containing the realized master
seed plus the distinct initialization, pilot, and production seed for every
chain. Each `chain_metadata.txt` records its production seed, initial parameter
values, retained-row count, acceptance fraction, and runtime.

`proposal_covariance.tsv` is a square labeled matrix in squared parameter
units. It is the regularized, pooled within-chain covariance learned from all
pilots; the multiplier recorded in `parameters_calibration.txt` scales its
standard deviations for production. `pilot_metadata.txt` records initial and
final pilot states, acceptance fractions, retained counts, per-chain runtimes,
and that realized multiplier. `results_calibration.txt` distinguishes summed
pilot and production runtimes and also reports their total.
Optional pilot sample tables contain parameters only and never contribute rows
to the posterior files.

`mcmc_diagnostics.tsv` contains one row for every monitored model parameter or
derived LPM quantity:

| Column | Meaning |
|---|---|
| `parameter` | Parameter or derived-quantity name |
| `rhat` | Larger of rank-normalized and folded rank-normalized split-$\hat R$ across production chains |
| `bulk_ess` | Bulk effective sample size across production chains |
| `tail_ess` | Smaller effective sample size for the empirical 5% and 95% quantile indicators |
| `mcse_mean` | Monte Carlo standard error of the posterior mean |
| `posterior_sd` | Standard deviation over retained production draws |
| `included_in_qualification` | Whether this row contributes to the ensemble gate; false for a structurally constant derived quantity |
| `qualified` | Whether this row passes every configured gate |

Native sampled parameters always contribute to qualification. Non-constant
derived LPM quantities also contribute, while a structurally constant derived
quantity is reported for completeness but cannot supply a meaningful R-hat or
ESS and therefore does not make qualification impossible.

A reproducible pandas/Matplotlib trace-reading example is in
{doc}`../user-guide/multichain-mh`. Trace plots use the separate chain tables,
never the pooled root table.

## Calibration table schemas

The same calibration files are used by both workflows.

### `parameters_calibration.txt`

A headerless two-column key/value table containing the resolved algorithm
configuration. Metropolis-Hastings records the transition count, burn-in,
thinning, derived retained-sample count, proposal, seed, initialization source,
and resolved prior metadata.
Simplex/FUQ records the method, tolerances, initialization count and seeds, and
the uncertainty sample count where applicable. Values that are lists or
mappings use their Python text representation.

### `results_calibration.txt`

A headerless two-column key/value table. All methods write `time_perform` in
seconds. Metropolis-Hastings also writes `success_rate`, the fraction of
accepted transitions. Simplex/FUQ writes aggregate optimizer run, iteration,
evaluation, and convergence fields.

For a multi-chain run this file additionally records
`qualification_status`, `diagnostics_message`, `chain_count`, retained counts,
whether pooling was written, mean/minimum/maximum acceptance, summed pilot and
production runtimes, and failed diagnostic counts. Interpret
`time_perform` as the sum of recorded pilot and production sampler runtimes,
not proof of wall-clock parallelism.

### `lpm_dist_calibrated.txt`

One row per retained joint sample. Columns appear in this order:

1. a serialized row index;
2. model parameters in the order declared by `params.yaml`;
3. `obj_function`, equal to $\sqrt{\chi^2/n}$;
4. modeled concentration columns named by tracer and observation date;
5. optional derived columns such as `param_in_bounds`, `mean`, `std`, `p10`,
   `p25`, `p50`, `p75`, and `p90`.

Rows are joint samples: parameter and concentration values from different rows
must never be recombined.

Modeled concentration columns are fitted latent responses for each retained
parameter row. They contain no newly simulated observation error and are not
posterior predictive draws. When compared with observations used by the same
likelihood, the comparison is in-sample.

### `lpm_histo_calibrated_<parameter>.txt`

One file per model parameter, with columns:

| Column | Meaning |
|---|---|
| `val` | Left edge of the histogram bin |
| `hist` | Probability-density value returned by `numpy.histogram(..., density=True)` |

The number of rows is the histogram bin count, currently 100. Consumers should
use the column names rather than depending on that implementation default.

### `lpm_stats_calibrated.txt`

Descriptive statistics produced by `pandas.DataFrame.describe()`. The first
column contains statistic labels (`count`, `mean`, `std`, `min`, `25%`, `50%`,
`75%`, and `max`); the other columns are the numeric sample-table columns.

### Chronicle and distribution tables

| File | Schema |
|---|---|
| `concentrations_all_models.txt` | `date`, followed by `<tracer>_<model-id>` columns for selected joint samples |
| `distributions.txt` | age `t` from 0 to 70 years, followed by one `p<sample-row>` PDF column per selected sample |
| `distributions_stats.txt` | `mean`, `std`, `p10`, `p25`, `p50`, `p75`, and `p90` for each selected sample |

The finite-width PDFs used for Dirac models in `distributions.txt` are plotting
approximations. Scientific convolution evaluates the corresponding point
masses exactly.

## `result_manifest.json` schema 2

| Field | Type | Meaning |
|---|---|---|
| `schema_version` | integer | Result-layout schema; currently `2` |
| `status` | string | `complete` after success, or `failed` after rejection by a required multi-chain convergence gate |
| `created_at_utc` | string | ISO 8601 terminal-manifest creation time with UTC offset |
| `pyages_version` | string | Installed PyAges version |
| `workflow` | string | `single_date` or `temporal` |
| `command` | array of strings | Process argument vector used for the run |
| `configuration` | object | Portable configuration path and SHA-256 digest |
| `inputs` | array of objects | Portable observation, selected LPM-resource, and tracer-resource paths with SHA-256 digests |
| `environment` | object | Python implementation, version, platform, and selected dependency versions |
| `repository` | object | Git revision, dirty state, status, diff digest, and tracked-workspace digest when available |
| `artifacts_sha256` | object | Relative artifact path to SHA-256 digest; excludes the manifest itself |
| `details` | object | Workflow-specific selection metadata |
| `failure` | object, optional | Exception `type` and `message`; present only when `status` is `failed` |

For `single_date`, `details` records the dataset, configured dataset year, LPM,
and completed calibration methods. A failed gate also records the attempted MH
calibration. For `temporal`, it records the dataset, mode, LPM list, and case
directories entered before the terminal state.

A failure manifest is evidence that the configured qualification gate rejected
the preserved chains; it is not a successful result marker. Configuration,
input, environment, repository, and artifact hashes follow the same contract
for both terminal statuses.

The manifest fingerprints the selected direct dependencies, but it is not a
complete package lock. Recreate a qualified environment from the versioned
constraint or environment file, then use the hashes to verify the exact inputs
and artifacts. Repository fields can be null when Git metadata is unavailable.

Incompatible changes to these documented table or manifest contracts require
the compatibility treatment described in {doc}`public-api`.
