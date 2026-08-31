# Changelog

All notable changes to PyAges are recorded in this file.

The project follows semantic versioning for its public API from version 1.0.
Before 1.0, incompatible public changes are identified explicitly below.

## Unreleased

### Added

- Added opt-in multi-chain Metropolis--Hastings workflows with reproducible
  dispersed initialization, a separate pilot stage that learns one fixed
  pooled within-chain proposal covariance, independent production streams,
  rank-normalized split-R-hat, bulk/tail ESS, MCSE, convergence-gated pooling,
  and per-chain diagnostic/provenance outputs. Existing one-chain workflows
  remain the default.
- Added extensive scientific qualifications derived from the historical
  mono-chain single-date examples: known-truth parameter and fitted-response
  recovery for the synthetic shifted-exponential case, and converged,
  support-aware in-sample latent-fit checks for the natural Ploemeur F09 case.
- Added directly runnable, versioned multi-chain profiles for the synthetic and
  Ploemeur qualifications, plus a backward-compatible single-date `results`
  namespace so profiles using the same dataset can write to isolated studies.

### Changed

- Centralized multi-chain execution, serialization, qualification, and failure
  handling across single-date and temporal workflows.
- Stratified initialization now spans effective marginal prior mass when a
  prior is enabled (including truncated normal, bounded uniform, and empirical
  priors), instead of retrying physically stratified points outside its support.
- Multi-chain runs now verify a versioned scientific-target signature across
  every pilot and production problem and carry the realized phase seed plan in
  their result provenance before any chain pooling.
- Required convergence-gate failures now write an auditable failed workflow
  manifest that fingerprints the preserved chains, diagnostics, inputs,
  environment, and source state without marking the result complete.
- Atomic result writers now use short temporary names, preserving atomic
  replacement while avoiding avoidable Windows path-length failures in deeply
  nested calibration directories.

## 1.0.1 - 2026-08-29

### Changed

- Completed the canonical PyAges naming pass across public metadata, tracer
  contacts, migration guidance, and automated metadata checks.
- Clarified the provenance and redistribution status of the SF6 and krypton-85
  input curves. The Mendeley Data DOI remains visible to readers while its
  bot-blocked resolver is excluded precisely from automated link checking.
- Classified the short, seeded Ploemeur F09 golden as a deterministic software
  regression fixture rather than a converged scientific posterior reference,
  following an exact Windows reproduction and an acceptance/trajectory audit.
- Reduced the extensive scientific CI sentinel from daily to weekly after the
  regression baseline was reproduced on both Linux and Windows.

## 1.0 - 2026-08-28

### Changed

- Renamed the project from **PyAge** to **PyAges** before the stable 1.0
  release. The distribution, import package, CLI, environment variables,
  result-manifest fields, validation identifiers, documentation, and citation
  metadata now consistently use `pyages`/`PYAGES`; no `pyage` compatibility
  alias is provided. This is an explicit pre-1.0 compatibility change.
- Separated packaged `data_core` runtime resources from provenance workbooks
  under an explicit `sources/` tree and removed the obsolete, unreferenced
  `MHapriori-normal.txt` definition. Supported runtime resource paths are
  unchanged. The I/O tests now mirror the `pyages.data_io` package name.
- Grouped maintained repository scripts into `scripts.article`,
  `scripts.qualification`, `scripts.release`, and `scripts.maintenance`, with
  shared helpers and Windows wrappers kept in their dedicated directories.
  Article case dispatch and guarded post-processing now live in
  `scripts.article` as well, leaving `article/` for declarative reproduction
  records; orchestration tests mirror the same responsibility families.
  The former flat module paths are intentionally removed before 1.0;
  historical reproduction manifests retain their recorded paths and hashes.
- Standardized parametric-prior YAML on the canonical `uniform` and `normal`
  names and removed the pre-1.0 `gaussian` alias.
- Moved inverse-Gaussian quantile robustness from the generic SciPy adapter to
  a private model-family implementation and removed the misleading
  `scipy_safe` template-generator choice. Exact support endpoints are now
  preserved, and numerical CDF inversion is used only if SciPy returns a
  non-finite interior quantile.
