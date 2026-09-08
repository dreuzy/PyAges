# First inspectable run

This tutorial checks an installation, runs the small single-date template, and
shows how to decide whether a result directory is complete. It is a software
smoke run, not a calibrated scientific interpretation.

## 1. Install the prepared 1.2 source

From the repository root, install the current checkout. Once 1.2 is published,
the equivalent user installation will be `python -m pip install pyages==1.2.0`:

```bash
python -m pip install .
```

See {doc}`../reference/install` for the separate editable development and
historical article-reproduction environments.

## 2. Check the installation

```bash
pyages --version
pyages check
pyages list lpms
pyages list tracers
```

`pyages check` exits successfully only when the package data, LPM registry, and
distributed tracer definitions can be loaded. The lists are authoritative for
the installed version.

## 3. Generate a self-contained example

Create a local project. It contains its own schema-3 configuration, synthetic
observations, and result directory, and does not depend on repository examples:

```bash
pyages new config quickstart
```

## 4. Run the template

```bash
pyages run quickstart/pyages.yaml
```

The command begins with output similar to:

```text
Running single-date workflow...
Config: .../quickstart/pyages.yaml
```

The template deliberately disables reachable-space exploration and both
calibrators. It verifies input loading, tracer/LPM convolution, result writing,
and provenance without claiming that an age distribution has been inferred.

## 5. Inspect completion and provenance

The result directory is local to the generated project:

```text
quickstart/
  results/
    quickstart/
      observations.tsv/
      concentrations.txt
      result_manifest.json
      ...
```

Open `result_manifest.json` first. A completed run has:

```json
{
  "schema_version": 2,
  "status": "complete",
  "workflow": "single_date"
}
```

The same file records SHA-256 hashes for the configuration, input table, and
every generated artifact. A required multi-chain convergence rejection can
write it with `status: failed`; other execution errors can leave it absent. A
directory without a complete manifest must not be treated as a finished run.

The full file and column reference is {doc}`../reference/results`.

## 6. Continue to an inference example

Use {doc}`../examples/synthetic-recovery` next. Its generating LPM and true
parameters are known, so differences between truth and the recovered posterior
can be examined before moving to a field dataset.

For scientific use, do not interpret one chain or a small template as a
convergence certificate. Follow the multi-chain criteria in
{doc}`../science/inference` and the qualification limits in
{doc}`../science/validation`.
