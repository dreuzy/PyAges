# Selected API reference

This reference covers supported entry points and a small number of contributor
interfaces needed to extend the scientific core. The definitive compatibility
promise is {doc}`../reference/public-api`.

## Core packages

```{eval-rst}
.. autosummary::
   :toctree: generated

   pyage.config
   pyage.calibration.problem
   pyage.calibration.utils.parameter_grid
   pyage.calibration.utils.systematic_sampling
   pyage.convolution
   pyage.observations
   pyage.lpm.lpm_build
   pyage.lpm.core.lpm_base
   pyage.lpm.core.lpm_dist
   pyage.lpm.core.registry
   pyage.tracer.tracer_protocol
   pyage.tracer.config
   pyage.tracer.tracer_root
   pyage.concentrations.concentrations
   pyage.concentrations.concentrations_time
   pyage.calibration.methods.metropolis_hastings
   pyage.calibration.methods.prior
   pyage.calibration.methods.trajectory
```

## I/O, CLI, and site integration

```{eval-rst}
.. autosummary::
   :toctree: generated

   pyage.data_io.lpm_params
   pyage.data_io.lpm_results
   pyage.data_io.lpm_distribution
   pyage.cli.main
   pyage.site.base_site
```

```{toctree}
:hidden:
:glob:

generated/*
```
