# Result files and provenance

Public workflows write results below `PYAGE_RESULTS_DIR`, whose default is
`~/results/PyAge`. Text tables use tab-separated values (TSV) unless stated
otherwise. The set of optional files depends on the analyses and figures
enabled in the YAML configuration.

## Completion contract

Every successful public workflow writes `result_manifest.json` last. Treat a
result directory as complete only when this file exists and contains
`"status": "complete"`.

Manifest schema 2 contains:

| Field | Meaning |
| --- | --- |
| `schema_version` | Version of the result/provenance contract; currently `2`. |
| `status` | `complete`; incomplete workflows do not write a success manifest. |
| `created_at_utc` | UTC completion timestamp in ISO 8601 form. |
| `pyage_version` | Installed PyAge version. |
| `workflow` | `single_date` or `temporal`. |
| `command` | Process argument vector recorded by Python. |
| `configuration` | Portable configuration path and SHA-256 digest. |
| `inputs` | Portable input paths and SHA-256 digests. |
| `environment` | Python implementation, platform, and direct dependency versions. |
| `repository` | Git commit, dirty state, diff digest, tracked-workspace digest, and tracked file count. |
| `artifacts_sha256` | Relative filename-to-SHA-256 map for every artifact written before the manifest. |
| `details` | Workflow-specific dataset, LPM, mode, calibration, or case-directory information. |

The manifest fingerprints a run; it does not by itself prove numerical or
scientific correctness. Use the validation layers in {doc}`../science/validation`.

For a source checkout, the repository section fingerprints the complete
tracked workspace, which includes packaged tracer histories and LPM parameter
files. In an installed wheel without Git metadata, repository fields can be
empty. The current public workflows list the observation table explicitly in
`inputs`; they do not enumerate every tracer and LPM resource there. A
publication archive must therefore preserve the exact package artifact and
scientific resources in addition to the manifest.

## Single-date layout

The standard root is:

```text
<results_root>/test_cases/<dataset_filename>/
```

Common root files are:

| File | Contents |
| --- | --- |
| `concentrations.txt` | Normalized observation table: tracer, concentration, absolute error, unit, and decimal sampling date. |
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

## Temporal layout

The temporal workflow root is:

```text
<results_root>/<study_name>/<dataset_stem>/<mode>/
```

It contains `span_full/` for a span calibration or one `date_<decimal-date>/`
directory per successive calibration. Each case then contains one directory
per LPM and the same calibration files described above. The root manifest's
`details.case_directories` lists the case directories written by that run.

## Reading results safely

- Use the exact objective column name; `obj_function`, normalized residual
  norm, and `half_log_chi_square` are different quantities.
- Do not infer convergence from `lpm_stats_calibrated.txt`. Publication runs
  require independent chains, split-$\hat R$, ESS, MCSE, and acceptance
  information as described in {doc}`../science/inference`.
- Compare the observation and tracer-history units yourself. PyAge records
  unit metadata but does not perform physical unit conversion.
- Keep `result_manifest.json` with every shared or archived result directory.
