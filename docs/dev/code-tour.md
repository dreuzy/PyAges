# Code tour

This page follows one PyAges calculation from its configuration file to its
result files. It is a map, not a reading list: begin with the route related to
your change and open neighbouring modules only when the code leads you there.

Complete the {doc}`getting-started` setup first. It verifies that the installed
command-line program and Python both use the repository's virtual environment.

## Vocabulary used in this tour

- **Source code** is the Python text in the `pyages/` directory.
- **YAML** is the human-readable file format used to describe a run. Indented
  keys and values specify data paths, models, methods, and output options.
- A **configuration** is the structured set of choices read from that YAML
  file.
- The **CLI** (command-line interface) is the `pyages` command entered in a
  terminal.
- A **workflow** coordinates a complete task: loading inputs, performing a
  calculation, and writing outputs.
- A **tracer** is a measured substance or signal whose concentration history
  provides information about groundwater age.
- An **LPM** (lumped-parameter model) represents the distribution of
  groundwater ages using a small set of parameters.
- **Calibration** searches for LPM parameter values whose simulated tracer
  concentrations agree with observations.

Knowing these definitions is enough to follow the software path. The scientific
documentation gives the mathematical detail behind each model and calibration
method.

## How Python code is organized here

A less experienced contributor may also need a few software terms:

- A **module** is one `.py` file. For example, `lpm_params.py` is a module.
- A **package** is a directory of related modules, such as `pyages/data_io/`.
- A **function** receives inputs, performs an action, and may return a result.
- A **class** describes a kind of object. An object can keep data between
  method calls; that retained data is its **state**.
- An **import** lets one module use a name defined by another. Imports therefore
  reveal which parts of the program depend on which other parts.
- A **side effect** is a change outside a function's return value, such as
  writing a file, changing an object, logging a message, or updating a cache.

A leading underscore means “internal implementation detail” by Python
convention. A contributor may need to edit `_container.py`, but user code should
normally import the public `Concentrations` name rather than depend on that file
path. `__init__.py` files help define which shorter public imports a package
offers.

When opening an unfamiliar module, do not begin by understanding every line.
Use this narrower reading process:

1. Read the module docstring at the top to learn its responsibility.
2. Find the public function or class called by the previous step in the flow.
3. Read its parameters, return value, raised errors, and side effects.
4. Follow only the next function calls involved in the behaviour you are
   changing.
5. Open the related test and see which input and expected result express the
   current contract.

This turns the code tour into a sequence of small questions: “What enters this
function?”, “What comes out?”, and “What observable state may it change?”

## From the command line to a workflow

A user starts a calculation with:

```bash
pyages run CONFIG
```

`CONFIG` is a placeholder for the path to a YAML file; it is not the literal
word to type. The command begins in `pyages/cli/commands/run.py` and proceeds as
follows:

```text
YAML file supplied by the user
  -> configuration checked for missing, misspelled, or invalid values
  -> runtime context prepared (data, paths, and display choices)
  -> model calibrated against observations
  -> plots and tables produced
  -> result manifest written and completed result directory published
```

At each arrow, the same user request is represented in a form better suited to
the next layer:

| Stage | Main input | Action | Main result |
| --- | --- | --- | --- |
| CLI | Words entered in the terminal | Separates the command, configuration path, and command-line overrides. | A request to start one workflow. |
| Configuration loading | YAML text | Parses text into Python values and rejects unsupported combinations. | A validated configuration object. |
| Context preparation | Validated choices and file paths | Opens observations, resolves directories, and constructs runtime objects. | A context ready for calculation. |
| Calibration | Context, LPM, and observations | Tries parameter values, predicts concentrations, and measures their fit. | Samples or optimized parameters plus diagnostics. |
| Reporting | Calibration results | Selects useful summaries and creates tables or plots. | Human-readable result files. |
| Publication | Completed files and run metadata | Verifies and moves a staged result tree into its final location. | A complete result directory and its manifest. |

Parsing, validating, calculating, and writing are separate actions on purpose.
For example, malformed YAML should fail before a long calibration starts, and
a reporting failure should not silently replace a previous complete result.

The `workflow.kind` value in the YAML chooses one of two routes:

- `single_date` compares observations for one sampling date;
- `temporal` works with observations collected at multiple dates.

For example, these two YAML lines are first read as text:

```yaml
workflow:
  kind: single_date
```

Configuration loading turns them into a typed `workflow.kind` value and checks
that `single_date` is allowed. CLI dispatch then compares that checked value and
calls the single-date runner. An unknown value is rejected at configuration
time, before observations are loaded or result files are created. Following one
field in this way is often easier than reading an entire configuration model.

