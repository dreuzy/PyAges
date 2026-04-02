# Synthetic single-date recovery example

Quick run:

```bash
python examples/synthetic/lpm_recovery_single_date/run_lpm_recovery_single_date.py
```

What it does:

- generates a synthetic concentration dataset from a known `exp_shifted` model,
- adds a controlled observational uncertainty,
- runs a single-date calibration with `Metropolis_Hastings`,
- rewrites the summary figures so the true synthetic model is visible against the estimated one.

Why this example is useful:

- the "true" parameters are known in advance,
- the link between model, generated data and estimated parameters is explicit,
- it is shorter and easier to interpret than a field case.

Main files:

- `generation/generation_settings.yaml`
  Defines the true model, the tracers, the date and the noise level.
- `lpm_recovery_single_date.yaml`
  Calibration workflow settings passed to `scripts/launcher.py`.
- `data/synthetic_exp_shifted_2010.txt`
  Generated synthetic observations used for calibration.
- `data/ground_truth.yaml`
  Stored truth used to annotate the final figures.

Key figures written to the results directory:

- `01_data_model_space.png`
  Noisy observations, true synthetic model and calibrated posterior samples.
- `02_parameter_summary.png`
  Recovered parameter distributions with the true parameter values marked.
- `03_objective_summary.png`
  Objective landscape with the true parameters and the estimated cloud.
