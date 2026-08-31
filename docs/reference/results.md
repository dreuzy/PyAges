# Result files and provenance

Public workflows write results below `PYAGES_RESULTS_DIR`, whose default is
`~/results/PyAges`. Text tables use tab-separated values (TSV) unless stated
otherwise. The set of optional files depends on the analyses and figures
enabled in the YAML configuration.

## Completion contract

Every successful public workflow writes `result_manifest.json` last. Treat a
result directory as complete only when this file exists and contains
`"status": "complete"`. A required multi-chain convergence gate writes
`"status": "failed"` after preserving and hashing its chain and diagnostic
evidence. Other execution errors can leave the manifest absent. When a new run
starts writing to a prepared result directory, it first removes the preceding
terminal manifest, so a failed rerun cannot retain a stale completion marker.

Manifest schema 2 contains:

| Field | Meaning |
| --- | --- |
| `schema_version` | Version of the result/provenance contract; currently `2`. |
| `status` | `complete`, or `failed` for rejection by a required multi-chain convergence gate. |
| `created_at_utc` | UTC terminal-manifest timestamp in ISO 8601 form. |
| `pyages_version` | Installed PyAges version. |
| `workflow` | `single_date` or `temporal`. |
| `command` | Process argument vector recorded by Python. |
| `configuration` | Portable configuration path and SHA-256 digest. |
| `inputs` | Portable input paths and SHA-256 digests. |
| `environment` | Python implementation, platform, and direct dependency versions. |
| `repository` | Git commit, dirty state, diff digest, tracked-workspace digest, and tracked file count. |
| `artifacts_sha256` | Relative filename-to-SHA-256 map for every artifact written before the manifest. |
| `details` | Workflow-specific dataset, LPM, mode, calibration, or case-directory information. |
| `failure` | Optional exception type and message for a failed convergence gate. |

For both public workflows, `details.observation_error_policy` records the
configured missing-error fraction and the ordered transformations that
produced the effective errors. Temporal runs also record `error_rel`. Each
transformation gives its method, fraction, affected row indices, and row count.

The manifest fingerprints a run; it does not by itself prove numerical or
scientific correctness. Use the validation layers in {doc}`../science/validation`.
A failure manifest makes a rejected calculation auditable; it never authorizes
use of unqualified chains as a pooled posterior.

For a source checkout, the repository section fingerprints the complete
tracked workspace. In an installed wheel without Git metadata or a Git
executable, repository fields can be empty. The `inputs` collection explicitly
hashes the observation table and every file below the selected LPM and tracer
resource directories. A publication archive must still preserve the exact
package artifact and environment in addition to the manifest.

## Single-date layout

The standard root is:

```text
<results_root>/test_cases/<dataset_filename>/
```

Common root files are:

| File | Contents |
| --- | --- |
| `concentrations.txt` | Normalized observation table: tracer, concentration, effective strictly positive absolute error, unit, and decimal sampling date. |
| `objective_function_grid.txt` | Optional sampled parameter grid and `half_log_chi_square`; see {doc}`../scientific-methods`. |
| `01_data_model_space.png` | Optional observation, reachable-space, and calibrated-model summary. |
| `02_parameter_summary.png` | Optional calibrated parameter distributions. |
| `03_objective_summary.png` | Optional objective landscape and calibrated solutions. |
| `result_manifest.json` | Completion and provenance contract described above. |

Reachable-space exploration writes:

```text
reachable_concentrations/
  parameters.txt
  c_reach.txt
```

Each enabled calibration method has its own directory, normally
`Metropolis_Hastings/` or `forward_uncertainty_quantification/`:

| File | Contents |
| --- | --- |
| `parameters_calibration.txt` | Effective sampler or optimizer settings, seeds, bounds/proposal metadata, and tolerances where applicable. |
| `results_calibration.txt` | Wall time and method-specific termination or acceptance information. |
| `lpm_dist_calibrated.txt` | Retained parameter, objective, and modeled-concentration rows. Repeated MCMC states after rejection are meaningful and must be preserved. |
| `lpm_stats_calibrated.txt` | Pandas descriptive statistics for numeric sample columns. These are not convergence diagnostics. |
| `lpm_histo_calibrated_<parameter>.txt` | One density histogram table per LPM parameter. |
| `distributions.txt` | Selected age-distribution curves used for output summaries. |
| `distributions_stats.txt` | Summary statistics for the selected age distributions. |
| `concentrations_all_models.txt` | Optional modeled tracer chronicles for selected posterior draws. |
| `concentration_times.png` | Optional modeled concentration chronicle from workflows or plotting paths that explicitly enable it; the smoke template does not emit it. |

The **Unreleased** multi-chain workflow adds separate chain directories,
diagnostics, pilot covariance, and seed provenance, and gates the pooled root
tables. Its normative layout, statuses, and failure behavior are documented in
{doc}`outputs`; they are not present in the `pyages==1.0.1` package from PyPI.

## Temporal layout

The temporal workflow root is:

```text
<results_root>/<study_name>/<dataset_stem>/<mode>/
```

It contains the effective normalized `concentrations.txt`, `span_full/` for a
span calibration, or one `date_<decimal-date>/`
directory per successive calibration. Each case then contains one directory
per LPM and the same calibration files described above. The root manifest's
`details.case_directories` lists the case directories written by that run.

## Reading results safely

- Use the exact objective column name; `obj_function`, normalized residual
  norm, and `half_log_chi_square` are different quantities.
- Do not infer convergence from `lpm_stats_calibrated.txt`. Publication runs
  require independent chains, split-$\hat R$, ESS, MCSE, and acceptance
  information as described in {doc}`../science/inference`.
- Compare the observation and tracer-history units yourself. PyAges records
  unit metadata but does not perform physical unit conversion.
- Keep `result_manifest.json` with every shared or archived result directory.
