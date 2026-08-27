# CLI flags reference

This page summarizes the optional flags exposed by the `pyage` CLI. For up-to-date
usage and defaults, you can always run `pyage --help` or `pyage <command> --help`.

## `pyage`

| Flag | Description |
| --- | --- |
| `--version` | Show the installed PyAge version and exit. |
| `--help` | Show the command groups and exit. |

## `pyage check`

Checks installation and key resources (dependencies, LPM registry, tracer data).

| Flag | Type | Description |
| --- | --- | --- |
| `-v`, `--verbose` | flag | Show detailed check results. |

Example:
```
pyage check --verbose
```

## `pyage list lpms`

Lists available LPM models.

| Flag | Type | Description |
| --- | --- | --- |
| `-v`, `--verbose` | flag | Show detailed information (model doc first line). |

Example:
```
pyage list lpms --verbose
```

## `pyage list tracers`

Lists available tracers in the data directory.

| Flag | Type | Description |
| --- | --- | --- |
| `-v`, `--verbose` | flag | Show tracer details (unit and date range). |

Example:
```
pyage list tracers --verbose
```

## `pyage run <config.yaml>`

Runs a workflow from a YAML configuration file.

| Flag | Type | Description |
| --- | --- | --- |
| `--transient` | flag | Run the canonical multi-date temporal workflow. |
| `--inline` | flag | Force inline matplotlib backend (useful in notebooks/IDEs). |
| `--lpm <name>` | option | Override LPM model name (single‑date) or list (transient). |
| `--mh-nsteps <int>` | option | Override Metropolis‑Hastings iteration count. |
| `--data-name <file>` | option | Override dataset filename (single‑date only). |
| `--data-dir <path>` | option | Override dataset directory (single‑date only). |
| `--data-file <path>` | option | Override dataset path (transient only). |
| `-v`, `--verbose` | flag | Enable verbose output. |

Examples:
```
pyage run examples/natural/ploemeur/exemple_ploemeur.yaml
pyage run --transient examples/natural/ploemeur_temporal/ploemeur_temporal.yaml
pyage run --lpm exp_shifted --mh-nsteps 5000 --data-name mydata.txt --data-dir examples/my_site/data my_config.yaml
pyage run --transient --lpm ig --mh-nsteps 2000 --data-file examples/my_site/data/ori_my_site_2005_2024.txt my_temporal.yaml
```

## `pyage new lpm <name>`

Generates a template for a new LPM model.

| Flag | Type | Description |
| --- | --- | --- |
| `--base <scipy|scipy_safe|root>` | option | Base class to extend (default: `scipy`). |
| `-o`, `--output <path>` | option | Output directory (default: `pyage/lpm/models/`). |

Example:
```
pyage new lpm weibull --base scipy_safe
```

## `pyage new tracer <name>`

Generates a template for a new tracer.

| Flag | Type | Description |
| --- | --- | --- |
| `--with-decay` | flag | Include radioactive decay configuration. |
| `--no-chronicle` | flag | Skip chronicle template (use constant concentration). |
| `-o`, `--output <path>` | option | Output directory (default: `data_core/data_tracer/`). |

Example:
```
pyage new tracer ar39 --with-decay
```