- Centralized finite-width PDF construction for the three Dirac model variants,
  made the uniform model's support parameters available in its constructor, and
  clarified distribution parameter labels, units, and descriptions.
- Raised the supported Python range to 3.12-3.14 and refreshed the qualified
  runtime, development, documentation, and notebook dependency baselines.
- Added CI gates for complete extra resolution, dependency auditing, and a
  dry-run solve of the reference Conda environment.
- Migrated repository automation and project links from GitLab to GitHub.
- Replaced calibration inheritance and attribute copying with explicit
  `CalibrationProblem` and `CalibrationMethod` composition.
- Reorganized calibration internals by responsibility: systematic exploration
  now lives under `pyages.calibration.exploration`, Metropolis--Hastings under
  `pyages.calibration.methods.mh`, and synthetic recovery in
  `pyages.qualification`. Removed the former `utils`, flat MH,
  `CalibrationSyntheticTest`, and `pyages.workflows.synthetic_recovery` paths
  before 1.0. The synthetic recovery experiment
  now accepts only `sample_count`, and repository
  qualification scripts import calibration symbols directly instead of using
  abbreviated module aliases. Empirical priors now use their documented
  piecewise-linear density, missing-error defaults respect each observation
  date, and systematic output reports both actual and requested grid sizes.
- Introduced descriptive `SingleDateContext` and `TemporalContext` runtime
  contexts. Split both workflow launchers into config/context/orchestration
  modules, temporal case/calibration modules, and plotting helpers by output
  product.
- Hardened workflow completion and provenance: reruns invalidate the preceding
  success manifest, manifests are replaced atomically and hash selected LPM and
  tracer resources, normalized outputs contain the effective uncertainties,
  temporal chains use recorded fresh seeds unless a fixed seed is enabled, and
  Matplotlib retains its environment-selected desktop or headless backend.
- Rejected path traversal in workflow-derived result components, moved shared
  configuration-root and result-component rules to `pyages.config.paths`, and
  kept dataset-specific result layout in
  `pyages.workflows.single_date.paths`. It also validates custom temporal result
  roots during YAML parsing and closes Matplotlib figures when a single-date
  run aborts.
- Separated reporting, qualification, and workflow runtime services into
  dedicated modules or packages. The former flat workflow utilities, internal
  workflow plots, and synthetic recovery paths are removed before 1.0 after
  migrating repository consumers to canonical imports.
- Renamed the internal qualification class to `SyntheticRecoveryExperiment`
  without retaining a workflow-named alias. Replaced the Holten schema's
  inheritance from the generic launcher schema with explicit Pydantic
  composition while preserving its existing flat YAML format.
- Made missing-error inference explicit through `dataset.missing_error_rel`
  in single-date and temporal workflows. Result manifests now record every
  observation-error transformation, its fraction, affected rows, and count.
- Rationalized the carbon-14 runtime definitions as three intentional
  contracts (`14C` constant recharge, `14C_NH`, and `14C_SH` chronicles),
  removed the unused duplicate YAML, and aligned every definition on the
  published 5730-year half-life.
- Replaced the flag-based `Concentrations` constructor with explicit
  `from_file()` and `from_dataframe()` constructors.
- Removed the redundant `pyages.observations` loading facade. Observation
  tables now load through `Concentrations.from_file()`, while dataset filename
  conventions remain in their site-specific packages. Concentration and
  calibration workflows now import their concrete symbols directly instead of
  retaining the historical module aliases.
- Hardened concentration-table validation, error assignment, chronicle
  copying, wide-table merges, and plotting contracts; `Concentrations` is now
  exported directly from `pyages.concentrations` and its input schema is
  documented in the user guide. Removed the pre-1.0 `cv`, `ConcentrationTime`,
  `name_date`, `error_affect_*`, `names_dates`, and deep-module aliases after
  migrating the repository to the explicit `frame`, `ConcentrationChronicle`,
  and observation-key APIs.
