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
make resolved paths and runtime options explicit. Cross-domain exports and plot
modules live under the canonical `pyages.reporting` import path, reusable
qualification experiments under `pyages.qualification`, and execution services
under `pyages.workflows.runtime`. Former flat workflow utility imports are
removed before 1.0. Shared configuration-root and result-path rules live in
`pyages.config.paths`; user-derived directory components are validated before
any directory is created.

## Package map

| Package | Purpose |
|---|---|
| `pyages.config` | User-facing configuration schemas and path resolution |
| `pyages.concentrations` | Observation tables and temporal reshaping |
| `pyages.tracer` | Typed tracer configuration and recharge histories |
| `pyages.lpm` | Model registry, transit-time models, and sample analysis |
| `pyages.convolution` | Forward scientific model |
| `pyages.calibration` | Problems, methods, priors, parameter grids, and outputs |
| `pyages.workflows` | Public single-date and temporal orchestration, plus runtime services |
| `pyages.reporting` | Reusable result tables and figures |
| `pyages.qualification` | Scientific recovery and benchmark experiments, outside the user API |
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
  RESULT --> REPORTING[reporting tables and plots]

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

The context is named `SingleDateContext` or `TemporalContext` in code; the
generic label above represents their shared role. The same core flow is used
by single-date and temporal workflows. Site code
prepares configuration and observations but does not replace the scientific
components shown here.

## Workflow source layout

The canonical module paths follow responsibilities rather than historical file
growth:

```text
pyages/
  workflows/
    single_date/   calibration, config, context, paths, reporting glue, runner
    temporal/      calibration, cases, context, runner
    runtime/       result manifest and Matplotlib session
  reporting/
    chronicles.py
    plots/         figures split by output product
  qualification.py  synthetic recovery experiment
```

`runner.py` is deliberately the orchestration entry point in both workflows.
New code imports public launchers from `pyages.workflows`, reporting helpers
from `pyages.reporting`, and the synthetic experiment from
`pyages.qualification`. The former flat workflow utilities and the internal
`pyages.workflows.plots` and `pyages.workflows.synthetic_recovery` paths are
intentionally removed.

Workflow contexts and runners use composition; none inherits from a
calibration, reporting, or configuration object. The shared Pydantic base
classes only centralize validation policy. Site schemas, including Holten,
compose the generic launcher schema instead of subclassing it. The internal
qualification object is named `SyntheticRecoveryExperiment`; no historical
`SyntheticRecoveryWorkflow` symbol is retained.
