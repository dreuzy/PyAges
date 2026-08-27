# Changelog

All notable changes to PyAge are recorded in this file.

The project follows semantic versioning for its public API from version 1.0.
Before 1.0, incompatible public changes are identified explicitly below.

## Unreleased

### Changed

- Raised the supported Python range to 3.12-3.14 and refreshed the qualified
  runtime, development, documentation, and notebook dependency baselines.
- Added CI gates for complete extra resolution, dependency auditing, and a
  dry-run solve of the reference Conda environment.
- Migrated repository automation and project links from GitLab to GitHub.
- Added read-only GitHub workflow permissions, immutable action references,
  protected collaboration metadata, release-candidate validation, and public
  contribution and security guidance.
- Added automated consistency checks for release identity and for qualified
  pip and Conda versions against the declared runtime compatibility ranges.
- Replaced calibration inheritance and attribute copying with explicit
  `CalibrationProblem` and `CalibrationMethod` composition.
- Introduced typed workflow contexts and split plotting helpers by purpose.
- Replaced the flag-based `Concentrations` constructor with explicit
  `from_file()` and `from_dataframe()` constructors.
- Reduced `LpmDist` to sample storage and orchestration; analysis, plotting,
  and serialization now live in focused modules accessed directly, without
  compatibility methods on the sample container.
- Isolated tracer YAML parsing in an immutable `TracerConfig` model.
- Added fixed and adaptive Metropolis-Hastings proposal modes with explicit
  qualification coverage.
- Split remaining high-branching core, example, site, and validation functions;
  Ruff now enforces a maximum cyclomatic complexity of 10 repository-wide.
- Separated regular parameter grids, systematic scientific evaluation, and
  sampling plots; parameter grids now support any positive dimension count.
- Calibration problems now create their optional systematic exploration only
  when requested, avoiding duplicate tracer and LPM loading in ordinary runs.
- Simplified multi-tracer convolution construction and added an explicit error
  for mismatched tracer and sampling-date counts.
- Date-range convolution now exposes its resolution and restores the original
  convolution date after evaluating the requested range.
- The top-level calibration package now loads its public problem class lazily,
  keeping lightweight utility imports independent from the scientific stack.
- Systematic exploration now uses the same explicit parameter names as
  `CalibrationProblem` (`observations`, `sample_count`, and data directories).
- Removed the pre-0.1 calibration, workflow, plotting, and repository-script
  compatibility facades after migrating package code, examples, and notebooks
  to their canonical imports.
- Replaced historical internal names such as `MH_step`, `MH_Trajectory`,
  `cdata`, and `random_each` with the canonical proposal, trajectory,
  observation, and row-selection interfaces.
- Replaced vague Metropolis-Hastings `legacy_*` labels with explicit
  `componentwise` and `scipy_ig` coordinate protocols. The seeded scalar-draw
  sequence is unchanged and now has a direct regression test.
- Centralized inverse-Gaussian coordinate transforms and moved the
  Ploemeur-article prior from the generic calibration package into the
  site-specific benchmark layer, retaining its exact support and Jacobian.
- Removed the unreachable young/old convolution correction, unused output and
  plotting methods, dead parameters, and other unconsumed implementation
  surfaces. Calibration objectives now always contain physical forward-model
  concentrations.
- Renamed the misleading internal `RMSE` helper to
  `normalized_residual_norm`, `arange_n` to `subdivide_interval`, and the
  systematic-map field `log-ojf` to `half_log_chi_square`.
- Corrected the unconsumed `Simplex_init_multipes` and `init_mutiples` labels
  to `Simplex_multi_start` and `initialization_count` without retaining aliases.
- Added a GMD-oriented scientific methods contract covering convolution
  equations and boundaries, grid tolerances, inverse-Gaussian coordinates,
  objective transformations, Metropolis-Hastings acceptance, and traceability
  to tests and qualification reports.
- Distinguished the released `0.1.0b1` software identity from the manuscript's
  future “PyAge v1.0” target and documented the DOI/archive synchronization
  gate.
