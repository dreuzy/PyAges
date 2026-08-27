# Selected API reference

This reference separates the supported user surface from contributor and
research interfaces. Presence in the second group does not create a
compatibility promise. The definitive policy is
{doc}`../reference/public-api`.

## Supported public Python API

The command-line contract is documented separately in
{doc}`../user-guide/cli-flags`.

Within the module pages below, the compatibility contract covers
`pyage.lpm.lpm_build.lpm_build`,
`pyage.lpm.core.registry.list_available_lpms`,
`pyage.tracer.tracer_root.Tracer`, and
`pyage.concentrations.concentrations.Concentrations` as specified in
{doc}`../reference/public-api`.

```{eval-rst}
.. autosummary::
   :toctree: generated

   pyage.__version__
   pyage.config
   pyage.convolution
   pyage.convolution.DEFAULT_TRACER_GRID_SETTINGS
   pyage.lpm.lpm_build
   pyage.tracer.tracer_root
   pyage.concentrations.concentrations
```

## Contributor and research interfaces

These objects support extensions, repository workflows, and internal
qualification. They may evolve without the deprecation policy applied to the
supported surface above.

```{eval-rst}
.. autosummary::
   :toctree: generated

   pyage.calibration.problem
   pyage.calibration.utils.parameter_grid
   pyage.calibration.utils.systematic_sampling
   pyage.observations
   pyage.lpm.core.lpm_base
   pyage.lpm.core.lpm_dist
   pyage.lpm.core.registry
   pyage.tracer.tracer_protocol
   pyage.tracer.config
   pyage.concentrations.concentrations_time
   pyage.calibration.methods.metropolis_hastings
   pyage.calibration.methods.prior
   pyage.calibration.methods.trajectory
```

### I/O, CLI implementation, and site integration

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