- Reorganized concentration handling by responsibility: series, temporal
  summaries, and plotting now live in explicit `pyages.concentrations` modules,
  serialization lives in `pyages.data_io.concentrations`, and calibrated export
  orchestration lives in `pyages.reporting.chronicles`. Removed the
  former `concentrations.chronicles` and `concentrations.utils` paths without
  pre-1.0 aliases. Replaced ambiguous `tracer_names()` with explicit
  `observation_tracer_names()` and `unique_tracer_names()` methods.
- Strengthened contributor-series validation, made chronicle-summary layouts
  reject missing axes and mismatched tracer sets, stopped concentration imports
  from initializing Matplotlib, and reused each temporal convolution across
  quantiles, figures, and wide-table exports.
- Changed concentration-error sampling to a true Gaussian distribution
  truncated at zero, preventing non-physical negative draws without creating
  an artificial point mass at zero. Centralized temporal prediction-grid
  validation and posterior quantiles so concentration and workflow plots share
  one numerical summary implementation.
- Made concentration units explicit at input boundaries, rejected placeholder
  and non-canonical labels, required one exact unit per tracer, and added a
  one-time observation/model exact-match check before calibration and
  temporal prediction plots. Physical unit conversions remain explicit
  preprocessing operations and numerical loops remain unit-check free.
- Migrated the Albuquerque and Ploemeur notebooks to the canonical
  concentration constructors, `frame`, tracer-name, and observation-key APIs;
  removed their remaining legacy imports and systematic-sampling keyword
  aliases. Internal `cv`/`cdata` names and the final plotting-time `cv`
  capability check were removed without compatibility shims.
- Renamed the sample container to `LpmSampleTable` and grouped LPM sample
  storage and analysis under `pyages.lpm.samples`; model reporting and plotting
  now live under explicit `pyages.lpm.reporting` and `pyages.lpm.plotting`
  packages, with model construction exported directly from `pyages.lpm`.
- Isolated tracer YAML parsing in an immutable `TracerConfig` model.
- Added fixed and adaptive Metropolis-Hastings proposal modes with explicit
  qualification coverage.
- Split remaining high-branching core, example, site, and validation functions;
  Ruff now enforces a maximum cyclomatic complexity of 10 repository-wide.
- Separated regular parameter grids, systematic scientific evaluation, and
  sampling plots; parameter grids now support any positive dimension count.
- Calibration problems now create their optional systematic exploration only
  when requested, avoiding duplicate tracer and LPM loading in ordinary runs.
- Simplified multi-tracer convolution construction, added an explicit error
  for mismatched tracer and sampling-date counts, and reject duplicate tracer
  names before constructing a name-keyed date-range result.
- Date-range convolution now exposes its resolution and restores the original
  convolution date, prepared grid, and diagnostics after evaluating the
  requested range.
- Hardened convolution boundaries for finite observation dates, integral date
  resolutions, finite Dirac responses and ages, valid mixture weights, bounded
  CDFs, and consistent production/window-mass providers. Prepared tracer grids
  are now validated read-only snapshots, and invalid batch return types fail
  before numerical work begins.
- Added a task-oriented direct-convolution guide covering finite histories,
  batches, diagnostics, cached grids, and numerical controls, and made the LPM
  extension contract explicit for CDFs and partial first moments.
- Separated tracer-grid construction from continuous CDF/moment integration,
  leaving `Convolution` responsible for orchestration and cache state. Renamed
  the internal multi-tracer module to `pyages.convolution.multi_tracer`; the
  supported `pyages.convolution.ConvolutionTracers` import is unchanged.
- Renamed the shared continuous-convolution controls to
  `ConvolutionSettings` and `DEFAULT_CONVOLUTION_SETTINGS`, removing the
  pre-1.0 `TracerGridSettings` and `DEFAULT_TRACER_GRID_SETTINGS` names.
- Reduced the tracer contributor contract to the numerical
  `ConvolutionTracerProtocol` and removed the unused extended `TracerProtocol`
  together with the pre-1.0 `pyages.tracer.tracer_protocol` import facade.
