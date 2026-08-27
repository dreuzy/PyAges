# Selected API reference

This reference covers supported entry points and a small number of contributor
interfaces needed to extend the scientific core. The definitive compatibility
promise is {doc}`../reference/public-api`.

## Core packages

```{eval-rst}
.. autosummary::
   :toctree: generated

   pyages.config
   pyages.config.loading
   pyages.calibration.methods.base
   pyages.calibration.outputs
   pyages.calibration.problem
   pyages.calibration.utils.parameter_grid
   pyages.calibration.utils.systematic_sampling
   pyages.convolution
   pyages.lpm.factory
   pyages.lpm.core.lpm_base
   pyages.lpm.samples.table
   pyages.lpm.core.parameter_manager
   pyages.lpm.core.registry
   pyages.tracer.tracer_protocol
   pyages.tracer.config
   pyages.tracer.tracer_root
   pyages.concentrations
   pyages.concentrations.chronicles
   pyages.calibration.methods.metropolis_hastings
   pyages.calibration.methods.prior
   pyages.calibration.methods.trajectory
```

## I/O, CLI, and site integration

```{eval-rst}
.. autosummary::
   :toctree: generated

   pyages.data_io.lpm_params
   pyages.data_io.lpm_results
   pyages.data_io.lpm_distribution
   pyages.cli.main
   pyages.site.base_site
   pyages.workflows
   pyages.workflows.result_manifest
```

```{toctree}
:hidden:
:glob:

generated/*
```
