# PyAge Documentation

PyAge is a groundwater age-dating toolkit built around environmental tracers,
lumped-parameter models (LPMs), convolution, and calibration workflows.

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
reference/index
```

```{toctree}
:maxdepth: 2
:caption: Scientific and Technical Documentation

scientific-overview
figures/figure1_overview
examples/index
architecture
uml/index
dev/index
api/index
```

```{toctree}
:maxdepth: 1
:caption: Scientific Audits and Migration Notes

convolution-method-evolution-report
scientific-migration-ig-decay
pyage-scientific-audit
pyage-tracerlpm-targeted-comparison
tracerlpm-visual-studio-feasibility
```
