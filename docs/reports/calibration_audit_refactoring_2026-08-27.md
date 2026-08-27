# Calibration audit and refactoring — 2026-08-27

## Scope

This audit covers `pyages/calibration`, its focused tests, the installed
single-date configuration boundary, and active calibration documentation. It
checks software structure and the documented scientific contract; it does not
re-qualify article posterior chains or the independent forward-model campaign.

The pre-change baseline was clean for the scoped code: 101 calibration tests
passed, four optional cases were skipped, and Ruff reported no lint or format
failures.

## Findings and resolution

| Severity | Finding | Resolution |
| --- | --- | --- |
| high | `MHConfig` could pass validation while the strict burn-in/thinning rule retained zero rows. Downstream code could therefore construct an empty calibration result. | Configuration now computes the exact retained count and rejects a zero-row chain before allocation. |
| medium | MH storage size was computed by iterating over all transitions, adding an avoidable $O(N)$ preparation pass. Monitored trajectories were also allocated for all transitions although only retained states were written. | Retained size now uses a constant-time formula; result and monitored-trajectory storage use that exact size. |
| medium | Forward uncertainty quantification deep-copied the complete bound problem, including prepared tracers and model state, solely to substitute sampled observations. This obscured which LPM instance was calibrated and scaled poorly with prepared data. | A shared observation-array boundary now accepts an explicit observation set. FUQ reuses the bound method and model while leaving the original observation container unchanged. |
| medium | Zero or boolean Simplex/FUQ run counts could produce empty result collections. | Both run counts must now be positive integers. |
| low | Proposal-specific MH fields were partly validated only after problem preparation, and incompatible fields could be silently ignored. | Proposal selection, multiplier, and mutually exclusive scale/covariance payloads are validated when `MHConfig` is created; model-dependent dimensions and positive definiteness remain checked after LPM binding. |
| low | Calibration methods repeated dataframe schema access and wall-clock timing logic. | `CalibrationMethod.observation_arrays()` centralizes ordered numeric extraction, and elapsed timings use monotonic `perf_counter()`. |
| documentation | Configuration fields existed, but no task-oriented page connected method choice, input gates, retention, outputs, diagnostics, and reproducibility. | {doc}`../user-guide/calibration` now provides that route and is linked from the user guide, configuration, methods, and output references. |

The MH target, strict retention inequality, seeded scalar componentwise proposal
protocol, objective definitions, result column order, and repeated-state
convention were intentionally preserved.

## Residual scientific and engineering risks

- Calibration assumes independent Gaussian observation errors and has no
  covariance-error likelihood.
- The sampler reports acceptance but does not calculate multi-chain $\hat R$,
  ESS, or Monte Carlo standard errors inside `LpmSampleTable`.
- Parameter prior appropriateness, identifiability, model adequacy, and tracer
  preprocessing remain analysis responsibilities rather than properties the
  software can infer.
- Empirical priors depend on external histogram families; their provenance and
  sensitivity must be archived by the calling study.
- Calibration methods remain contributor interfaces. Only
  `CalibrationProblem` is exported by the small `pyages.calibration` public
  facade.

## Verification contract

The refactoring is covered by tests for invalid Simplex counts, exact MH
retention counts, zero-retention rejection, proposal payload compatibility,
FUQ Cartesian execution, deterministic seeded behavior, objective semantics,
and calibrated output schemas. The documentation build and cross-document
contracts are part of the final verification for this change.

Final local verification:

- `python -m ruff check` on the changed Python scope: passed;
- calibration, configuration, and documentation-contract tests: 149 passed,
  four skipped;
- exhaustive small-grid comparison of the constant-time retention formula with
  the literal documented predicate: passed;
- `python -m sphinx -W --keep-going -b html docs docs/_build/html`: passed with
  warnings treated as errors.