The CLI reads the YAML once, applies any options explicitly supplied on the
command line, and calls the selected workflow. Keeping this decision near the
CLI means that the scientific calculation does not need to understand command-
line syntax.

### Single-date route

Read these files in order when changing a single-date run:

1. `pyages/workflows/single_date/runner.py` coordinates the whole run and
   decides which step comes next.
2. `pyages/workflows/single_date/context.py` turns the checked configuration
   into objects needed while the run is active, including loaded observations
   and output paths.
3. `pyages/workflows/single_date/calibration.py` selects reachability, Simplex,
   or Metropolis--Hastings (MH) calibration and calls the corresponding engine.
4. `pyages/workflows/single_date/reporting.py` turns completed calculations into
   concise tables and plots.

“Reachability” explores which tracer concentrations a model can produce before
fitting it. “Simplex” is a numerical optimization method. “MH” is a sampling
method described further below. You only need to enter the implementation of a
method when your change affects that method itself.

The runner is intentionally an **orchestrator**: it decides when steps happen
and how failures are handled, but delegates numerical details to calibration
objects and presentation details to reporting functions. Therefore:

- change the runner when a step must be added, removed, or reordered;
- change `context.py` when inputs must be loaded or prepared differently;
- change `calibration.py` when workflow settings must be translated differently
  for a calibration method;
- change the calibration package when the numerical method itself changes;
- change `reporting.py` when the same result should be displayed differently.

This distinction prevents a display change from accidentally altering the
scientific calculation and prevents a sampler from needing to know where plots
are saved.

### Temporal route

The temporal workflow uses a parallel structure:

1. `pyages/workflows/temporal/runner.py` coordinates the cases and publishes
   their results.
2. `pyages/workflows/temporal/context.py` checks and loads observations that
   include sampling dates.
3. `pyages/workflows/temporal/cases.py` groups observations into `span` or
   `successive` cases according to the configuration.
4. `pyages/workflows/temporal/calibration.py` calibrates one LPM for one case.

Both routes call `pyages/workflows/runtime/mh.py` for MH runs. This module is an
**adapter**: it translates workflow configuration into the objects expected by
the calibration package. It also decides whether to run one sampling chain or
several chains. Keeping that translation in one place prevents the two
workflows from implementing subtly different versions of the same policy.

An adapter generally should not reimplement the algorithm it calls. Its input
uses the vocabulary of one layer (workflow configuration), and its output uses
the vocabulary of another (MH configuration and results). When debugging this
boundary, first ask whether the wrong value was supplied to the engine or
whether the engine handled the right value incorrectly.

### Reporting labels and model-space preparation

Tracer display spelling is centralized in
`pyages/concentrations/_labels.py::pretty_tracer_name`. Both concentration
figures and reporting figures call this helper. To add another conventional
display spelling, extend that function and its focused plotting test instead of
adding a second mapping in an individual plot.

`pyages/reporting/plots/model_space.py` prepares each posterior result once and
reuses it across all pairwise panels. The deterministic maintenance benchmark
compares this path with the former repeated preparation:

```bash
python -m scripts.maintenance.benchmark_model_space
```

Keep data alignment separate from display labels. Observation values use
`tracer@date#index` keys, where `#0`, `#1`, and following suffixes distinguish
replicates. A reference table with an explicit `observation_key` column is
independent of row order; the legacy long-table fallback derives those suffixes
from row position and therefore requires matching order.

## The scientific calculation

`pyages/calibration/problem.py` brings together four elements:

1. the measured tracer concentrations;
2. the selected LPM and its parameter values;
3. the simulated tracer concentrations produced by the model;
4. an objective function that measures disagreement between simulation and
   observation.

One evaluation can be pictured as:

```text
candidate parameter values
  -> configure the LPM's groundwater-age distribution
  -> convolve that distribution with each tracer history
  -> obtain one predicted concentration per observation
  -> compare predictions with measured concentrations
  -> return one objective value to the calibration method
```

The calibration method repeats this evaluation with different candidate
parameters. Simplex uses objective values to move towards a better point. MH
uses them together with the prior to decide which samples to retain. Separating
the “evaluate one candidate” problem from the “choose the next candidate”
method allows several calibration algorithms to use the same scientific
forward calculation.

LPM construction begins in `pyages/lpm/factory.py`. A **factory** is a function
that creates the appropriate model object from a short configured name. Model
implementations live in `pyages/lpm/models/`. Their allowed parameter ranges
and prior distributions live under `data_core/data_lpm/<model>/params.yaml`.

