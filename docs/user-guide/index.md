# User Guide

This section collects installation, configuration, CLI usage, and extension
guides for day-to-day use of PyAge.

Use this guide by task:

- {doc}`tutorial` performs a first run and explains what was produced.
- {doc}`getting-started` gives the supported installation and smoke commands.
- {doc}`configuration` documents the YAML inputs.
- {doc}`cli-flags` lists command-line overrides.
- {doc}`running-examples` describes the maintained examples.
- {doc}`adding-tracer` and {doc}`adding-lpm` cover scientific extensions.

The installed `pyage` command is the supported entry point. Discover the
models and tracers present in your installation rather than relying on a static
list:

```bash
pyage list lpms
pyage list tracers
```

For the relationship between the main scientific objects, see
{doc}`../architecture`.

```{toctree}
:maxdepth: 1

tutorial
getting-started
running-examples
configuration
cli-flags
adding-lpm
adding-tracer
```
