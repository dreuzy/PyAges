# Ploemeur F09 2010 multi-chain qualification

```{note}
This profile uses an **Unreleased** development-branch feature. It is not
available in the `pyages==1.0.1` package from PyPI. Use a source installation
and record the exact Git commit.
```

This maintained profile derives a multi-chain inference from the historical
single-date Ploemeur example. Its scope is deliberately narrow: three F09
observations from 2010, the shifted-exponential (`exp_shifted`) LPM, the
registered fallback uncertainty policy, and no informative parameter prior.
All three source uncertainty fields are zero placeholders. Before calibration,
the workflow replaces each one with 1% of the mean tracer-history response
evaluated at the sampling date. This is not 1% of the observed concentration
and does not validate a laboratory uncertainty model.

## Run the profile

From the repository root:

```bash
pyages run examples/natural/ploemeur/exemple_ploemeur_multichain.yaml
```

The default result location is:

```text
<results_root>/ploemeur_f09_multichain/ploemeur_F09_2010.txt/Metropolis_Hastings/
```

Use a separate result root or archive the preceding directory before treating
the run as qualification evidence.

## Fixed protocol

| Control | Value |
|---|---:|
| Production chains | 5 |
| Production transitions per chain | 5,000 |
| Production burn-in | 0.20 |
| Thinning | none (`nskip: 1`) |
| Retained rows per chain | 3,999 |
| Pilot transitions per chain | 2,000 |
| Pilot burn-in | 0.50 |
| Initialization | `bounds_stratified` |
| Proposal covariance | pooled within-chain, ridge `1e-6` |
| Proposal multiplier | `2.38 / sqrt(2)` through `auto` |
| Master seed | 20260831 |
| Required gates | R-hat `< 1.01`; bulk and tail ESS `>= 300` |
| Additional test acceptance range | `0.20` to `0.50` per production chain |

This corresponds to 10,000 pilot and 25,000 production transitions, executed
sequentially by the current runner.

## What the qualification checks

The extensive test requires:

- five distinct dispersed starts and production seeds;
- a positive-definite two-parameter proposal covariance;
- finite samples inside the calibration ranges, without visible accumulation at
  their limits;
- convergence of every applicable parameter or derived quantity;
- MCSE of the mean no larger than 10% of posterior standard deviation;
- exact row-wise preservation of `mu`, `shift`, derived `p50`, objective, and
  modeled concentrations;
- independent forward recomputation of representative retained rows;
- agreement of the fitted latent concentrations with the observations under
  the registered in-sample residual limits.

The acceptance interval is a profile-specific regression bound, not a general
PyAges convergence criterion.

The fitted concentration distribution is **not a posterior predictive
distribution**: PyAges evaluates the latent model response for retained
parameter states but does not draw new observation noise. The check is
therefore described as an in-sample check of fitted latent predictions.

For the fixed seed in the qualified environment, the observed maximum R-hat
was `1.001381`, the minimum bulk ESS was `2485.89`, the minimum tail ESS was
`2950.23`, chain acceptance fractions ranged from `0.3480` to `0.3738`, and the
normalized RMS residual of the median fitted latent prediction was `1.0687`.
The executable test enforces scientific thresholds rather than exact equality
to those descriptive values.

Run it with:

```bash
python -m pytest -q --run-extensive tests/examples/test_ploemeur_multichain_scientific.py
```

## Limits

This test does not supply known field values for `mu` or `shift`. It does not
cover F11, the complete monitoring record, an independent validation sample,
alternative LPM families, tracer-history uncertainty, or structural
identifiability. Convergence and a coherent in-sample latent fit do not prove
that the shifted-exponential LPM is unique or hydrogeologically adequate.
The separate inverse-Gaussian profile uses a different uncertainty scale, so
the two profiles are not a controlled comparison of LPM families.

See {doc}`../user-guide/multichain-mh` for operational interpretation,
{doc}`../science/inference` for diagnostics, and
{doc}`../reports/multichain-mh-qualification-2026-08-31` for the shared
qualification record.