A **prior distribution** describes which parameter values are considered
plausible before the current observations are taken into account. Changing a
prior is therefore a scientific change, even when the Python algorithm remains
the same.

Predicted concentrations ultimately pass through `pyages/convolution/`. In
plain terms, convolution combines a tracer's history with the groundwater-age
distribution represented by the LPM. Small numerical changes in this package
can affect many models, so run scientific reference tests as well as local unit
tests when changing it.

## Two examples of data entering the scientific core

External files and tables are flexible: they may contain missing columns,
misspelled values, text where a number is expected, or unsupported units. The
numerical code would become complicated if it had to check all of those cases
inside every calculation. PyAges therefore validates data at **boundaries** and
passes a simpler, predictable representation inward.

### LPM parameter files

`pyages/data_io/lpm_params.py` is responsible for reading one model's
`params.yaml`. Its actions are deliberately ordered:

```text
model name and data directory
  -> construct the absolute params.yaml path
  -> read the exact file bytes
  -> decode them as UTF-8 and parse YAML
  -> validate the document against the LPM parameter schema
  -> cache the validated result for later calls
  -> return an immutable schema or a defensive document copy
```

The **schema** states which fields, value types, and relationships are allowed.
Parsing answers “is this valid YAML?”, whereas schema validation answers “is
this valid PyAges LPM configuration?” Those are different failure modes.

The cache avoids decoding and validating unchanged content repeatedly. Its
fingerprint is the complete file content, not only a modification time. If the
bytes change, the cached entry no longer matches and the file is parsed again.
A defensive copy prevents a caller that edits the returned dictionary from
silently changing the cached source of truth.

When changing this path, decide which responsibility is affected:

- filesystem, decoding, or cache behaviour belongs in `lpm_params.py`;
- the meaning and relationships of fields belong in
  `pyages/data_io/_lpm_parameter_schema.py`;
- a particular model's scientific values belong in its
  `data_core/data_lpm/<model>/params.yaml` file.

### Observation tables

`pyages/concentrations/_container.py` defines the internal implementation of
`Concentrations`. A **container** is an object that keeps related values and
enforces rules about them. Construction does more than retain a pandas
`DataFrame`:

1. It copies the caller's table so later normalization cannot unexpectedly
   modify the caller's object.
2. It supplies a zero-valued error column when that optional column is absent.
3. It verifies required and duplicate columns before converting values.
4. It converts concentrations, errors, and dates to finite numeric values.
5. It rejects negative errors and empty tracer names, and normalizes units.
6. Only after every check succeeds does it replace its internal frame with the
   canonical columns and a fresh row index.

The last ordering is important. Validation works on a separate copy and
publishes it only at the end, so a late error does not leave the container
partly normalized. Downstream calibration can then rely on a stable table
shape instead of repeating input checks.

Tests for these boundary actions should cover both successful normalization and
rejection of invalid input. A test that only checks one valid table would not
protect the error behaviour on which callers also rely.

## Metropolis--Hastings files

Metropolis--Hastings (MH) repeatedly proposes parameter values, compares their
fit with observations, and accepts or rejects each proposal according to the
method's probability rule. The implementation is split so that each file has a
limited job:

```text
current parameter sample
  -> proposal code suggests a candidate
  -> prior code evaluates whether the candidate is plausible
  -> calibration problem evaluates its fit to observations
  -> sampler applies the MH acceptance rule
  -> accepted candidate, or repeated current value, is stored in the chain
  -> repeat
```

Rejecting a candidate is a normal part of MH, not an exception. The current
value is recorded again and the chain continues. An exception instead means
that the algorithm could not validly perform the step, for example because an
input contract was violated.

- `pyages/calibration/methods/mh/config.py` stores the fixed choices for one
  chain, such as its length and proposal settings.
- `pyages/calibration/methods/mh/sampler.py` performs the repeated propose-and-
  accept loop for one chain. A **chain** is the ordered sequence of samples
  produced by that loop.
- `pyages/calibration/methods/mh/prior.py` and `_prior_marginals.py` evaluate the
  configured prior distributions.
- `pyages/calibration/methods/mh/ensemble.py` coordinates initialization, pilot
  runs, and production when several chains are requested. Here, an **ensemble**
  simply means a group of independently started chains.
- `pyages/calibration/methods/mh/diagnostics.py` decides whether those chains
  provide sufficiently stable evidence.
- `pyages/calibration/methods/mh/results.py` defines the result records returned
  to the workflow.

Initialization chooses valid starting values. Pilot runs provide evidence for
preparing the production run, while production creates the samples intended
for downstream results. Keeping these stages explicit makes it possible to
test that temporary or mutable state from one stage is not accidentally reused
by another.

