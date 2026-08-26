# Holten

This page documents the Holten benchmark example implemented in
`examples/natural/holten/`.

The scientific assumptions and interpretation limits adopted by the final
article benchmark are summarized in {doc}`../../science/case-studies`.

The goal of the example is not to provide a generic multi-tracer demo. It is a
case-specific benchmark built from Visser et al. (2013), with local tracer
histories, local data preparation, local benchmark figures, and a local
Holten-specific `4-bin` helper used for comparison with the paper.

## Scope

Current scope:

- campaign: April 2010
- wells: the production wells listed in `examples/natural/holten/holten.yaml`
- calibration tracers: `3H`, `kr85`, `39Ar`
- diagnostic-only helium support: `3He_trit`, `He4`, `He4_terr`, `DeltaNe_pct`

What is generic and stays in the core:

- the executable launcher workflow
- the bootstrap LPM selected in `holten.yaml`
- tracer loading and convolution infrastructure

What stays local to Holten:

- source-data mapping from the article tables
- local tracer preparation rules
- helium diagnostics used for interpretation
- article comparison figures and summary tables
- the local `4-bin` benchmark helper

Holten can mix tracer definitions coming from the example itself and from the
core tracer registry. The current setup keeps `3H` and `kr85` local, while
`39Ar` is resolved from `data_core/data_tracer/39Ar`.

## Main Files

- `examples/natural/holten/holten.yaml`
  Main configuration for the example.
- `examples/natural/holten/holten_case.py`
  Shared context, paths, and config helpers.
- `examples/natural/holten/holten_prepare.py`
  Data preparation, tracer YAML validation, observation conversion, and helium
  diagnostics.
- `examples/natural/holten/holten_benchmark.py`
  Pre-model figures and published-results comparison helpers.
- `examples/natural/holten/holten_four_bin.py`
  Holten-specific local `4-bin` fit and local Metropolis-Hastings posterior.
- `examples/natural/holten/run_holten.py`
  Orchestrator for the full workflow.
- `examples/natural/holten/exemple_holten.ipynb`
  Notebook for step-by-step reading of the case.

## Workflow

The example is intentionally split into four local layers:

1. `holten_case.py`
   Resolve paths and interpret the Holten config.
2. `holten_prepare.py`
   Build prepared tracer inputs and converted well observations.
3. `holten_benchmark.py`
   Produce pre-model figures and published-results comparisons.
4. `holten_four_bin.py`
   Run the local article-oriented `4-bin` comparison workflow.

`run_holten.py` assembles those layers without pushing the case-specific logic
into the generic PyAge core.

## Run

Full workflow:

```bash
python examples/natural/holten/run_holten.py --mode full
```

Preparation and benchmark artifacts only:

```bash
python examples/natural/holten/run_holten.py --mode prepare_only
```

This mode stops after preparation and benchmark artifacts. It does not launch
the bootstrap calibration or the final comparison summary.

Calibration phase only:

```bash
python examples/natural/holten/run_holten.py --mode calibration_only
```

This mode prepares the case if needed, then runs only the launcher/bootstrap
calibration step.

Comparison phase only:

```bash
python examples/natural/holten/run_holten.py --mode compare_only
```

This mode rebuilds the comparison products only. If the local `4-bin` summary
is missing, it is recomputed on the fly because the comparison depends on it.
It still reloads the prepared Holten inputs, so it may refresh intermediate
prepared files before producing the comparison outputs.

Run a subset of wells:

```bash
python examples/natural/holten/run_holten.py --mode full --wells 67-19,72-22,85-33
```

## Outputs

Holten-local artifacts are written under:

- `examples/natural/holten/generated/benchmark/prepared/`
- `examples/natural/holten/generated/benchmark/pre_model/`
- `examples/natural/holten/generated/benchmark/four_bin/`
- `examples/natural/holten/generated/benchmark/benchmark/`

These folders contain:

- prepared input tables actually used by the workflow
- pre-model tracer and well figures
- local `4-bin` fit summaries and posterior summaries
- comparison tables against the published reference results

Launcher outputs remain in the standard results directory configured by PyAge.
Per-well launcher input files are generated only when
`holten.preparation.generate_per_well_files` is enabled in `holten.yaml`.
If `holten.launcher.enabled` is `true`, this option must stay enabled because
the launcher runs read those per-well files.

## Models Used Here

There are two distinct model layers in the Holten example:

- the generic launcher LPM selected in `holten.yaml`
- the local Holten `4-bin` helper used for article-oriented comparison

The generic LPM is currently `uniform`. It is only used as a bootstrap model to
exercise the executable launcher workflow on the Holten data.

The Holten `4-bin` logic is not a generic LPM yet. It stays local because the
`old` end-member depends on tracer-specific Holten conventions.

## Validation

Holten regression coverage lives in:

- `tests/examples/test_holten_helpers.py`
- `tests/examples/test_holten_golden.py`
- `tests/examples/holten_test_support.py`

Run the Holten tests with:

```bash
python -m pytest tests/examples/test_holten_helpers.py tests/examples/test_holten_golden.py -q
```

## Optional Dependencies

- `openpyxl`
  Needed only if the workflow has to read `visser_data.xlsx` directly instead of
  the CSV extracted for the `4-bin` reference table.
- `pdftoppm`
  Needed only for article figure extraction from the local PDF.

If those tools are missing, the core Holten preparation and local benchmark fit
still work, but the corresponding optional figure extraction step is skipped or
fails with an explicit message.

## Notes

- Helium is kept as diagnostic context, not as part of the main calibration
  dataset.
- The notebook and the script share the same local helpers. The script is the
  reproducible entry point; the notebook is the explanatory entry point.
- Additional helium-specific notes remain in
  `docs/examples/holten/notes-helium.md`.
