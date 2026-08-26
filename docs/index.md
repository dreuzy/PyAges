# PyAge Documentation

PyAge is a groundwater age-dating toolkit built around environmental tracers,
lumped-parameter models (LPMs), convolution, and calibration workflows.

The documentation is organized by audience: start with the user guide to run
PyAge and use the scientific and architecture pages to understand its
contracts. {doc}`Scientific reports <reports/index>` and
{doc}`archived notes <archive/index>` remain available for traceability but
are kept outside the primary navigation because they are not user instructions.

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
reference/index
api/index
```

```{toctree}
:maxdepth: 2
:hidden:

dev/index
reports/index
archive/index
```