The diagnostics use several standard statistical measures:

- **R-hat** compares variation within chains with variation between chains;
  values near one support the conclusion that the chains behave similarly.
- **ESS** (effective sample size) estimates how much independent information is
  present after accounting for correlation between successive samples.
- **MCSE** (Monte Carlo standard error) estimates uncertainty caused by using a
  finite sample from the algorithm.

These diagnostics are related checks, not interchangeable scores. Do not change
their thresholds merely to make a run qualify; explain and test any policy
change. They describe the reliability of the sampling process; they do not by
themselves prove that the selected LPM is the correct scientific model or that
the observations are free from bias.

## Where to make common changes

The final column shows a focused test command. Running only the closest tests
while editing usually gives feedback much faster than the complete suite.

| Goal | Start here | First check to run |
| --- | --- | --- |
| Add or change a YAML option | `pyages/config/models.py` | `python -m pytest -q tests/config` |
| Change CLI selection or overrides | `pyages/cli/commands/run.py` | `python -m pytest -q tests/cli` |
| Change the order of workflow steps | the relevant `runner.py` | `python -m pytest -q tests/workflows` |
| Change one-chain MH behaviour | `pyages/calibration/methods/mh/sampler.py` | `python -m pytest -q tests/calibration` |
| Change multi-chain policy | `pyages/calibration/methods/mh/ensemble.py` and `diagnostics.py` | `python -m pytest -q tests/calibration tests/workflows` |
| Change LPM parameter loading or caching | `pyages/data_io/lpm_params.py` | `python -m pytest -q tests/data_io/test_lpm_params.py` |
| Change valid LPM parameter fields or relationships | `pyages/data_io/_lpm_parameter_schema.py` | `python -m pytest -q tests/data_io/test_lpm_params.py` |
| Change observation normalization or selection | `pyages/concentrations/_container.py` | `python -m pytest -q tests/concentrations` |
| Add an LPM | `pyages/lpm/models/` and `data_core/data_lpm/` | `python -m pytest -q tests/lpm` |
| Change concentration calculations | `pyages/convolution/` | `python -m pytest -q tests/convolution` |
| Change result files | `pyages/data_io/` and `pyages/workflows/runtime/manifest.py` | `python -m pytest -q tests/data_io tests/workflows` |
| Change tracer display spelling | `pyages/concentrations/_labels.py` | `python -m pytest -q tests/concentrations tests/examples/test_example_summary_plots.py` |
| Change model-space preparation | `pyages/reporting/plots/model_space.py` | `python -m pytest -q tests/examples/test_example_summary_plots.py tests/scripts/maintenance/test_benchmark_model_space.py` |

The paths are starting points, not ownership walls. A behaviour may have tests
in more than one directory, especially when it connects configuration,
calibration, and reporting.

In these commands, the path after `pytest -q` controls collection. A single
test file gives the fastest narrow feedback; a directory includes neighbouring
contracts; the full profile later checks interactions with the rest of the
project. Passing the narrow test is therefore the beginning of validation, not
the final evidence.

## Important contracts and why they exist

A **contract** here means behaviour on which another part of the program or a
user relies. Preserve these behaviours unless the change deliberately updates
the contract, its tests, and its documentation:

- Configuration models reject unknown YAML keys. A misspelling therefore stops
  the run instead of silently selecting a default value.
- Each ensemble stage and chain receives a fresh calibration problem. Mutable
  state from one chain cannot leak into another.
- Information about failed convergence is saved before an error is raised. A
  user can inspect why the run failed rather than receiving only an exception.
- Samples from several chains are combined only when the configured diagnostic
  policy permits it. Unqualified output is not presented as a successful
  calibrated result.
- Result files are first written to a staging directory and then moved into
  place as one completed unit. This is **atomic publication**: an interrupted
  run cannot replace a previous valid result with a half-written directory.
- The **public API** is the deliberately supported set of Python imports for
  users. It is smaller than the internal file tree so implementation details can
  change safely. Check `tests/test_public_api.py` before exposing a new name.

## Checking the change

During editing, combine the focused test from the table with:

```bash
python -m scripts.maintenance.check_dev quick
```

This fast command runs code-quality checks such as Ruff and Pyright. The
{doc}`getting-started` guide explains each tool and how it differs from Pytest.

Before proposing the change, run:

```bash
python -m scripts.maintenance.check_dev full
```

The full profile adds the standard test suite and a strict documentation build.
Tests marked `extensive` exercise longer scientific qualification cases and are
kept separate from the normal suite; {doc}`testing` explains when they are
required.
