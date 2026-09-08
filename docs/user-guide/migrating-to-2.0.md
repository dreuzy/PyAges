# Migrating from PyAges 1.2 to 2.0

PyAges 2.0 deliberately has one configuration vocabulary and one managed
Metropolis--Hastings (MH) execution path. It does not silently translate a
1.x file: an unknown section or an old field now produces an error before a
scientific calculation starts.

This guide explains how to perform that migration explicitly. The goal is not
merely to make the YAML load. It is to make every scientific and numerical
choice visible enough to review.

## Before changing a study

Keep the original configuration, result directory, PyAges version, and Git
commit together. Migrate a copy and write new results to a new directory. An
old posterior is evidence from the old configuration; it must not be relabelled
as a 2.0 result.

You can identify the old syntax from the beginning of the YAML file:

- `schema_version: 2` means the canonical PyAges 1.2 schema;
- no `schema_version` means the older, workflow-specific 1.x layout;
- `schema_version: 3` is already the PyAges 2.0 layout.

There is no `pyages config migrate` command in 2.0. Automatic conversion was
removed because path resolution, chain initialization, random streams, and
temporal prior handling can affect the calculation. Each choice therefore has
to be reviewed by a person.

## A safe migration procedure

1. Create a fresh 2.0 example beside the study:

   ```bash
   pyages new config migration-2-0
   pyages new config migration-2-0-temporal --kind temporal
   ```

   The first command creates a single-date example; the second creates a
   temporal example. Each directory contains a complete schema-3 YAML file and
   a small observation table.

2. Copy scientific values from the old file into the fresh structure. Use the
   mappings below instead of copying whole sections.
3. Recheck every relative path. In schema 3 it starts from the directory that
   contains the YAML file, not from the repository root.
4. Run a short, non-publication calculation in a new output directory. Check
   the generated `result_manifest.json`, retained sample count, actual seeds,
   prior choice, parameter ranges, and selected observations.
5. Only then restore the production `nsteps` and diagnostic thresholds. Treat
   the resulting 2.0 calculation as a new run.

## Top-level sections

Schema 2 already introduced most of the common section names. The remaining
changes are small but strict:

| PyAges 1.2 schema 2 | PyAges 2.0 schema 3 | Action |
| --- | --- | --- |
| `schema_version: 2` | `schema_version: 3` | Change the discriminator after completing the other edits. |
| `data` | `data` | Keep the section and review paths. |
| `lpm` | `lpm` | Keep the section; `models` is always a list. |
| `run.calibration_metropolis_hastings` | `run.metropolis_hastings` | Rename the single-date run flag. |
| `run.calibration_simplex` | `run.simplex` | Rename the single-date run flag. |
| `calibration.metropolis_hastings` | `calibration.metropolis_hastings` | Keep the section, then flatten its former `multichain` block as described below. |
| `calibration.simplex` | `calibration.simplex` | Keep the single-date section. |
| `reporting` | `reporting` | Keep the temporal section. |
| `output` | `output` | Keep the section and use a new result directory while checking the migration. |

For an unversioned 1.x file, first apply these structural renames:

| Unversioned 1.x | Schema 3 |
| --- | --- |
| `dataset` | `data` |
| single-date `lpm.model_name` | `lpm.models: [<name>]` |
| single-date `lpm.data_directory` | `lpm.directory` |
| `calibration_metropolis_hastings` | `calibration.metropolis_hastings` |
| `calibration_simplex` | `calibration.simplex` |
| temporal `lpm_models.models` or `lpm_models.list` | `lpm.models` |
| temporal `lpm_models.directory` | `lpm.directory` |
| temporal `figures` | `reporting` |
| `results` | `output` |

Add the explicit workflow discriminator if it is absent:

```yaml
schema_version: 3
workflow:
  kind: single_date  # or temporal
```

Do not combine an old and a new name in the same file. Schema 3 rejects the old
name instead of choosing one value arbitrarily.

## One or several MH chains