- Removed the pre-1.0 tracer-method forwarding facade from `Convolution`:
  tracer metadata and response methods now remain on its explicit `tracer`
  collaborator. Multi-tracer batches expose `convolutions` and
  `tracer_names()` instead of the ambiguous `elements` and `element_names()`,
  and repository consumers no longer retain module or `LPM` type aliases.
- The top-level calibration package now loads its public problem class lazily,
  keeping lightweight utility imports independent from the scientific stack.
- Systematic exploration now uses the same explicit parameter names as
  `CalibrationProblem` (`observations`, `sample_count`, and data directories).
- Removed the pre-0.1 calibration, obsolete workflow launcher, plotting, and
  repository-script compatibility facades after migrating package code,
  examples, and notebooks to their canonical imports. The remaining flat
  workflow utility facades are also removed before 1.0.
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
- Aligned the stable software, manuscript campaign, archive, and release-tag
  identity on `1.0`, with a clean tagged-commit gate and DOI/archive
  synchronization checks.
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
- Standardized `pyages new lpm` on the existing lowercase module convention
  (`pyages/lpm/models/<name>.py`) and aligned its generated class and guidance.
- Added a resumable complete article campaign that writes outside the Git checkout,
  verifies the qualified TracerLPM workbook/XLL, rebuilds all article evidence,
  and produces both an editorial package and a hash-validated GMD archive. The
  Holten--Dirichlet sensitivity case is retained as a distinct robustness stage
  and is included in the archive without replacing the canonical Holten results.
- Removed mandatory historical-result inputs from the stabilized Ploemeur,
  shifted-exponential, and Holten campaigns; archived posteriors are no longer
  used for initialization, gates, or report generation.
- Split the optional historical evidence audit from fresh-campaign validation;
  the latter now checks stage completion and all package/archive hashes.
- Added a versioned two-regime forward-qualification contract: significant
  concentrations use a 0.05% symmetric-relative limit, near-zero values use an
  input-scale-normalized absolute limit, and every required case and grid
  resolution must pass.
- Centralized calibrated-distribution, statistics, and empirical-histogram TSV
  readers in `pyages.data_io` and migrated reusable runtime consumers to those
  format-aware entry points.

### Removed

- Removed the obsolete `open_file` argument from
  `pyages.data_io.lpm_results.write_lpm`; path-like and writable-stream targets
  are detected directly. This is an explicit pre-1.0 contributor-interface
  compatibility change.

### Fixed

- SciPy-backed LPM means are no longer forced positive with ``abs()``;
  incompatible negative or non-finite transit-time means now fail explicitly.
- Corrected finite-width Dirac PDF approximations to normalize the actual
  piecewise-linear area, including at zero age, reject invalid grids and pulse
  widths, and return zero consistently outside their sampling grid. Direct
  Dirac convolution remains unchanged.
- Corrected the double-Dirac `mu2` metadata to years while preserving its
  existing interpretation as the additional delay from `mu1` to the second
  point mass.
- Separated the archived SciPy 1.14.1 article-reproduction baseline from the
  SciPy 1.18.1 user constraints, added Python-version-aware SciPy compatibility
  bounds, included both environment records in future article packages, and
  documented the environments without claiming equivalence.
- Corrected active documentation of the historical forward relative
  discrepancy (non-zero reference denominator, otherwise `NaN`) without
  modifying checksum-protected reports, manifests, or results.
- Allowed standalone reproduction-archive validation without requiring the
  unrelated archive-construction arguments.

- `LpmSampleTable.best_model()` now builds a model from the single row with the best
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
- Corrected temporal configuration requirements and result-layout guidance,
  made the documented Weibull and log-normal extensions satisfy the continuous
  convolution contract, and removed stale internal notes from public-facing
  docstrings.

## 0.1.0b1 - 2026-08-19

### Changed

- Separated convolution, calibration, presentation, data I/O, and temporal
  workflow responsibilities into focused modules.
- Renamed the installable distribution to `pyage-groundwater`; the import
  package and CLI remained `pyage` at that release.
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
