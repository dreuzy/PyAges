# HYP-26-0172 simulation study

Reproducible simulation plan for the article *Long-term CFC monitoring
advances groundwater age interpretation and reveals transit-time dynamics in
a fractured crystalline aquifer*.

## Principles

- Observation data remain under `sites/ploemeur/data`; this directory never
  contains copies of source measurements.
- `experiment_matrix.csv` is the index linking scientific claims, workflow
  configurations, runs, and article figures.
- Heavy outputs are written under `results/HYP-26-0172/runs/<experiment_id>`.
- Every launched experiment receives a manifest recording its configuration,
  input hashes, Git revision, environment, command, and final status.
- MCMC outputs (`runs`) are kept separate from derived tables (`derived`) and
  publication graphics (`figures`).
- `figures.yaml` is the authoritative map from scientific claims to
  experiments, derived tables, builders, and source observations.
- `archive/` contains provenance-only development material. It is never an
  input to the finalized production chain.

## Scientific reading guide

The study compares three interpretations of the same temporal observations:

1. **Full series**: one posterior inferred from the complete observation
   period.
2. **Independent windows**: each sampling window inferred without information
   from the full series.
3. **Conditioned windows**: each sampling window inferred using the full-series
   posterior as prior information.

These concepts have one visual vocabulary throughout the study: grey for the
full series, red for independent/unconstrained windows, and blue for
conditioned windows. The definitions live in `postprocessing/style.py`.

The main scientific question is whether repeated CFC measurements contain
information about changes in the apparent transit-time distribution that
cannot be recovered from a single sampling date. Model-family, observation
error, initialization, tracer selection, and the pre/post-2012 split are
treated as explicit sensitivity analyses rather than implicit plotting
choices.

## Experiment families

| Family | Purpose | Article output |
|---|---|---|
| `main` | Full-series, independent, and conditioned estimates | Figures 3 and 4 |
| `model` | Shifted exponential versus shifted inverse Gaussian | Figure 5 |
| `regime` | Full/pre-/post-2012 conditioning at five wells | Figure 6 |
| `error` | Relative-error sensitivity from 10 to 40% | Figure A1 |
| `initialization` | Widely separated F11 initial states and seeds | Robustness statement |
| `tracer` | F11 CFC-11-only versus joint three-CFC calibration | Section 3.3 |

The `double_prior` workflow performs the full-span, period-specific, and
successive-window stages. Consequently, one matrix row can supply several
derived products; the `article_outputs` column records all intended consumers.

## Commands

Validate the matrix and referenced YAML files without running a calibration:

```powershell
python -m sites.ploemeur.studies.HYP-26-0172.scripts.validate_study
```

List the commands selected for Figure 6:

```powershell
python -m sites.ploemeur.studies.HYP-26-0172.scripts.run_matrix --select article_outputs=Figure6
```

Run one experiment explicitly:

```powershell
python -m sites.ploemeur.studies.HYP-26-0172.scripts.run_matrix `
  --experiment-id regime_F11_exp_3cfc_err20_seed12345 --execute
```

Run the same experiment with an isolated 100-step smoke profile:

```powershell
python -m sites.ploemeur.studies.HYP-26-0172.scripts.run_matrix `
  --experiment-id regime_F11_exp_3cfc_err20_seed12345 `
  --profile smoke --execute
```

After the selected runs finish, build derived CSV files and available figures:

```powershell
python -m sites.ploemeur.studies.HYP-26-0172.postprocessing.build_products --profile smoke
```

Launch all enabled 40,000-step production experiments with two concurrent
six-process workflows:

```powershell
python -m sites.ploemeur.studies.HYP-26-0172.scripts.supervise_runs --max-workers 2
```

When an earlier production campaign must be preserved, use a named isolated
profile consistently for execution and postprocessing:

```powershell
python -m sites.ploemeur.studies.HYP-26-0172.scripts.supervise_runs `
  --profile cdf_v2 --max-workers 2
python -m sites.ploemeur.studies.HYP-26-0172.postprocessing.build_products `
  --profile cdf_v2
