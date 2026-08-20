# Ploemeur single-date example

Quick run:

```bash
python -m examples.natural.ploemeur.run_ploemeur
```

What it does:

- loads the single-date `F09` concentration record,
- uses the shifted exponential LPM (`exp_shifted`),
- explores the reachable concentration space for the selected LPM,
- runs both calibration strategies:
  - `forward_uncertainty_quantification`
  - `Metropolis_Hastings`
- writes a compact set of summary figures first, then the detailed method files.

Key summary figures:

- `01_data_model_space.png`
  Observation, reachable space, and calibrated concentration samples.
- `02_parameter_summary.png`
  Parameter distributions for both calibration strategies.
- `03_objective_summary.png`
  Objective landscape with the estimated parameter clouds overlaid.

Outputs:

- stored under the default results root (`PYAGE_RESULTS_DIR`) unless overridden
  in the environment.