PyAges 1.2 treated one chain as the absence of a `multichain` block and several
chains as a separate optional engine. PyAges 2.0 uses one block for every
positive chain count.

For example, this schema-2 fragment:

```yaml
calibration:
  metropolis_hastings:
    nsteps: 5000
    burn_in: 0.2
    thinning: 10
    seed: 12345
    monitor: false
    display_traj: false
    multichain:
      enabled: true
      chains: 4
      master_seed: 20260831
      initialization:
        strategy: bounds_stratified
      pilot:
        enabled: true
        nstep: 2000
        burn_in: 0.5
      diagnostics:
        require_convergence: true
```

becomes:

```yaml
calibration:
  metropolis_hastings:
    nsteps: 5000
    burn_in: 0.2
    thinning: 10
    seed: 20260831
    chains: 4
    prior_option: false
    likelihood: true
    display_traj: false
    initialization:
      strategy: bounds_stratified
    pilot:
      enabled: true
      nsteps: 2000
      burn_in: 0.5
    diagnostics:
      require_convergence: true
```

Apply these rules:

- without an enabled old `multichain` block, set `chains: 1` and keep the old
  top-level `seed`;
- with an enabled old block, move its `chains`, `initialization`, `pilot`, and
  `diagnostics` directly below `metropolis_hastings`;
- rename `multichain.master_seed` to `seed`. This was the effective seed of an
  old multi-chain run; the sibling one-chain seed was not used;
- rename `pilot.nstep` to `pilot.nsteps`;
- remove `multichain.enabled`. The positive `chains` value now states the whole
  choice;
- remove `monitor`. `display_traj` requests a trajectory figure for each
  production chain; low-level in-memory recording is not a YAML workflow
  option;
- if an old multi-chain block relied on the 1.2 pilot default, write
  `pilot.enabled: true` explicitly. The 2.0 default is `false`;
- an old block with `multichain.enabled: false` was a one-chain run. Migrate it
  as `chains: 1` and discard the inactive nested multi-chain settings.

The only supported initialization strategies are `bounds_stratified`,
`prior_sample`, and `explicit`. The default is `bounds_stratified` for every
chain count.

## Single-date field names

Unversioned single-date files also require these field renames:

| 1.x field | 2.0 field |
| --- | --- |
| `nstep` | `nsteps` |
| `nskip` | `thinning` |
| `run.calibration_metropolis_hastings` | `run.metropolis_hastings` |
| `run.calibration_simplex` | `run.simplex` |

Keep `burn_in`, `prior_option`, `likelihood`, and `display_traj` only when their
values still express the intended study. Do not infer convergence from the
number of transitions: for several chains, review `diagnostics.max_rhat`,
`min_bulk_ess`, `min_tail_ess`, and `require_convergence` separately.

## Temporal field names and scientific defaults

The temporal configuration now separates preparation and reporting counts from
the MH algorithm:

| PyAges 1.x or schema-2 location | Schema-3 location |
| --- | --- |
| `calibration.explo_res` or `calibration.metropolis_hastings.explo_res` | `calibration.exploration_resolution` |
| `calibration.lpm_number` or `calibration.metropolis_hastings.lpm_number` | `calibration.posterior_draw_count` |
| `calibration.mh_nsteps` | `calibration.metropolis_hastings.nsteps` |
| `calibration.nskip` | `calibration.metropolis_hastings.thinning` |
| `calibration.burn_in` | `calibration.metropolis_hastings.burn_in` |

Two defaults need deliberate attention:

- PyAges 1.x used a fresh random seed when `seed_enabled: false`. To retain
  that policy, use `seed: null`. If `seed_enabled: true`, copy the numeric
  `seed`. Remove `seed_enabled` in both cases.
- The old temporal workflow always enabled the parametric LPM prior. To retain
  that scientific target, write `prior_option: true`. In 2.0 the choice is
  explicit and the common default is `false`.

A representative schema-3 temporal section is:

