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
| `1` | Installation check failure, invalid validated arguments, import failure, or workflow failure |
| `2` | Click parsing error, such as a missing argument or invalid `--base` choice |

`pyages run` prints a concise error and exits with status 1 when configuration,
input loading, scientific preparation, calibration, or output generation
fails. Add `--verbose` to include the Python traceback for workflow failures.
A failed workflow can leave intermediate files in its deterministic output
directory, but it does not write a completed `result_manifest.json`. See
{doc}`../reference/outputs` for the completion contract.

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

Lists available tracers in the data directory.

| Flag | Type | Description |
| --- | --- | --- |
| `-v`, `--verbose` | flag | Show tracer details (unit and date range). |

Example:
```
pyages list tracers --verbose
```

## `pyages run <config.yaml>`

Runs a workflow from a YAML configuration file.

| Flag | Type | Description |
| --- | --- | --- |
| `--transient` | flag | Run the canonical multi-date temporal workflow. |
| `--inline` | flag | Force the inline matplotlib backend for the single-date workflow; accepted but unused with `--transient`. |
| `--lpm <name>` | option | Override the single-date model; with `--transient`, replace the configured list with this one model. |
| `--mh-nsteps <int>` | option | Override Metropolis-Hastings transitions; must be positive, and the temporal configuration additionally requires a value greater than 100. |
| `--data-name <file>` | option | Override dataset filename (single-date only). |
| `--data-dir <path>` | option | Override dataset directory (single-date only). |
| `--data-file <path>` | option | Override dataset path (transient only). |
| `-v`, `--verbose` | flag | Enable verbose output. |

Examples:
```
pyages run examples/natural/ploemeur/exemple_ploemeur.yaml
pyages run --transient examples/natural/ploemeur_temporal/ploemeur_temporal.yaml
pyages run --lpm exp_shifted --mh-nsteps 5000 --data-name mydata.txt --data-dir examples/my_site/data my_config.yaml
pyages run --transient --lpm ig --mh-nsteps 2000 --data-file examples/my_site/data/ori_my_site_2005_2024.txt my_temporal.yaml
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

## `pyages new lpm <name>`

Generates a template for a new LPM model.

| Flag | Type | Description |
| --- | --- | --- |
| `--base <scipy|root>` | option | Base class to extend (default: `scipy`). |
| `-o`, `--output <path>` | option | Output directory (default: `./pyages/lpm/models/`). |

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

Example:
```
pyages new tracer ar39 --with-decay
```
