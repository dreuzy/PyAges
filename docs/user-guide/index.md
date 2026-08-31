# User Guide

This section collects installation, configuration, CLI usage, and extension
guides for day-to-day use of PyAges.

Use this guide by task:

- {doc}`tutorial` performs a first run and explains what was produced.
- {doc}`getting-started` installs PyAges and runs a minimal calibration.
- {doc}`configuration` documents the YAML inputs.
- {doc}`concentrations` defines the observation-table schema and validation.
- {doc}`convolution` explains direct forward calculations, finite histories,
  diagnostics, batches, and numerical controls.
- {doc}`calibration` explains method choice, retention, diagnostics, and
  reproducibility.
- {doc}`multichain-mh` gives the end-to-end multi-chain MH procedure, including
  qualification, failure handling, and trace inspection; its
  {ref}`in-memory ensemble map <multichain-mh-in-memory-record>` shows where
  pilot chains, production chains, diagnostic matrices, and pooled samples
  live.
- {doc}`cli-flags` lists command-line overrides.
- {doc}`running-examples` describes the maintained examples.
- {doc}`adding-tracer` and {doc}`adding-lpm` cover scientific extensions.

The installed `pyages` command is the supported entry point. Discover the
models and tracers present in your installation rather than relying on a static
list:

```bash
pyages list lpms
pyages list tracers
```

For the relationship between the main scientific objects, see
{doc}`../architecture`.

```{toctree}
:maxdepth: 1

tutorial
getting-started
running-examples
configuration
concentrations
convolution
calibration
multichain-mh
cli-flags
adding-lpm
adding-tracer
```
