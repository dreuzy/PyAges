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

Once a workflow has resolved its target result directory, it creates a hidden
sibling staging directory derived from a fresh `run_id`. A preceding published
tree, including its terminal manifest, remains intact while the new run is in
progress. New artifacts are written only into staging; its state journal
contains the complete UUID and the identity of the publication it may replace.
On success, or on rejection by a required scientific gate, the terminal tree is
verified again and promoted over that exact preceding publication by
same-filesystem renaming. A compare-and-swap check rejects a stale concurrent
promotion. Consequently a terminal directory contains artifacts from exactly
one run. Other exceptions leave the staging journal at `status: started` for
inspection, while the deterministic result directory continues to identify
the last successfully published terminal run, if one exists.

Journal and terminal-manifest control files must be real regular files. The
artifact, publication-token, and nested-stage traversals fail closed on any
symbolic link, Windows junction, special file, unreadable directory, or entry
that changes type while it is inspected. Such a tree is never diagnosed as
promotable and cannot be published as self-contained evidence. The hierarchy
lock is likewise a no-follow regular file in a private directory owned by the
current operating-system user; it serializes every PyAges result hierarchy
operation performed by that user.

## Interrupted-stage operations

PyAges never removes an interrupted stage automatically. Inventory a result
root or any common ancestor with:

```console
pyages stages inspect <root>
pyages stages inspect <root> --json
```

Inspection is recursive and performs no explicit filesystem write. It does not
open the promotion lock. Each candidate reports:

- journal validity and the complete `run_id`;
- whether `result_manifest.json` is absent, unsealed, sealed, or invalid;
- whether the current artifacts match a valid sealed manifest;
- whether the public result tree still matches the journal's compare-and-swap
  token;
- a point-in-time `promotable_now` diagnosis and explicit issues.

`promotable_now` is diagnostic only. Normal workflow promotion repeats all
checks under the hierarchy lock. An unsealed stage may still belong to a live
workflow: age, an available lock, and `status: started` do not prove that its
owner has stopped.

After stopping or otherwise excluding the owning workflow, preserve an
unwanted stage outside automatic discovery with:

```console
pyages stages quarantine <stage-directory> --run-id <complete-uuid> --yes
```

The UUID acknowledgement prevents selection of a similarly named stage. The
command validates the managed journal and sibling relationship both before and
under the same user-global hierarchy lock used by promotion, then atomically renames
the complete tree to `.pyages-quarantine-<run-prefix>` beside it. It does not
delete or rewrite evidence. It refuses an invalid journal, link or junction,
UUID mismatch, or occupied quarantine destination. Inspect corrupted candidates
manually; PyAges deliberately provides no forced deletion or automatic purge.

Quarantine is an administrative preservation action, not an automatic resume
or recovery operation. Retain, archive, or manually remove the quarantined tree
according to local retention policy after its evidence has been reviewed.

Input loading and validation occur before staging is allocated. When a
required convergence gate rejects a completed calculation, the raised Python
exception includes a note naming the public directory to which the failed
evidence tree was promoted.

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
values, retained-row count, `acceptance_rate`, and runtime. The multi-chain
parameter table uses `burn_in` and `pilot_burn_in`; the former experimental
`burn-in`, `pilot_burn-in`, and per-chain `success_rate` spellings are not
written.

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
| `included_in_qualification` | Whether this row contributes to the ensemble gate; false for a derived quantity that is constant across all retained production draws |
| `qualified` | Whether this row passes every configured gate |

Native sampled parameters always contribute to qualification. Non-constant
derived LPM quantities also contribute, while a derived quantity that is
constant across all retained production draws is reported for completeness but
cannot supply a meaningful R-hat or ESS and therefore does not make
qualification impossible.

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
whether pooling was written, `mean_acceptance_rate`,
`minimum_acceptance_rate`, `maximum_acceptance_rate`, summed pilot and
production runtimes, and failed diagnostic counts. The historical root
`success_rate` remains the mean transition acceptance fraction because it is a
stable result-file field; no additional multi-chain success-rate aliases are
created. Interpret
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
| `run_id` | string | UUID identifying this run from staging through terminal promotion |
| `started_at_utc` | string | ISO 8601 staging-start time with UTC offset |
| `created_at_utc` | string | ISO 8601 terminal-manifest creation time with UTC offset |
| `pyages_version` | string | Installed PyAges version |
| `workflow` | string | `single_date` or `temporal` |
| `command` | array of strings | Process argument vector used for the run |
| `configuration` | object | Portable configuration path and SHA-256 digest |
| `inputs` | array of objects | Portable observation, selected LPM-resource, and tracer-resource paths with SHA-256 digests |
| `environment` | object | Python implementation, version, platform, and selected dependency versions |
| `package` | object | Distribution name/version, metadata digest, source kind, and `direct_url.json`/`RECORD` evidence when available |
| `repository` | object | Git evidence only when the imported PyAges file is tracked by that worktree; otherwise neutral fields |
| `artifacts_sha256` | object | Relative artifact path to SHA-256 digest for this run only; excludes its journal and manifest |
| `details` | object | Workflow-specific selection metadata |
| `failure` | object, optional | Exception `type` and `message`; present only when `status` is `failed` |

For `single_date`, `details` records the dataset, configured dataset year, LPM,
and completed calibration methods. If Simplex completes before an MH gate
rejects the chains, it remains listed as completed; the failed gate separately
records MH in `calibrations_attempted`. For `temporal`, details record the
dataset, mode, LPM list, and case directories entered before the terminal state.

A failure manifest is evidence that the configured qualification gate rejected
the preserved chains; it is not a successful result marker. Configuration,
input, environment, repository, and artifact hashes follow the same contract
for both terminal statuses.

The manifest fingerprints the selected direct dependencies, but it is not a
complete package lock. Recreate a qualified environment from the versioned
constraint or environment file, then use the hashes to verify the exact inputs
and artifacts. Repository fields are neutral when Git cannot establish that
the executed package source belongs to the discovered worktree; in that case,
use the `package` evidence and preserve the original wheel as well.

Incompatible changes to these documented table or manifest contracts require
the compatibility treatment described in {doc}`public-api`.
