# API Reference

The API reference is generated during the Sphinx build from the package
structure and the docstrings currently present in the codebase.

## Core packages

```{eval-rst}
.. autosummary::
   :toctree: generated
   :recursive:

   pyage.cli
   pyage.config
   pyage.lpm
   pyage.tracer
   pyage.convolution
   pyage.concentrations
   pyage.calibration
   pyage.observations
   pyage.data_io
   pyage.site
```

## Runtime and shared constants

```{eval-rst}
.. autosummary::
   :toctree: generated

   pyage.global_parameters
```

```{toctree}
:hidden:
:glob:

generated/*
```
