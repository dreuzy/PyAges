# PyAge: A modular Python framework for groundwater age modeling

## Abstract
PyAge is a research software framework for groundwater age modeling based on
environmental tracers and lumped-parameter models (LPMs). The codebase couples
tracer chronologies with transit-time distributions through convolution and
supports parameter inference using deterministic and stochastic calibration
methods. PyAge is organized as a reusable core library with site-specific
workflows, YAML-driven configuration, and regression tests. This document
summarizes the main capabilities of the software, its ease of use for direct
applications, and its extensibility to new tracers and LPMs.

## 1. Introduction
Groundwater age estimation often relies on environmental tracers and simplified
models of subsurface transport. PyAge provides a modular implementation of
LPM-based convolution modeling, tracer handling, and calibration workflows.
The software is designed to be both scientifically transparent and practical
for applied studies, with documented configuration files, runnable examples,
and an extendable architecture.

## 2. Software architecture
We start with a brief description of the repository layout so that readers can
refer to the codebase structure throughout the paper. The organization follows
standard scientific‑software conventions, with each top‑level folder serving a
distinct role. `pyage/` is the core library and contains the scientific
implementation: LPM definitions and registries, tracer models and chronicle
handling, convolution operators, calibration algorithms, configuration models,
and shared utilities. `data_core/` hosts shared model data that are not
site‑specific, including LPM parameter YAML files (bounds, priors, defaults)
and tracer chronologies (YAML metadata and CSV recharge series). `scripts/`
provides runnable entry points for common workflows (single‑date and temporal
launchers, system checks, and benchmark runs). `examples/` contains complete,
reproducible use cases with ready‑to‑run YAML configurations and input data.
`tests/` contains unit and regression tests, including golden references for
numerical outputs. `docs/` holds architecture notes and user documentation.
Finally, `install/` provides environment specification files for reproducible
setup (e.g., conda YAML and related installation helpers).

PyAge is organized around four core components that reflect the scientific
workflow: tracers, Lumped Parameter Models (LPMs), convolution, and calibration.
Tracer and LPM classes are independent. The convolution layer combines tracer
inputs and LPM transit time distributions to compute modeled concentrations.
Calibration compares modeled and observed concentrations to infer LPM
parameters. The code uses object‑oriented design to separate concerns,
encapsulate data and algorithms, and allow extension via inheritance.

Figure 1: Core organization of PyAge.

- Core library in `pyage/` (LPMs, tracers, convolution, calibration, config).
- Shared model data in `data_core/` (LPM parameter files, tracer chronologies).
- Entry points and orchestration scripts in `scripts/`.
- Example configurations and datasets in `examples/`.
- Tests and golden references in `tests/`.
- Documentation in `docs/`.

This layout allows the same numerical engine to be reused across sites while
keeping site-specific data and scripts isolated.

## 3. Modeling capabilities
### 3.1 Lumped-parameter models (LPMs)
PyAge represents groundwater transit times with LPMs, implemented as
probability distributions. LPMs can be based on SciPy distributions or custom
implementations. Each model provides:

- Probability density and cumulative distribution functions.
- Moments and summary statistics.
- Parameter metadata (bounds, priors, units, initial values) stored in YAML.

Different LPMs can be selected per workflow, or compared within the same run.

### 3.2 Tracer chronologies and decay/production
Tracer definitions combine a recharge chronology with optional radioactive
decay and in-situ production. Tracer configuration is data-driven, with
chronicles stored as CSV and metadata stored in YAML. This enables:

- Direct use of measured or published atmospheric histories.
- Consistent unit handling across tracers.
- Optional decay and production terms for isotopic tracers.

### 3.3 Convolution-based concentrations
Tracer concentrations are computed by convolving input chronologies with the
LPM transit-time distribution. This provides a standard forward model for
single-date and multi-date observations. The same convolution engine supports
both steady-state and temporal workflows.

## 4. Calibration and inference
PyAge includes both stochastic and deterministic calibration methods:

- Metropolis-Hastings (MCMC) for probabilistic parameter inference.
- Simplex-based optimization for deterministic fitting.

Workflows can be configured to produce posterior distributions, summary
statistics, and diagnostics. The calibration layer is parameterized in YAML,
with fields such as step counts, burn-in fraction, and sampling intervals.

## 5. Usability for direct applications
PyAge is designed for applied workflows with minimal code changes:

- YAML configuration files define datasets, tracers, LPMs, and calibration
  parameters.
- CLI commands (`pyage run`, `pyage run --transient`, `pyage list`, `pyage check`)
  provide a consistent entry point when installed as a package.
- Entry points (`pyage run` and `pyage run --transient`)
  enable direct execution from the repository.
- Quickstart templates under `examples/templates/` run in short time without
  interactive plotting, suitable for rapid validation.
- Results are written to a structured output tree, facilitating comparison and
  reproducibility.

This design allows a typical application workflow to be: select a YAML config,
choose LPMs and tracers, run a calibration, and inspect standardized outputs.

## 6. Extensibility to new tracers and LPMs
PyAge was built to make extension straightforward and low-risk.

### 6.1 Adding new tracers
New tracers are added by providing:

- A YAML configuration describing units, decay, and production options.
- A CSV recharge chronicle (or a constant value).

A template generator (`pyage new tracer`) creates
the required files and stubs. This workflow allows new tracers to be inserted
without modifying the core codebase.

### 6.2 Adding new LPMs
New LPMs require:

- A Python class in `pyage/lpm/models/` implementing the distribution.
- A YAML parameter file under `data_core/data_lpm/<model>/params.yaml`.
- Registration via a decorator so the model appears in the LPM registry.

This separation keeps numerical behavior in code and calibration metadata in
data files, enabling parameter tuning without editing source code.

### 6.3 Site APIs
Site workflows can implement a shared interface (`pyage/site/base_site.py`)
to provide a consistent API for loading, validating, and running site-specific
workflows. This supports new sites while preserving a common execution pattern.

## 7. Reproducibility and testing
PyAge includes:

- Regression tests with golden reference outputs for critical workflows.
- Optional extensive tests for computationally heavy scenarios.
- Configuration-driven runs that can be repeated exactly with fixed seeds.

## 8. Conclusion
PyAge provides a complete workflow for tracer-based groundwater age modeling,
from data ingestion and forward convolution to calibration and reporting. Its
YAML-driven configuration, CLI entry points, and curated templates reduce the
barrier to direct application, while the modular design makes it feasible to
add new tracers, LPMs, and site workflows without changing the core logic. As
a result, the framework supports both reproducible research and extension to
new scientific use cases.