```

Each schema-v2 run manifest records separate fingerprints for numerical source
files and scientific inputs, plus the complete installed-package environment.
The profile directory already provides isolation, so experiment identifiers are
not suffixed; this keeps deeply nested Windows figure paths below 260 characters.

Progress is recorded in `results/HYP-26-0172/supervisor_status.json`; per-run
stdout and stderr are kept in `results/HYP-26-0172/logs`.

During incremental development, add `--allow-partial` to render the available
subset. Without it, multi-well figures are emitted only when all required wells
are present.

By default `run_matrix.py` is a dry run. `--execute` is mandatory before any
calibration starts. Existing non-empty run directories are rejected unless
`--resume` is supplied.

## Output contract

Each run directory contains at least:

```text
results/HYP-26-0172/runs/<experiment_id>/
|-- manifest.json
|-- resolved_config.yaml
|-- input_checksums.json
|-- environment.txt
`-- workflow/                 # native PyAges results
```

Postprocessing must create durable, tabular intermediates below
`results/HYP-26-0172/derived`. In particular, Figure 6 should be rendered from
`figure6_median_transit_times.csv`, not by searching dated result folders.

The production chain is:

```text
experiment_matrix.csv
  -> matrix-managed workflow runs
  -> derived/*.csv
  -> postprocessing figure builders
  -> figures/*.{png,pdf,tif}
```

Only the extraction stage may inspect native workflow folders. Figure builders
must consume a declared derived table, except Figure 3 (posterior prediction
ensembles) and the observation-only Figures 2/S1. See `figures.yaml` for the
complete contract.

The code follows the same boundary: `product_extraction.py` discovers and
validates native run outputs, `summary_figures.py` renders Figures 4, 5, 6 and
A1 only from derived tables, and `build_products.py` is the short orchestration
facade. Figure 3 remains in the facade as the documented native-posterior
exception.

Each generated figure has three outputs: a 300-DPI PNG preview, a vector PDF,
and the submission artifact (`.tif`). Submission TIFF files are flattened RGB,
single-frame, LZW-compressed graphs at 600 DPI. Validate them with:

```powershell
python -m sites.ploemeur.studies.HYP-26-0172.postprocessing.validate_submission_figures
```

## Figure-to-experiment map

| Article element | Matrix families |
|---|---|
| Figure 2 | Observations only (no calibration) |
| Figures 3-4 | `main` |
| Figure 5 | `model` |
| Figure 6 | `regime` |
| Figure A1 | `error` |
| Figure S1 | Observations only (no calibration) |
| F11 initialization check | `initialization` |
| F11 tracer check | `tracer` |

## Restarting the study later

1. Update curated observations in `sites/ploemeur/data/ori`; runtime selection
   files are generated in an isolated operating-system temporary directory and
   removed automatically.
2. Review `experiment_matrix.csv` and its referenced files in `params/`.
3. Run `scripts/validate_study.py`.
4. Launch the required matrix rows with `scripts/run_matrix.py`.
5. Build products with `postprocessing/build_products.py`.
6. Build observation-only products with
   `postprocessing/build_observation_figures.py`.
7. Validate submission TIFF files with
   `postprocessing/validate_submission_figures.py`.

Record the Git revision and environment manifests produced with each run.
Historical pre-matrix configurations are retained under `archive/` only to
explain earlier outputs. No archived executable is part of the workflow.

## Closure and limitations

The code chapter is considered closed when every reported result is linked
through `figures.yaml` and `experiment_matrix.csv`, all matrix configurations
validate, derived tables are reproducible from manifests, and submission
figures pass technical validation.

Interpretation still depends on the selected LPM family, observation-error
model, tracer set, and prior-conditioning strategy. A future update should
rerun the declared sensitivity families rather than silently changing a
figure script or selecting the newest output directory.
