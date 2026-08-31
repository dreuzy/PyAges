# Multi-chain MH qualification record — 2026-08-31

**Status:** executable development-branch qualification; Unreleased in PyPI
`1.0.1`.

## Decision

The multi-chain Metropolis--Hastings implementation is qualified for the two
versioned single-date profiles below at their registered seeds and thresholds:

- recovery of the known shifted-exponential parameters and latent tracer
  responses in the synthetic realization;
- convergence, support integrity, row integrity, and coherent fitted latent
  concentrations for Ploemeur F09 2010.

This decision qualifies the implemented numerical workflow and these cases. It
does not establish universal MCMC performance or hydrogeological validity.

## Reproduction inputs

| Case | Canonical configuration | Executable test |
|---|---|---|
| Synthetic known truth | `examples/synthetic/lpm_recovery_single_date/lpm_recovery_single_date_multichain.yaml` | `tests/examples/test_synthetic_recovery_multichain_scientific.py` |
| Ploemeur F09 2010 | `examples/natural/ploemeur/exemple_ploemeur_multichain.yaml` | `tests/examples/test_ploemeur_multichain_scientific.py` |

Both configurations use `bounds_stratified` starts, master seed `20260831`, a
separate pilot stage, pooled within-chain covariance with relative ridge
`1e-6`, automatic `2.38/sqrt(d)` proposal scaling, no diagnostic thinning, and
required R-hat/bulk-ESS/tail-ESS gates.

Run the qualifications from an editable source installation:

```bash
python -m pytest -q --run-extensive tests/examples/test_synthetic_recovery_multichain_scientific.py
python -m pytest -q --run-extensive tests/examples/test_ploemeur_multichain_scientific.py
```

`python run_tests.py extensive` runs these cases with the complete core suite.

The final qualified Windows/Python 3.12 campaign collected and passed all
`1,298` core cases, including the seven opt-in extensive cases, in `1,314.88`
seconds. A dedicated short pytest base directory was used because the legacy
site-specific Ploemeur golden has a deeply nested result layout on Windows;
this changes no configuration, seed, calculation, or scientific artifact.

## Registered protocols and cost

| Case | Chains | Pilot | Production | Retained production rows | Sequential MH transitions |
|---|---:|---:|---:|---:|---:|
| Synthetic | 4 | 1,500 per chain, 50% burn-in | 4,000 per chain, 25% burn-in | 11,996 | 22,000 |
| Ploemeur F09 | 5 | 2,000 per chain, 50% burn-in | 5,000 per chain, 20% burn-in | 19,995 | 35,000 |

Wall time is hardware- and model-dependent; these tests belong to the weekly
and manually triggered extensive profile rather than every pull request.

## Observed evidence

| Case | Convergence evidence | Case-specific evidence |
|---|---|---|
| Synthetic | Maximum R-hat `1.003066`; minimum bulk ESS `1540.59`; minimum tail ESS `1647.96` | `mu=28`, `shift=4`, and `mu+shift=32` recovered by the registered marginal and joint checks; four fitted latent tracer responses agree with the versioned truth/noisy observations under their error limits |
| Ploemeur F09 | Maximum R-hat `1.001381`; minimum bulk/tail ESS `2485.89`; chain acceptance `0.3480`–`0.3738` | Positive-definite proposal, bounded joint rows, independent forward recomputation, and median fitted-latent NRMSE `1.0687` |

These values describe the fixed-seed qualification run. The tests gate
scientifically meaningful inequalities, not exact floating-point equality to
the descriptive diagnostics above.

## Interpretation boundary

The synthetic result concerns one versioned noisy realization. It is not a
coverage study over repeated noise draws.

Ploemeur has no known field parameter vector. Its concentration intervals are
distributions of fitted latent model responses over retained parameter states.
No new observation-error realization is drawn, so these must not be called
posterior predictive distributions. They are in-sample because the same three
observations define the likelihood and the residual checks.

Neither result establishes LPM uniqueness, robustness to every prior or bound,
out-of-sample prediction, tracer-history correctness, or transferability to
another aquifer.

## Evidence preservation

The weekly or manually dispatched extensive CI job fixes pytest's temporary
root at `.artifacts/extensive-pytest` and uploads the complete
`synthetic_multichain_scientific` and `ploemeur_f09_multichain_scientific`
result trees with `if: always()`. The artifact is retained for 30 days, so raw
chains and partial failure evidence remain available for short-term review.

A direct YAML run writes the same persistent chain tables, diagnostics,
proposal covariance, seed provenance, and a success manifest under the selected
results root. A required convergence rejection writes a failure manifest that
hashes the preserved partial evidence without claiming completion. For a
publication claim, preserve those files beyond the CI
expiry together with the exact source commit, environment, input checksums, and
artifact SHA-256 values. Neither a successful CI log nor its 30-day artifact is
a permanent scientific archive.

Operational instructions are in {doc}`../user-guide/multichain-mh`; exact file
schemas are in {doc}`../reference/outputs`.
