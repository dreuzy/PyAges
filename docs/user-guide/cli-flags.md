# CLI flags reference

This page summarizes the optional flags exposed by the `pyages` CLI. For the
usage installed in the current environment, run `pyages --help` or
`pyages <command> --help`.

## `pyages`

| Flag | Type | Description |
| --- | --- | --- |
| `--version` | flag | Show the installed PyAges version and exit. |

## Exit status and failure behavior

| Status | Meaning |
|---:|---|
| `0` | Help/version display or successful command |
| `1` | Installation check failure, invalid validated arguments, workflow failure, or stage-operation refusal |
| `2` | Click parsing error, such as a missing argument or invalid `--base` choice |

`pyages run` prints a concise error and exits with status 1 when configuration,
input loading, scientific preparation, calibration, or output generation
fails. Add `--verbose` to include the Python traceback for workflow failures.
A failed workflow can leave intermediate files in its deterministic output
directory, but it does not write a completed `result_manifest.json`. Rejection
by a required multi-chain convergence gate instead writes an auditable manifest
with `status: failed`. See {doc}`../reference/outputs` for the completion
contract.

## `pyages check`

Checks installation and key resources (dependencies, LPM registry, tracer data).

| Flag | Type | Description |
| --- | --- | --- |
| `-v`, `--verbose` | flag | Show detailed check results. |

Example:
```
pyages check --verbose
```

## `pyages list lpms`

Lists available LPM models.

| Flag | Type | Description |
| --- | --- | --- |
| `-v`, `--verbose` | flag | Show detailed information (model doc first line). |

Example:
```
pyages list lpms --verbose
```

## `pyages list tracers`

Lists tracers in the packaged `data_core/data_tracer` directory. This command
does not read `tracers.data_directory` from a workflow configuration.

| Flag | Type | Description |
| --- | --- | --- |
| `-v`, `--verbose` | flag | Show tracer details (unit and date range). |

Example:
```
pyages list tracers --verbose
```

## `pyages run <config.yaml>`

Runs the workflow selected by `workflow.kind` in the YAML configuration.
Legacy files without that field are detected from their dataset structure.

| Flag | Type | Description |
| --- | --- | --- |
| `--transient` | flag | Deprecated compatibility flag for legacy temporal files; prefer `workflow.kind: temporal`. |
| `--inline` | flag | Force the inline matplotlib backend for the single-date workflow; accepted but unused for temporal workflows. |
| `--lpm <name>` | option | Override the single-date model or replace a temporal model list with this one model. |
| `--mh-nsteps <int>` | option | Override Metropolis-Hastings transitions; must be positive, and the temporal configuration additionally requires a value greater than 100. |
| `--data-name <file>` | option | Override dataset filename (single-date only). |
| `--data-dir <path>` | option | Override dataset directory (single-date only). |
| `--data-file <path>` | option | Override dataset path (temporal only). |
| `-v`, `--verbose` | flag | Enable verbose output. |

Examples:
```
pyages run examples/natural/ploemeur/exemple_ploemeur.yaml
pyages run examples/natural/ploemeur_temporal/ploemeur_temporal.yaml
pyages run --lpm exp_shifted --mh-nsteps 5000 --data-name mydata.txt --data-dir examples/my_site/data my_config.yaml
pyages run --lpm ig --mh-nsteps 2000 --data-file examples/my_site/data/ori_my_site_2005_2024.txt my_temporal.yaml
```

Overrides are applied to a temporary YAML file created beside the original
configuration so relative paths keep the same resolution base. The original
file is never modified, and the temporary file is deleted whether the workflow
succeeds or fails.

Mode-specific options behave as follows:

| Invocation | Behavior |
|---|---|
| single-date with `--data-file` | Prints a warning and ignores `--data-file` |
| temporal with `--data-name` or `--data-dir` | Prints a warning and ignores those options |
| temporal with `--inline` | Accepts the flag without changing the temporal plotting backend |

When overrides are used, the result manifest fingerprints the temporary
effective YAML before it is removed and the `command` field records the CLI
flags. Preserve the original configuration plus the command line with any
archived result.

## `pyages stages inspect <root>`

Recursively inventories workflow staging candidates without changing the
filesystem. The diagnosis covers the run journal, terminal-manifest seal,
artifact hashes, and publication compare-and-swap token. It cannot determine
whether a workflow process is still writing to an unsealed stage.
The human and JSON representations use the same point-in-time field name,
`promotable_now`; there is no legacy `promotable` alias.

| Flag | Type | Description |
| --- | --- | --- |
| `--json` | flag | Emit the complete inventory as a machine-readable JSON array. |

Example:

```console
pyages stages inspect ~/results/PyAges
```

## `pyages stages quarantine <stage-directory>`

Atomically renames one valid managed stage to a sibling quarantine directory;
it never deletes or rewrites its contents. Stop the owning workflow first.

| Flag | Type | Description |
| --- | --- | --- |
| `--run-id <uuid>` | required option | Acknowledge the complete UUID printed by `stages inspect`. |
| `--yes` | flag | Confirm the quarantine operation without an interactive prompt. |

Example:

```console
pyages stages quarantine /results/.pyages-a1b2c3d4-e5f \
  --run-id a1b2c3d4-e5f6-47a8-9123-456789abcdef --yes
```

There is no automatic purge command. See {doc}`../reference/outputs` for the
operational safety and retention contract.

## `pyages new lpm <name>`

Generates a template for a new LPM model.

| Flag | Type | Description |
| --- | --- | --- |
| `--base <scipy|root>` | option | Base class to extend (default: `scipy`). |
| `-o`, `--output <path>` | option | Output directory (default: `./pyages/lpm/models/`). |

This is a source-development command. Run it from the root of a writable,
editable checkout. The option changes only the model-module destination; the
parameter YAML is generated under `./data_core/data_lpm/<name>/`. A module
written outside `pyages/lpm/models/` is not discovered until it is integrated
into that importable package.

Example:
```
pyages new lpm weibull --base scipy
```

## `pyages new tracer <name>`

Generates a template for a new tracer.

| Flag | Type | Description |
| --- | --- | --- |
| `--with-decay` | flag | Include radioactive decay configuration. |
| `--no-chronicle` | flag | Skip chronicle template (use constant concentration). |
| `-o`, `--output <path>` | option | Output directory (default: `data_core/data_tracer/`). |

The output path is the root containing one directory per tracer. When it is not
the packaged default, set `tracers.data_directory` to the same root in the
workflow YAML. `pyages list tracers` continues to show only the packaged root.

Example:
```
pyages new tracer ar39 --with-decay
```
