# Ploemeur `ig_shifted` prior-active multi-chain qualification

```{note}
This profile uses an **Unreleased** development-branch feature. Use a source
installation and record the exact Git commit when preserving evidence.
```

This maintained profile adds two contracts not covered together by the other
single-date qualifications: a three-parameter LPM and an active parametric
prior. It reuses the versioned 2010 Ploemeur F09 CFC-11, CFC-12, and CFC-113
observations and fits the shifted inverse-Gaussian (`ig_shifted`) LPM.

## Run the profile

From the repository root:

```bash
pyages run examples/natural/ploemeur/exemple_ploemeur_ig_shifted_prior_multichain.yaml
```

The default result location is:

```text
<results_root>/ploemeur_f09_ig_shifted_prior_multichain/ploemeur_F09_2010.txt/Metropolis_Hastings/
```

## Scientific target and prior

The source observations contain zero uncertainty placeholders. This profile
replaces them with 20% of the mean tracer-history response evaluated at the
sampling date, matching the maintained Ploemeur inverse-Gaussian study
assumption. This is a case-specific uncertainty policy, not a relative error on
the observed concentration and not a universal measurement-error model.

The prior is not declared ad hoc in the example. With `prior_option: true`, MH
loads the canonical uniform distributions from
`data_core/data_lpm/ig_shifted/params.yaml`:

| Parameter | Calibration range (years) | Parametric prior (years) | Effective sampled support (years) |
|---|---:|---:|---:|
| `mu` | 0.1 to 100 | 0 to 100 | 0.1 to 100 |
| `sigma` | 0.1 to 30 | 0 to 30 | 0.1 to 30 |
| `shift` | 0.1 to 50 | 0 to 30 | 0.1 to 30 |

The serialized calibration metadata records each prior family and its
parameters. The `prior_sample` initialization draws each marginal independently
from the corresponding prior conditioned on its intersection with the
calibration range, using its bounded quantile. It does not draw and reject
values outside that range, and `max_attempts` is not consumed by this strategy. For the
fixed seed, the five starts are distinct and widely dispersed in all three
coordinates.

## Fixed protocol

| Control | Value |
|---|---:|
| Production chains | 5 |
| Production transitions per chain | 15,000 |
| Production burn-in | 0.20 |
| Thinning | none (`nskip: 1`) |
| Retained rows per chain | 11,999 |
| Pilot transitions per chain | 5,000 |
| Pilot burn-in | 0.75 |
| Initialization | independent `prior_sample` draws |
| Proposal covariance | pooled within-chain, ridge `1e-6` |
| Proposal multiplier | `2.38 / sqrt(3)` through `auto` |
| Master seed | 20260831 |
| Required gates | R-hat `< 1.01`; bulk and tail ESS `>= 300` |
| Additional test acceptance range | `0.20` to `0.40` per production chain |

This is 25,000 pilot and 75,000 production transitions, currently executed
sequentially. Fixed-seed `prior_sample` review runs took about 4 to 7 minutes
under different concurrent machine loads; a bounds-stratified comparison took
about 2.6 minutes. Time in the wide inverse-Gaussian parameter region is also
state dependent. Runtime is descriptive and is not a test threshold.

The retained `prior_sample` run had maximum R-hat `1.001912`, minimum bulk ESS
`1915.23`, minimum tail ESS `3001.80`, and production acceptance fractions
from `0.3219` to `0.3411`. The acceptance interval is a profile-specific
regression bound, not a general PyAges convergence criterion. The executable
test enforces the declared bounds, not exact equality to these
environment-dependent summaries.

## Executable checks

Run the qualification with:

```bash
python -m pytest -q --run-extensive tests/examples/test_ploemeur_ig_shifted_prior_multichain_scientific.py
```

The test checks all native parameters and non-constant derived moments,
including `mean = mu + shift` and `std = sigma`. It also checks prior
provenance, distinct phase seeds and dispersed starts, a positive-definite 3x3
proposal covariance, joint-row objective integrity, independent forward
recomputation, fitted-latent concentration intervals, and the result manifest.

## Interpretation limits

For the fixed-seed run, the 97.5% posterior quantile of `sigma` is about 29.48
years and the 99.5% quantile is about 29.90 years against an upper support of
30 years. The extensive test deliberately preserves evidence of this contact.
It must not be reported as an interior, data-identified estimate of `sigma`.
Changing or widening that prior would define a different scientific target and
requires a separate sensitivity analysis.

The observations have no known field parameter truth. Qualification establishes
numerical convergence, provenance, and internal in-sample coherence for this
fixed target. It does not establish structural identifiability, model
uniqueness, posterior predictive calibration, out-of-sample skill, or
hydrogeological validity. The fitted concentration rows contain latent model
responses; they do not include newly simulated observation noise.