```yaml
calibration:
  exploration_resolution: 20
  posterior_draw_count: 10
  metropolis_hastings:
    nsteps: 5000
    burn_in: 0.2
    thinning: 10
    seed: null
    chains: 1
    prior_option: true
```

`posterior_draw_count: 0` retains the documented automatic selection rule.

## LPM parameter files

The former word `bounds` mixed two different ideas. Replace it with
`calibration_range` in every maintained `params.yaml`:

```yaml
parameters:
  - name: mu
    domain:
      minimum: 0.0
      minimum_inclusive: false
    calibration_range: [0.1, 100.0]
    init: 10.0
```

`domain` answers “where is the formula mathematically valid?”;
`calibration_range` answers “what finite interval may this calibration
search?”. If `domain` is omitted in YAML, PyAges uses the closed calibration
range as the domain. The old `bounds` name is rejected.

## Relative paths

Every relative schema-3 path starts beside the configuration file. For
example, in `study/config/pyages.yaml`:

```yaml
data:
  data_dir: data
```

means `study/config/data`, not `<repository>/data`. Adjust the text when moving
the YAML. For standard LPM definitions, omitting `lpm.directory` selects the
data packaged with PyAges and is usually more portable than writing a checkout
path.

## Python API changes

Code importing PyAges directly must use the current names:

| Removed 1.x API | PyAges 2.0 API |
| --- | --- |
| `LauncherConfig`, `LauncherParams` | `SingleDateConfig` |
| `TemporalParams` | `TemporalConfig` |
| configuration `load_params()` | `load_config()` |
| configuration `load_params_payload()` | `load_config_payload()` |
| LPM `load_params()` | `load_parameter_document()` |
| LPM `get_calibration_ranges()` | `schema.calibration_ranges` |
| LPM `get_domains()` | `schema.domains` |
| LPM `get_init()` | `schema.initial_values` |
| LPM `get_bounds()` | `schema.calibration_ranges` |
| `MHEnsembleConfig` | `MHRunConfig` |
| `MultiChainMetropolisHastings` | `MetropolisHastingsRunner` |
| `MHConfig(nstep=..., nskip=..., monitor=...)` | `MHConfig(nsteps=..., thinning=..., record_trajectory=...)` |
| `write_calibrated_lpm()` | `calibration.outputs.write_calibrated_result()` |
| `display_lpms()` | `calibration.outputs.display_calibrated_models()` |

The sampler reports `acceptance_rate` and `runtime_seconds`; the former
`success_rate` and `time_perform` names are removed. Managed run records no
longer duplicate `execution_mode` or `master_seed`: use the chain count and
recorded `seed`.

## What numerical equality to expect

A migrated file is not guaranteed to reproduce the exact 1.2 MH trajectory.
PyAges 2.0 derives a production seed for chain 1 through the same seed plan as
all other chains, and `bounds_stratified` is now also the one-chain default.

If an exact initial state matters, declare it explicitly:

```yaml
initialization:
  strategy: explicit
  explicit_starts:
    - mu: 10.0
      shift: 2.0
```

Even then, compare the recorded target, priors, ranges, observations, retained
sample count, and actual production seed before interpreting a numerical
difference. Exact file identity is not the correct acceptance criterion for a
deliberately changed stochastic execution contract.

## Final review checklist

- The file starts with `schema_version: 3` and an explicit `workflow.kind`.
- No old and new section names are mixed.
- Every relative path resolves from the YAML directory.
- `chains`, `seed`, initialization, pilot, and diagnostics are explicit enough
  for the study.
- A temporal study explicitly states `prior_option`.
- All LPM parameter files use `calibration_range`, not `bounds`.
- The migrated run writes to a new directory.
- `result_manifest.json` reports the expected configuration, inputs, seeds,
  package version, chain count, and completed or failed qualification state.

See {doc}`configuration` for the complete schema-3 field reference and
{doc}`multichain-mh` for the statistical meaning of the managed MH settings.
