# Core scientific data

`data_core` contains the shared model definitions and tracer histories used by
PyAges. It is a separate Python package so runtime resources can be resolved
with `importlib.resources` both from a source checkout and from an installed
wheel.

The directory has three deliberately different areas:

- `data_lpm/`: packaged LPM parameter definitions used at runtime;
- `data_tracer/`: packaged tracer YAML files and normalized recharge series;
- `sources/`: source workbooks retained for provenance, not runtime use.

Only `README.md`, the YAML definitions, and the normalized CSV or text
resources selected in `pyproject.toml` are included in built distributions.
Files under `sources/` must not become runtime dependencies.

The three workbooks under `sources/tracer/` document how atmospheric CFC and
SF6 histories were assembled. Their redistribution and attribution conditions
are recorded in the repository-level `NOTICE-DATA.md`.

New runtime LPM or tracer data should be added under `data_lpm/` or
`data_tracer/` respectively and covered by a test. Raw material used to derive
those runtime resources belongs under `sources/`.

## Carbon-14 runtime contracts

The three carbon-14 identifiers are intentionally distinct:

- `14C` uses a constant recharge of 100 pmC and is retained for field cases
  whose initial activity is modeled as constant;
- `14C_NH` uses the packaged Northern Hemisphere (Zone 2) recharge chronicle;
- `14C_SH` uses the packaged Southern Hemisphere recharge chronicle.

Every tracer directory contains exactly one canonical YAML named after the
directory. All three definitions use the published 5730-year half-life; the
loader converts it once to `ln(2) / 5730` per year. The zonal chronicles and
their provenance are documented in `NOTICE-DATA.md`.
