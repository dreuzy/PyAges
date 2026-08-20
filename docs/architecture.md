# Architecture

PyAge follows the scientific calculation from inputs to results. Most users
only need the command line and YAML files; contributors can understand the
core through the five objects below.

```text
YAML + observations
        |
        v
Concentrations -> CalibrationProblem -> CalibrationMethod -> LpmDist
                         |
                         v
              Tracer + LPM -> Convolution
```

## Core responsibilities

| Component | Owns | Does not own |
|---|---|---|
| `Concentrations` | A validated observation table | File paths, calibration |
| `Tracer` | Recharge, decay, and production data | Transit-time models |
| `LpmBase` subclasses | Transit-time distributions and parameters | Tracer histories |
| `Convolution` | The forward concentration calculation | Optimization |
| `CalibrationProblem` | Observations, model, convolution, objective | Search algorithm state |
| `CalibrationMethod` | Simplex or MH execution | Input loading and reporting |
| `LpmDist` | Calibrated sample rows | Plotting and file-format logic |

Composition is deliberate. A calibration method receives a prepared problem;
it does not inherit or copy the problem's internal attributes. A convolution
receives a tracer and evaluates an LPM; it is not a tracer subclass.

## Execution flow

A single-date or temporal workflow performs the same sequence:

1. Load and validate YAML with the models in `pyage.config`.
2. Resolve paths relative to the configuration file.
3. Load observations with `Concentrations.from_file()`.
4. Prepare a `CalibrationProblem` containing the LPM, tracer convolutions, and
   objective function.
5. Run a calibration method such as Simplex or Metropolis-Hastings.
6. Store samples in `LpmDist.frame`.
7. Write standard result tables and optional figures.

The workflow modules own orchestration only. Their immutable context objects
make resolved paths and runtime options explicit. Plot modules are grouped by
purpose under `pyage.workflows.plots`; compatibility facades retain older
imports without putting plotting decisions back into the workflows.

## Package map

| Package | Purpose |
|---|---|
| `pyage.config` | User-facing configuration schemas and path resolution |
| `pyage.concentrations` | Observation tables and temporal reshaping |
| `pyage.tracer` | Typed tracer configuration and recharge histories |
| `pyage.lpm` | Model registry, transit-time models, and sample analysis |
| `pyage.convolution` | Forward scientific model |
| `pyage.calibration` | Problems, methods, priors, parameter grids, and outputs |
| `pyage.workflows` | Single-date and temporal orchestration |
| `pyage.data_io` | Stable tabular serialization boundaries |
| `pyage.cli` | Installed command-line entry point |

Shared scientific data live in `data_core`. Reusable examples live in
`examples`; site-specific studies live in `sites`. Neither directory is a
dependency of the installable `pyage` package.

## Extension points

- Add a tracer through YAML plus an optional `recharge.csv`; core Python code
  normally does not change.
- Add an LPM by implementing the `LpmBase` contract and registering it with
  `@register_lpm`.
- Add a calibration algorithm by implementing `CalibrationMethod.run(problem)`
  and returning `LpmDist`.
- Add a workflow by building an explicit context and composing existing core
  objects.

See {doc}`user-guide/adding-tracer` and {doc}`user-guide/adding-lpm` for the
supported procedures.

## Boundaries that must remain stable

Numerical refactoring is protected by analytical, characterization, and golden
tests. Result filenames and `result_manifest.json` form the workflow output
contract. Supported Python imports and the deprecation policy are listed in
{doc}`reference/public-api`.

The two diagrams in {doc}`uml/index` show the package dependencies and runtime
flow. Exhaustive UML class diagrams are intentionally omitted: they duplicate
the API reference, expose private details, and become stale without improving
understanding of this pipeline-oriented design.
