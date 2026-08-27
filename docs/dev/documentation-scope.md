# Documentation Scope and Granularity

PyAges documentation follows software responsibilities and supported contracts;
it does not mirror the repository tree. A directory or source file does not
need its own online page merely because it exists.

The online documentation must let its audiences answer five questions:

1. How do I install and run PyAges?
2. How do I configure a calculation and interpret its results?
3. Which scientific assumptions, equations, units, and numerical conventions
   affect the calculation?
4. Which interfaces are supported, and how can I extend them?
5. How can I reproduce a published or qualified result?

Material that does not help answer one of these questions belongs closer to
the implementation.

## Documentation layers

| Layer | Required content | Normal location |
|---|---|---|
| User tasks | Complete procedures, runnable examples, expected outputs, and common failure modes | `docs/user-guide` and `docs/examples` |
| Scientific contracts | Equations, parameter meanings, units, assumptions, validity limits, numerical conventions, and references | `docs/science` and the scientific overview pages |
| Operational contracts | Every user-controlled configuration field, CLI option, result file, manifest schema, and compatibility rule | `docs/user-guide` and `docs/reference` |
| Public Python API | Supported modules, classes, functions, signatures, return values, exceptions, and concise examples | `docs/api`, generated from source docstrings |
| Extension contracts | The complete interface and registration procedure for adding an LPM, tracer, calibration method, or workflow | `docs/user-guide` and selected contributor API pages |
| Package architecture | One responsibility and dependency description per major domain | `docs/architecture.md` |
| Maintainer procedures | Releasing, versioning, citation, qualification, and documentation maintenance | `docs/dev` |
| Reproducible study or validation directory | Purpose, inputs, exact entry point, outputs, and evidence status | A local `README.md` in the runnable directory |
| Implementation detail | Invariants, non-obvious algorithmic choices, and reasons for a workaround | Module or object docstrings and focused source comments |
| Executable contract | Behaviors and numerical invariants that must not regress | Tests and golden references |

Reports and archived design notes provide traceability. They are evidence, not
normative instructions, and therefore remain outside the primary task-oriented
documentation.

## Required depth by PyAges domain

The architecture page gives each top-level domain a stable place without
requiring a page for every subpackage.

| Domain | Online depth required |
|---|---|
| `pyages.config` | Every supported YAML field, type, default, constraint, path rule, and validation error that users can act on |
| `pyages.concentrations` | Input table schema, units, missing-data rules, temporal reshaping, and supported constructors |
| `pyages.tracer` | Recharge, decay, production, date conventions, configuration contract, and supported tracer interface |
| `pyages.lpm` | Each selectable model's equation, parameters, bounds and scientific limitations; factory, sample-table, and extension contracts |
| `pyages.convolution` | Forward equation, discretization and boundary conventions, settings that affect results, and supported entry points |
| `pyages.calibration` | Objective and prior conventions, algorithm controls, diagnostics, result semantics, and selected extension interfaces |
| `pyages.workflows` | End-to-end procedures, inputs, outputs, manifests, failure behavior, and reproducibility controls; not every orchestration helper |
| `pyages.data_io` | Stable file layouts and schemas; Python helpers only when contributors need them |
| `pyages.cli` | Every installed command, option, default, exit behavior, and practical example; not individual command modules |
| `pyages.site` and site-specific code | Integration contract when reusable; study details otherwise stay in the relevant local README |

Subdirectories such as `core`, `utils`, `models`, `plots`, `templates`, and
`commands` do not automatically receive separate pages. Their contents appear
online only when they implement a user-visible scientific concept, a stable
interface, or a supported extension point.

The same boundary applies outside the installed package:

- `examples` documents reusable user scenarios;
- `sites` documents site-specific execution and provenance locally;
- `article` documents the exact publication-reproduction cases;
- `validation` documents independent comparison procedures and evidence;
- `scripts` provides a local catalogue of maintained entry points;
- `tests` and `audit` are evidence and are not duplicated as online tutorials.

## Public, contributor, and private interfaces

Presence in the generated API reference is not by itself a compatibility
promise. The supported public surface is defined in
{doc}`../reference/public-api`.

- A **public interface** receives a complete docstring, a generated reference
  entry, and compatibility treatment.
- A **contributor interface** receives a complete docstring and an online
  reference entry only when an extension procedure depends on it.
- A **private implementation** receives a module or object docstring when that
  helps maintenance. It does not receive an online page by default.

Private numerical code deserves unusually precise local documentation when it
contains scientific invariants, unit conversions, limiting cases, tolerances,
or stability workarounds. This precision still belongs beside the code unless
it changes how users interpret or reproduce results.

## When to create a new online page

Create a page only when at least one of these conditions is true:

- users must make a choice whose consequences need explanation;
- a scientific or file-format contract must remain stable across refactoring;
- several public objects participate in one concept or procedure;
- an extension cannot be implemented safely from the API signatures alone;
- a maintainer procedure must be performed consistently;
- published or qualification evidence must be independently reproducible.

Prefer extending an existing concept or reference page when the new material
is short. Avoid pages that merely list files, restate signatures generated by
Sphinx, or describe an internal call sequence with no stable contract.

## Documentation requirements for a change

A change is documented at the smallest layer that fully explains its impact:

- update the user guide for a changed workflow or failure mode;
- update the configuration, CLI, or output reference for any observable
  contract change;
- update the scientific pages, validation evidence, and migration note when a
  numerical convention or result changes;
- update docstrings and the selected API reference for public or contributor
  interfaces;
- update the relevant local README when a study, example, validation campaign,
  or maintained script changes;
- use only docstrings, comments, and tests for a refactor with no observable
  effect.

Before merging documentation changes, build Sphinx in warnings-as-errors mode:

```console
python -m sphinx -E -a -W --keep-going -b html docs docs/_build/html
```

Run the documentation contract tests as well:

```console
python -m pytest tests/test_public_docstrings.py tests/test_documentation_contracts.py
```
