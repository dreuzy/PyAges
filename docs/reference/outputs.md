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

Both public workflows write `result_manifest.json` **last**, after every
requested table and figure has been produced. A directory without a manifest
whose `status` is `complete` is not a completed workflow result, even if it
contains apparently usable intermediate files.

Workflows reuse their deterministic output directory and do not remove files
left by an earlier run. For qualification or publication evidence, start from
an empty result directory or archive the preceding run first. The new manifest
hashes every file present below the result directory, including any file left
from an earlier run.

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
`-- result_manifest.json                      # successful workflow only
```

`concentrations.txt` is always written. It is the normalized long-form
observation table used by the workflow and follows the schema in
{doc}`../user-guide/concentrations`.

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
replaced by an underscore and insignificant trailing zeros are removed.

```text
<mode>/
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
`-- result_manifest.json                       # successful workflow only
```

The manifest belongs to the `<mode>` directory and covers every date/LPM case
below it. `figures.concentrations_2d` has an effect only when
`figures.distributions` is also true. The `Metropolis_Hastings` presentation
subdirectory is produced only when `figures.temporal` is true; it is distinct
from the LPM directory that holds the calibration tables.

## Calibration table schemas

The same calibration files are used by both workflows.

### `parameters_calibration.txt`

A headerless two-column key/value table containing the resolved algorithm
configuration. Metropolis-Hastings records the transition count, burn-in,
thinning, proposal, seed, initialization source, and resolved prior metadata.
Simplex/FUQ records the method, tolerances, initialization count and seeds, and
the uncertainty sample count where applicable. Values that are lists or
mappings use their Python text representation.

### `results_calibration.txt`

A headerless two-column key/value table. All methods write `time_perform` in
seconds. Metropolis-Hastings also writes `success_rate`, the fraction of
accepted transitions. Simplex/FUQ writes aggregate optimizer run, iteration,
evaluation, and convergence fields.

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
| `status` | string | `complete`; the manifest is written only after success |
| `created_at_utc` | string | ISO 8601 creation time with UTC offset |
| `pyages_version` | string | Installed PyAges version |
| `workflow` | string | `single_date` or `temporal` |
| `command` | array of strings | Process argument vector used for the run |
| `configuration` | object | Portable configuration path and SHA-256 digest |
| `inputs` | array of objects | Portable scientific-input paths and SHA-256 digests |
| `environment` | object | Python implementation, version, platform, and selected dependency versions |
| `repository` | object | Git revision, dirty state, status, diff digest, and tracked-workspace digest when available |
| `artifacts_sha256` | object | Relative artifact path to SHA-256 digest; excludes the manifest itself |
| `details` | object | Workflow-specific selection metadata |

For `single_date`, `details` records the dataset, LPM, and completed calibration
methods. For `temporal`, it records the dataset, mode, LPM list, and case
directories.

The manifest fingerprints the selected direct dependencies, but it is not a
complete package lock. Recreate a qualified environment from the versioned
constraint or environment file, then use the hashes to verify the exact inputs
and artifacts. Repository fields can be null when Git metadata is unavailable.

Incompatible changes to these documented table or manifest contracts require
the compatibility treatment described in {doc}`public-api`.
