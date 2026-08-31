# Ploemeur single-date example

The maintained example uses the shifted-exponential LPM (`exp_shifted`) for
the three F09 observations from 2010.

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

The historical `exemple_ploemeur.yaml` remains a pedagogical mono-chain
configuration and also runs the simplex route. A successful single chain is
not a convergence certificate.

## Multi-chain qualification profile

The development branch provides a separate canonical configuration:

```bash
pyages run examples/natural/ploemeur/exemple_ploemeur_multichain.yaml
```

This **Unreleased** profile is not part of `pyages==1.0.1`. It runs five
dispersed chains, with 2,000 pilot and 5,000 production transitions per chain,
no thinning, a fixed covariance learned from pooled within-chain pilot
variation, and required R-hat/bulk-ESS/tail-ESS gates. The current runner
executes the 35,000 MH transitions sequentially.

Run the executable scientific check with:

```bash
python -m pytest -q --run-extensive tests/examples/test_ploemeur_multichain_scientific.py
```

For master seed `20260831`, the observed maximum R-hat is `1.001381`, minimum
bulk/tail ESS is `2485.89`, chain acceptance ranges from `0.3480` to `0.3738`,
and the median fitted-latent normalized RMS residual is `1.0687`. The test
enforces thresholds rather than exact equality to those descriptive values.

These are in-sample fitted latent concentrations, not posterior predictive
draws: no new observation noise is simulated. The field data contain no known
true `mu` or `shift`, and this case does not establish LPM uniqueness,
out-of-sample skill, or hydrogeological validity. See
[`docs/examples/ploemeur-multichain.md`](../../../docs/examples/ploemeur-multichain.md).

Key summary figures:

- `01_data_model_space.png`
  Observation, reachable space, and calibrated concentration samples.
- `02_parameter_summary.png`
  Parameter distributions for both calibration strategies.
- `03_objective_summary.png`
  Objective landscape with the estimated parameter clouds overlaid.

Outputs:

- stored under the default results root (`PYAGES_RESULTS_DIR`) unless overridden
  in the environment.
- multi-chain runs retain each chain under `chains/`, diagnostics in
  `mcmc_diagnostics.tsv`, proposal covariance, complete seed provenance, and a
  pooled root table only after the configured qualification policy permits it.
