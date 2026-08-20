# User guide

Use this guide by task:

- {doc}`getting-started` installs PyAge and runs a minimal calibration.
- {doc}`configuration` documents the YAML inputs.
- {doc}`cli-flags` lists command-line overrides.
- {doc}`running-examples` describes the maintained examples.
- {doc}`adding-tracer` and {doc}`adding-lpm` cover scientific extensions.

The installed `pyage` command is the supported entry point. Discover the
models and tracers present in your installation rather than relying on a static
list in the documentation:

```bash
pyage list lpms
pyage list tracers
```

For the relationship between the main scientific objects, see
{doc}`../architecture`.
