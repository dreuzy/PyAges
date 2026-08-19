# Changelog

All notable changes to PyAge are recorded in this file.

The project follows semantic versioning for its public API from version 1.0.
Before 1.0, incompatible public changes are identified explicitly below.

## Unreleased

## 0.1.0b1 - 2026-08-19

### Changed

- Separated convolution, calibration, presentation, data I/O, and temporal
  workflow responsibilities into focused modules.
- Renamed the installable distribution to `pyage-groundwater`; the import
  package and CLI remain `pyage`.
- Made core LPM and tracer data explicit package resources.
- Removed filesystem creation as a side effect of importing path settings.
- Centralized the package and CLI version in `pyage/_version.py`.

### Added

- GitLab checks for linting, supported Python versions, strict documentation,
  distributions, and isolated wheel smoke tests.
- Public API, compatibility, contribution, security, and release guidance.
- Data provenance and redistribution guidance for tracer histories and example
  observations.
- A reproducible PyAge–TracerLPM validation runner and compact reference cases.

### Fixed

- Restored compatibility with the declared NumPy 1.x minimum when normalizing
  empirical prior distributions.
- Prevented calibration diagnostics and concentration chronicles from opening
  Matplotlib figures when figure output is disabled.

### Removed

- Generated example outputs, notebook outputs, local runner configurations, and
  publisher PDFs from the versioned source tree.
