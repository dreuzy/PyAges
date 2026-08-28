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
   pyages.calibration.exploration.grid
   pyages.calibration.exploration.systematic
   pyages.convolution
   pyages.lpm.factory
   pyages.lpm.core.lpm_base
   pyages.lpm.samples.table
   pyages.lpm.core.parameter_manager
   pyages.lpm.core.registry
   pyages.tracer.protocols
   pyages.tracer.simple_tracers
   pyages.tracer.config
   pyages.tracer.tracer_root
   pyages.concentrations
   pyages.concentrations.series
   pyages.concentrations.temporal
   pyages.calibration.methods.mh
   pyages.calibration.methods.mh.prior
   pyages.calibration.methods.mh.proposals
   pyages.calibration.methods.mh.trajectory
```

## I/O, CLI, and workflows

```{eval-rst}
.. autosummary::
   :toctree: generated

   pyages.data_io.lpm_params
   pyages.data_io.lpm_results
   pyages.data_io.lpm_distribution
   pyages.data_io.concentrations
   pyages.cli.main
   pyages.workflows
   pyages.workflows.single_date
   pyages.workflows.temporal
   pyages.workflows.runtime.manifest
   pyages.reporting
   pyages.reporting.chronicles
   pyages.reporting.plots
   pyages.qualification
```

```{toctree}
:hidden:
:glob:

generated/*
```
