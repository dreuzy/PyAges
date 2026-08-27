# Architecture

PyAges follows the scientific calculation from inputs to results. Most users
only need the command line and YAML files; contributors can understand the
core through the five objects below.

```text
YAML + observations
        |
        v
Concentrations -> CalibrationProblem -> CalibrationMethod -> LpmSampleTable
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
| `LpmSampleTable` | Calibrated sample rows | Plotting and file-format logic |

Composition is deliberate. A calibration method receives a prepared problem;
it does not inherit or copy the problem's internal attributes. A convolution
receives a tracer and evaluates an LPM; it is not a tracer subclass.

## Execution flow

A single-date or temporal workflow performs the same sequence:

1. Load and validate YAML with the models in `pyages.config`.
2. Resolve paths relative to the configuration file.
3. Load observations with `Concentrations.from_file()`.
4. Prepare a `CalibrationProblem` containing the LPM, tracer convolutions, and
   objective function.
5. Run a calibration method such as Simplex or Metropolis-Hastings.
6. Store samples in `LpmSampleTable.frame`.
7. Write standard result tables and optional figures.

The workflow modules own orchestration only. Their immutable context objects
make resolved paths and runtime options explicit. Plot modules are grouped by
purpose under the canonical `pyages.workflows.plots` import path.

## Package map

| Package | Purpose |
|---|---|
| `pyages.config` | User-facing configuration schemas and path resolution |
| `pyages.concentrations` | Observation tables and temporal reshaping |
| `pyages.tracer` | Typed tracer configuration and recharge histories |
| `pyages.lpm` | Model registry, transit-time models, and sample analysis |
| `pyages.convolution` | Forward scientific model |
| `pyages.calibration` | Problems, methods, priors, parameter grids, and outputs |
| `pyages.workflows` | Single-date and temporal orchestration |
| `pyages.data_io` | Validated YAML loading and stable result-file serialization |
| `pyages.cli` | Installed command-line entry point |

Shared scientific data live in `data_core`. Reusable examples live in
`examples`; site-specific studies live in `sites`. Neither directory is a
dependency of the installable `pyages` package.

## Extension points

- Add a tracer through YAML plus an optional `recharge.csv`; core Python code
  normally does not change.
- Add an LPM by implementing the `LpmBase` contract and registering it with
  `@register_lpm`.
- Add a calibration algorithm by implementing `CalibrationMethod.run(problem)`
  and returning `LpmSampleTable`.
- Add a workflow by building an explicit context and composing existing core
  objects.

See {doc}`user-guide/adding-tracer` and {doc}`user-guide/adding-lpm` for the
supported procedures.

## Boundaries that must remain stable

Numerical refactoring is protected by analytical, characterization, and golden
tests. Result filenames and `result_manifest.json` form the workflow output
contract. Supported Python imports and the deprecation policy are listed in
{doc}`reference/public-api`.

The maintained diagrams below summarize package dependencies and runtime flow.
Exhaustive UML class diagrams are intentionally omitted: they duplicate the API
reference, expose private details, and become stale without improving
understanding of this pipeline-oriented design.

## Package dependency diagram

```{mermaid}
flowchart TB
  DATA[data_core] --> TRACER[tracer]
  DATA --> LPM[lpm]

  CLI[cli] --> WF[workflows]
  CONFIG[config] --> WF
  CONC[concentrations] --> PROBLEM[CalibrationProblem]
  WF --> CONC
  WF --> PROBLEM

  TRACER --> CONV[convolution]
  LPM --> CONV
  CONV --> PROBLEM
  PROBLEM --> METHODS[calibration methods]
  METHODS --> RESULT[LpmSampleTable]
  RESULT --> IO[data_io]
  RESULT --> PLOTS[workflow plots]

  EXAMPLES[examples and sites] -. configure .-> CLI
  TESTS[tests] -. qualify .-> CONV
  TESTS -. qualify .-> METHODS
```

Arrows represent runtime dependencies or data flow. `examples` and `sites`
consume the installable core; the core does not import them.

## Runtime diagram

```{mermaid}
flowchart TB
  YAML[YAML] --> CFG[Validated config]
  OBSFILE[Observation table] --> OBS[Concentrations]
  CFG --> CTX[WorkflowContext]
  OBS --> PROBLEM[CalibrationProblem]
  CTX --> PROBLEM
  TR[Tracer] --> CONV[Convolution]
  LPM[LPM] --> CONV
  CONV --> PROBLEM
  PROBLEM --> METHOD[CalibrationMethod]
  METHOD --> SAMPLES[LpmSampleTable.frame]
  SAMPLES --> STATS[Analysis]
  SAMPLES --> FILES[TSV + manifest]
  SAMPLES --> FIGS[Optional figures]
```

The same core flow is used by single-date and temporal workflows. Site code
prepares configuration and observations but does not replace the scientific
components shown here.