- Upgraded public workflow manifests to schema 2. They are now written only
  after successful completion and include input, artifact, environment, Git
  diff, and complete tracked-workspace fingerprints.
- Made componentwise MH proposal provenance immutable in `MHConfig`; removed
  the unused sampler-level `lpm_number` field and mutable step selectors.
- Defined the publication evidence split explicitly: Git tracks code,
  configurations, manifests, and archive pointers, while an immutable
  scientific archive carries the numerical results needed to audit the paper.
- Added drift tests that validate the documented YAML examples and keep the
  documented LPM inventory synchronized with the runtime registry.
- Added a resumable whole-article campaign that writes outside the Git checkout,
  verifies the qualified TracerLPM workbook/XLL, rebuilds all article evidence,
  and produces both an editorial package and a hash-validated GMD archive.
- Removed mandatory historical-result inputs from the stabilized Ploemeur,
  shifted-exponential, and Holten campaigns; archived posteriors are no longer
  used for initialization, gates, or report generation.

### Fixed

- Updated the didactic summary plots to consume the current `LpmDist.frame`
  interface, restoring the synthetic recovery example after the removal of the
  legacy `dist()` accessor.
- Made synthetic-input regeneration explicit (`--regenerate`) so an ordinary
  teaching run cannot silently rewrite versioned scientific reference files.
- Disabled the unqualified simplex/FUQ branch in the Albuquerque starter
  configuration; its placeholder zero uncertainties did not provide a robust
  optimizer-convergence example.
- `LpmDist.best_model()` now builds a model from the single row with the best
  objective instead of combining independent column minima.
- Invalid observation tables and tracer configuration values now fail early
  with contextual exceptions.
- Corrected the current shifted-exponential generator and article package to
  label and name the publication output consistently as Table 4.
- Parametric and empirical priors now return exact zero density outside their
  support instead of flooring it to `1e-300` before log evaluation.
- Simplex now enforces LPM bounds, rejects unsuccessful optimizer termination,
  and recomputes parameters, objective, and concentrations at the same optimum
  before persisting a joint result row.
- MCMC monitoring now records the correctly signed negative log-posterior and
  whether each retained transition was accepted. Explicit initial parameters
  now take precedence over prior-MAP initialization.
- Generic MH output no longer writes an implicit shared `none.txt` posterior;
  posterior-to-prior export is an explicit site-workflow operation.

## 0.1.0b1 - 2026-08-19

### Changed

- Separated convolution, calibration, presentation, data I/O, and temporal
  workflow responsibilities into focused modules.
- Renamed the installable distribution to `pyage-groundwater`; the import
  package and CLI remain `pyage`.
- Made core LPM and tracer data explicit package resources.
- Removed filesystem creation as a side effect of importing path settings.
- Centralized the package and CLI version in `pyage/_version.py`.
- Moved the single-date workflow and its plotting/configuration helpers into
  the installable package; repository scripts now provide compatibility imports.
- Pinned a portable qualified dependency set while retaining broader runtime
  compatibility ranges in package metadata.

### Added

- GitLab checks for linting, supported Python versions, strict documentation,
  distributions, and isolated wheel smoke tests.
- Public API, compatibility, contribution, security, and release guidance.
- Data provenance and redistribution guidance for tracer histories and example
  observations.
- A reproducible PyAge–TracerLPM validation runner and compact reference cases.
- A versioned `result_manifest.json` in public workflow output directories.
- Coverage, formatting, TracerLPM benchmark, .NET compilation, and real
  installed-workflow checks in continuous integration.

### Fixed

- Restored compatibility with the declared NumPy 1.x minimum when normalizing
  empirical prior distributions.
- Prevented calibration diagnostics and concentration chronicles from opening
  Matplotlib figures when figure output is disabled.
- Restored Python 3.9 imports for annotations using PEP 604 union syntax.
- Preserved configuration-relative data paths when CLI overrides create a
  temporary YAML file and in the installed temporal workflow.
- Rejected ambiguous or missing concentration inputs and unsupported
  calibration dimensions with explicit errors.

### Removed

- Generated example outputs, notebook outputs, local runner configurations, and
  publisher PDFs from the versioned source tree.
