# Changelog

All notable changes to PyAge are recorded in this file.

The project follows semantic versioning for its public API from version 1.0.
Before 1.0, incompatible public changes are identified explicitly below.

## Unreleased

### Changed

- Replaced calibration inheritance and attribute copying with explicit
  `CalibrationProblem` and `CalibrationMethod` composition.
- Introduced typed workflow contexts and split plotting helpers by purpose.
- Replaced the flag-based `Concentrations` constructor with explicit
  `from_file()` and `from_dataframe()` constructors.
- Reduced `LpmDist` to sample storage and orchestration; analysis, plotting,
  and serialization now live in focused modules. `dist()` remains available
  as a compatibility alias for `frame`.
- Isolated tracer YAML parsing in an immutable `TracerConfig` model.
- Added fixed and adaptive Metropolis-Hastings proposal modes with explicit
  qualification coverage.
- Split remaining high-branching core, example, site, and validation functions;
  Ruff now enforces a maximum cyclomatic complexity of 10 repository-wide.

### Fixed

- `LpmDist.get_best_lpm()` now builds a model from the single row with the best
  objective instead of combining independent column minima.
- Invalid observation tables and tracer configuration values now fail early
  with contextual exceptions.

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
