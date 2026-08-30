# First inspectable run

This tutorial checks an installation, runs the small single-date template, and
shows how to decide whether a result directory is complete. It is a software
smoke run, not a calibrated scientific interpretation.

## 1. Install the current release

Install the stable distribution from PyPI. Keep a source checkout available
because this tutorial uses its minimal example template:

```bash
python -m pip install "pyages==1.0.1"
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

## 3. Choose a separate result directory

Keeping results outside the source checkout avoids mixing generated artifacts
with versioned inputs.

On Linux or macOS:

```bash
export PYAGES_RESULTS_DIR="$PWD/pyages-results"
```

In PowerShell:

```powershell
$env:PYAGES_RESULTS_DIR = Join-Path $PWD "pyages-results"
```

## 4. Run the template

From the repository root:

```bash
pyages run examples/templates/quickstart_single.yaml
```

The command begins with output similar to:

```text
Running single-date workflow...
Config: .../examples/templates/quickstart_single.yaml
```

The template deliberately disables reachable-space exploration and both
calibrators. It verifies input loading, tracer/LPM convolution, result writing,
and provenance without claiming that an age distribution has been inferred.

## 5. Inspect completion and provenance

The result directory is:

```text
pyages-results/
  test_cases/
    ploemeur_F09_2010.txt/
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
every generated artifact. It is written only after the workflow succeeds. A
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
