# Code tour

This page is the shortest path from a YAML file to the scientific calculation.
Read the files in the order shown here; most changes do not require knowing the
whole repository.

## From the command line to a workflow

`pyages run CONFIG` starts in `pyages/cli/commands/run.py`. The command reads the
YAML once, selects `single_date` or `temporal` from `workflow.kind`, applies any
CLI overrides, and calls the matching workflow entry point.

The two workflows share the same shape:

```text
YAML
  -> validated configuration
  -> prepared context (data, paths, display options)
  -> calibration
  -> reporting
  -> result manifest and atomic publication
```

For a single-date run, follow these files:

1. `pyages/workflows/single_date/runner.py` owns the lifecycle.
2. `pyages/workflows/single_date/context.py` loads data and prepares runtime
   objects from the nested `LauncherConfig`.
3. `pyages/workflows/single_date/calibration.py` runs reachability, Simplex, or
   MH without owning sampler details.
4. `pyages/workflows/single_date/reporting.py` creates the compact summaries.

For a temporal run, use the parallel route:

1. `pyages/workflows/temporal/runner.py` owns cases and publication.
2. `pyages/workflows/temporal/context.py` validates and loads the dated data.
3. `pyages/workflows/temporal/cases.py` creates `span` or `successive` cases.
4. `pyages/workflows/temporal/calibration.py` calibrates one model and case.

Both routes meet in `pyages/workflows/runtime/mh.py`. That module is the only
workflow adapter for MH settings and the only place that chooses between a
single chain and a qualified ensemble.

## The scientific kernel

`pyages/calibration/problem.py` connects observations, an LPM, tracers, and the
objective function. LPM construction starts in `pyages/lpm/factory.py`; model
implementations live in `pyages/lpm/models/`, while their parameter ranges and
priors live under `data_core/data_lpm/<model>/params.yaml`.

For MH, the main files are deliberately separated by responsibility:

- `config.py`: immutable one-chain controls.
- `sampler.py`: one-chain transition loop and its private state.
- `prior.py` and `_prior_marginals.py`: factorized prior facade and typed
  marginal distributions.
- `ensemble.py`: orchestration of initialization, pilot, and production chains.
- `diagnostics.py`: R-hat, ESS, MCSE, and qualification decisions.
- `results.py`: immutable records returned by the engine.

Forward concentrations ultimately pass through `pyages/convolution/`. Treat
that package as a numerical boundary: changes there should be checked against
the scientific and golden tests, not only unit tests.

## Where to make common changes

| Goal | Start here | Check with |
| --- | --- | --- |
| Add a YAML option | `pyages/config/models.py` | `tests/config/` |
| Change CLI dispatch or overrides | `pyages/cli/commands/run.py` | `tests/cli/` |
| Change workflow sequencing | the relevant `runner.py` | `tests/workflows/` |
| Change one-chain MH | `methods/mh/sampler.py` | `tests/calibration/` |
| Change multi-chain policy | `methods/mh/ensemble.py` and `diagnostics.py` | multi-chain workflow tests |
| Add an LPM | `pyages/lpm/models/` and `data_core/data_lpm/` | `tests/lpm/` |
| Change result files | `pyages/data_io/` and `workflows/runtime/manifest.py` | result-contract tests |

## Contracts worth preserving

- YAML models reject unknown keys so misspellings do not silently alter a run.
- A calibration problem is freshly built for every ensemble stage and chain.
- Failed convergence is serialized before an error is raised.
- Pooled multi-chain output is published only when the configured policy allows
  it.
- Result directories are staged and promoted atomically; a failed run keeps
  evidence without replacing a previous successful result.
- Public imports are intentionally smaller than the internal module tree. Check
  `tests/test_public_api.py` before exporting a new symbol.

For a first contribution, run the focused tests for the area you changed, then
the normal suite described in {doc}`testing`. The tests marked `extensive`
exercise the maintained scientific qualification profiles and are intentionally
separate from the fast default suite.
