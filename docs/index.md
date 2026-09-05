# PyAges Documentation

PyAges is a groundwater age-dating toolkit built around environmental tracers,
lumped-parameter models (LPMs), convolution, and calibration workflows.

The documentation is organized by audience: start with the user guide to run
PyAges and use the scientific and architecture pages to understand its
contracts. {doc}`Scientific reports <reports/index>` and
{doc}`archived notes <archive/index>` remain available for traceability but
are separated from task-oriented instructions because they are not user
guides.

The development branch also provides an **Unreleased**
{doc}`multi-chain MH qualification workflow <user-guide/multichain-mh>` with
maintained synthetic, single-date, prior-active, and temporal profiles.

## Quality and validation

- {doc}`Scientific validation <science/validation>` explains the qualification
  layers, executable evidence, reported results, and limits of interpretation.
- {doc}`Testing <dev/testing>` maps each test family to its purpose, CI scope,
  evidence, and limitations.
- {doc}`Generated test inventory <dev/test-inventory>` lists every collected
  module with its type, short purpose, and case counts.
- {doc}`Continuous integration <dev/ci>` documents workflow triggers, jobs,
  permissions, artifacts, schedules, and failure semantics.

For a local build:

```bash
python -m pip install -c install/constraints.txt -e ".[docs]"
python -m sphinx -b html docs docs/_build/html
```

```{toctree}
:maxdepth: 2
:caption: Getting Started

overview
user-guide/index
```

```{toctree}
:maxdepth: 2
:caption: Concepts and Architecture

scientific-overview
scientific-methods
figures/figure1_overview
architecture
```

```{toctree}
:maxdepth: 2
:caption: Examples and Reference

examples/index
studies/index
reference/index
api/index
```

```{toctree}
:maxdepth: 1
:caption: Development

dev/index
```

```{toctree}
:maxdepth: 1
:hidden:

reports/index
archive/index
```
