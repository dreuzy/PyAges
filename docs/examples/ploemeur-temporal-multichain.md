# Ploemeur temporal multi-chain qualification

```{note}
This profile exercises an **Unreleased** development-branch feature. It is not
included in `pyages==1.0.1`; run it from the source revision that contains this
page and record that revision with the results.
```

This maintained profile calibrates one shifted-exponential LPM against the
Ploemeur F09 temporal record: 58 observations of three tracers over 20 sampling
dates (18 CFC-11 observations and 20 each for CFC-12 and CFC-113). It exercises
the canonical temporal workflow, its parametric priors, pilot covariance,
independently seeded production chains, convergence gate, serialization, and
terminal manifest.

Run it from the repository root:

```bash
pyages run --transient examples/natural/ploemeur_temporal/ploemeur_temporal_multichain.yaml
```

The default result location is:

```text
<results_root>/ploemeur_temporal_multichain/
  ori_ploemeur_F09_2005_2024/span/span_full/exp_shifted/
```

Archive an existing result before rerunning when it must remain qualification
evidence. Promotion uses guarded same-filesystem renames and rollback to replace
the preceding tree; it is not an atomic filesystem exchange of the two trees.

## Scientific target and uncertainty policy

All 58 source rows contain zero uncertainty placeholders. The profile replaces
them with 20% of the absolute observed concentration before calibration. The
configured 1% tracer-history-mean fallback remains recorded but is not used for
this dataset because the first transformation resolves every row. Consequently
the normalized residual checks assess coherence under a fixed relative-error
assumption; they do not validate laboratory uncertainty estimates. The terminal
manifest records the effective transformation and all affected row indices.

The normal priors are loaded from the canonical
`data_core/data_lpm/exp_shifted/params.yaml`, not redefined by this example.
They factorize over `mu` and `shift`; the sampler also enforces their calibration
ranges, so the effective posterior target is restricted to those ranges. This
is one declared prior model, not a prior-sensitivity analysis. The temporal
workflow currently enables registered parametric priors unconditionally; unlike
the single-date workflow, its YAML schema has no `prior_option` or `prior_type`
toggle.

## Fixed protocol

| Control | Value |
|---|---:|
| Observations | 58 over 20 dates |
| LPM | shifted exponential (`exp_shifted`) |
| Parametric priors | `mu ~ Normal(25, 5)`; `shift ~ Normal(10, 2)` conditioned on the calibration ranges |
| Production chains | 4 |
| Production transitions per chain | 5,000 |
| Production burn-in | 0.20 |
| Thinning | none (`nskip: 1`) |
| Retained rows per chain | 3,999 |
| Pilot transitions per chain | 2,000 |
| Pilot burn-in | 0.50 |
| Initialization | `bounds_stratified` over effective bounded prior mass |
| Proposal covariance | pooled within-chain, ridge `1e-6` |
| Proposal multiplier | `2.38 / sqrt(2)` through `auto` |
| Master seed | 20260831 |
| Required gates | R-hat `< 1.01`; bulk and tail ESS `>= 300` |
| Additional test precision bound | relative MCSE of the mean `<= 0.10` |
| Additional test acceptance range | `0.20` to `0.50` per production chain |

The R-hat and ESS thresholds, together with finite MCSE, form the runtime
qualification decision. The relative-MCSE and acceptance ranges are additional
profile-specific regression bounds in the executable scientific test; they are
not general PyAges convergence criteria.

The profile performs 8,000 pilot and 20,000 production transitions. The
current runner executes them sequentially, so it belongs to the scheduled
extensive campaign rather than the pull-request smoke suite.

## What the executable qualification checks

The extensive test requires:

- four distinct starts and production seeds;
- positive-definite fixed production covariance;
- explicit provenance for both normal priors, including their exact means and
  standard deviations;
- finite joint rows inside physical support, with the 0.5% parameter quantiles
  strictly above its lower boundaries, and exact values for all declared
  shifted-exponential moments and quantiles;
- the runtime R-hat, bulk ESS, tail ESS and finite-MCSE gates for every
  applicable parameter and non-constant derived quantity;
- the profile-specific relative-MCSE and per-chain acceptance bounds above;
- exact row-wise agreement between objectives and all 58 fitted
  concentrations;
- independent forward recomputation of representative retained rows;
- a normalized RMS residual no larger than `1.10` and no individual absolute
  normalized residual larger than `5.0`;
- a median retained objective below the objective at the canonical default
  parameter vector (`mu=10`, `shift=10`).

For master seed `20260831` in the qualified environment, maximum R-hat was
`1.003728`, minimum bulk ESS was `1766.99`, minimum tail ESS was `2087.03`, and
chain acceptance fractions ranged from `0.3212` to `0.3346`. The normalized RMS
residual of the median fitted latent response was `0.9177`; the largest
absolute normalized residual was `4.6015`, for CFC-11 in 2021. These values are
descriptive outputs of that fixed run: the test enforces the declared bounds
rather than exact equality, and none of these in-sample summaries establishes
predictive skill.

Run the executable qualification with:

```bash
python -m pytest -q --run-extensive tests/examples/test_ploemeur_temporal_multichain_scientific.py
```

## Interpretation limits

The fitted concentration rows are latent model responses, not posterior
predictive replicates with newly sampled observation noise. The same field
record supplies calibration and residual checks, so this is not an
out-of-sample validation. The profile qualifies only `span` mode, the
shifted-exponential LPM, the documented 20% error policy, this prior, seed, and
chain schedule. It does not prove LPM uniqueness, structural identifiability,
or transferability to another aquifer.

See {doc}`../user-guide/multichain-mh` for operational interpretation and
{doc}`../reports/multichain-mh-qualification-2026-08-31` for the consolidated
qualification boundary.
