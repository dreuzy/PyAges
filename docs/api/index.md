# API Reference

The API reference focuses on supported entry points. Internal implementation
modules are intentionally omitted: their structure may change without being a
public compatibility promise.

## Core packages

```{eval-rst}
.. autosummary::
   :toctree: generated

   pyage.config
   pyage.convolution
   pyage.observations
   pyage.lpm.lpm_build
   pyage.lpm.core.lpm_base
   pyage.lpm.core.lpm_dist
   pyage.lpm.core.registry
   pyage.tracer.tracer_protocol
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
