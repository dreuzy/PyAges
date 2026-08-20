# Synthetic single-date recovery example

This example is a compact teaching case built to understand the PyAge
single-date workflow without the ambiguity of field data.

The idea is simple:

1. define a known LPM and known parameter values;
2. generate synthetic tracer concentrations from that model;
3. add controlled noise to create synthetic observations;
4. run the calibration workflow on those observations only;
5. compare the recovered parameters with the known truth.

Because the truth is known in advance, this example is easier to read than a
natural case such as Ploemeur.

## Quick run

```bash
python examples/synthetic/lpm_recovery_single_date/run_lpm_recovery_single_date.py
```

## What the workflow produces

The workflow:

- regenerates the synthetic dataset from the YAML generation settings;
- writes the noisy observations to `data/synthetic_exp_shifted_2010.txt`;
- runs the single-date calibration with `Metropolis_Hastings`;
- rebuilds the summary figures so the true synthetic solution is shown against
  the estimated posterior;
- writes a compact parameter-recovery table for quick interpretation.

## Files in this folder

### Main entry points

- `README.md`
  This file. It explains the purpose of the example, the role of each file, and
  where to find the broader documentation.
- `run_lpm_recovery_single_date.py`
  Main script to run the example end to end. It regenerates the synthetic data,
  launches the single-date workflow, and rebuilds the final figures with the
  known truth shown explicitly.
- `exemple_lpm_recovery_single_date.ipynb`
  Notebook version of the example. It is meant for interactive use and explains
  the workflow step by step, including beginner and expert views.

### Configuration files

- `generation/generation_settings.yaml`
  Defines the synthetic truth:
  the true LPM family, the true parameter values, the tracer list, the
  observation date, the random seed, and the relative noise level applied to
  the generated concentrations.
- `lpm_recovery_single_date.yaml`
  Defines the calibration workflow:
  reachable-space sampling, objective-function sampling, and
  `Metropolis_Hastings` settings such as the number of MCMC steps.

### Python helpers

- `synthetic_case.py`
  Helper module used by both the script and the notebook. It contains the logic
  to:
  generate the synthetic dataset, store the ground truth, rebuild the summary
  figures with the truth displayed, and write the parameter-recovery summary.

### Generated data files

- `data/synthetic_exp_shifted_2010.txt`
  Synthetic observations actually used as input by the calibration.
  This is the noisy dataset.
- `data/true_concentrations.txt`
  Noise-free concentrations generated directly from the true synthetic model.
  This is useful to compare truth vs observation.
- `data/ground_truth.yaml`
  Metadata describing the synthetic truth used in the run:
  model name, true parameter values, tracers, date, and stored concentration
  values.

## Main outputs in the results directory

The results are written under the global PyAge results root, usually:

```text
<home>/results/PyAge/test_cases/synthetic_exp_shifted_2010.txt/
```

The main summary figures are:

- `01_data_model_space.png`
  Observations, prior reachable space, posterior samples, and the true
  synthetic solution.
- `02_parameter_summary.png`
  Posterior parameter distributions with the true parameter values marked.
- `03_objective_summary.png`
  Objective-function summary with the true parameters and posterior samples.
- `parameter_recovery_summary.txt`
  Compact table comparing true values and recovered posterior statistics.

The notebook expert mode also shows an interpolated objective-function view
where posterior solutions are colored by their objective value.

## How this example fits into the global documentation

This folder explains one specific example. For the broader project
documentation, start with:

- [`README.md`](../../../README.md)
  Global project overview: installation, CLI, repository layout, results
  directory, and main entry points.
- [`docs/user-guide/running-examples.md`](../../../docs/user-guide/running-examples.md)
  Overview of the available examples and how to run the main workflows.

Related files that help place this example in the repository:

- [`examples/templates/quickstart_single.yaml`](../../templates/quickstart_single.yaml)
  Minimal single-date configuration template.
- [`examples/natural/ploemeur/`](../../natural/ploemeur)
  Natural single-date example used as the main field-data reference.
- `pyage run`
  Canonical single-date workflow used by this example.
- [`scripts/common/example_summary_plots.py`](../../../scripts/common/example_summary_plots.py)
  Shared plotting helpers used to build the didactic summary figures.

## Recommended reading order

If you are discovering the codebase, a practical order is:

1. read this `README.md`;
2. open `generation/generation_settings.yaml`;
3. open `lpm_recovery_single_date.yaml`;
4. run `run_lpm_recovery_single_date.py`;
5. then inspect `exemple_lpm_recovery_single_date.ipynb`.
