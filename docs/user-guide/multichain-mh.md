# Running and qualifying multi-chain MH

```{note}
Multi-chain MH is an **Unreleased** feature on the development branch. It is
not included in the `pyages==1.0.1` package from PyPI. Until the next release,
install PyAges from the source checkout that contains the configuration and
implementation described here, and record its Git commit.
```

This guide covers the complete operational path: dispersed initialization,
pilot tuning, independent production streams, diagnostics, qualification,
pooling, and inspection. The exhaustive field reference is in
{ref}`optional-multi-chain-mh-configuration`; the statistical definitions are
in {doc}`../science/inference`.

## Start from a reproducible profile

Two maintained single-date configurations exercise the same public workflow as
an ordinary YAML file:

```bash
pyages run examples/synthetic/lpm_recovery_single_date/lpm_recovery_single_date_multichain.yaml
pyages run examples/natural/ploemeur/exemple_ploemeur_multichain.yaml
```

The synthetic case has known generating parameters and is the first profile to
run. The Ploemeur F09 case has no known field parameter truth; it qualifies
convergence and the internal coherence of fitted latent concentrations only.
See {doc}`../examples/synthetic-recovery` and
{doc}`../examples/ploemeur-multichain` for their exact protocols.

Both profiles use deterministic result-directory names. A new run writes into
an isolated, run-ID-derived staging tree while the preceding published result
remains intact. Terminal promotion verifies the staged artifacts and replaces
the exact preceding publication, so the manifest hashes only artifacts from
that run and a stale concurrent run cannot overwrite it. Archive the preceding
result first when it must be retained as qualification evidence.

## Understand the stages

An enabled ensemble follows this sequence:

1. `bounds_stratified` draws one dispersed Latin-hypercube start per chain
   inside the physical LPM bounds, or within the effective marginal prior mass
   when an informative prior is enabled.
2. A distinct pilot random stream advances each start and retains tuning draws.
3. PyAges centers each pilot chain separately and estimates one pooled
   within-chain covariance. A scale-aware ridge makes it positive definite.
4. The covariance and proposal multiplier are frozen before production.
5. Production uses a fresh mutable calibration problem and a distinct random
   stream for every chain.
6. PyAges calculates folded rank-normalized split-R-hat, bulk ESS, tail ESS,
   and the Monte Carlo standard error of the mean before pooling.
7. Root posterior tables are written only after the configured gate passes, or
   after the user explicitly requests exploratory pooling with
   `require_convergence: false`.

Pilot draws tune the random walk; they are never posterior draws. The proposal
covariance is not a prior covariance and is not learned from the first
production chain.

Prior-based ensemble starts use the prior's bounded marginal interface. A
normal marginal is conditioned on the physical LPM interval before its
quantile is inverted; a uniform marginal uses the overlap between its own
support and that interval; and an empirical marginal integrates its
piecewise-linear density after clipping it precisely at the physical bounds.
The initializer therefore does not reinterpret prior storage or distribution
metadata. This keeps `prior_sample`, `prior_map`, and `bounds_stratified` on
one tested scientific definition.

## Choose the controls deliberately

A typical qualification block is:

```yaml
multichain:
  enabled: true
  chains: 4
  master_seed: 12345
  initialization:
    strategy: bounds_stratified
  pilot:
    enabled: true
    nstep: 2000
    burn_in: 0.5
    covariance_mode: pooled_within_chain
    relative_ridge: 1.0e-6
    proposal_multiplier: auto
  diagnostics:
    max_rhat: 1.01
    min_bulk_ess: 300
    min_tail_ess: 300
    require_convergence: true
```

The presence of `multichain:` activates the ensemble because `enabled`
defaults to `true`. The explicit value above makes the intended scientific
profile visible; use `enabled: false` to keep a block in a file without running
it. Omitting the mapping or setting it to `null` selects the historical
one-chain path.

`chains` is the number of pilot and production chains. `master_seed` is the
root of separate initialization, pilot, and production streams. A fixed value
replays the ensemble; `null` realizes and records a fresh root seed. The
ordinary one-chain `seed` is ignored while the ensemble is enabled.

Use `nskip: 1` for diagnostic runs unless storage is a demonstrated constraint.
Thinning discards information and cannot improve mixing. Increase production
length when ESS is insufficient. Do not weaken a gate merely to obtain a
pooled file.

## Interpret qualification and failure

The workflow records one of three statuses:

| Status | Meaning |
|---|---|
| `qualified` | Every applicable quantity has finite diagnostics, R-hat below the configured strict limit, and bulk/tail ESS at or above their limits. |
| `not_qualified` | Diagnostics were calculated, but at least one applicable quantity failed a gate. |
| `diagnostics_unavailable` | Diagnostics could not be calculated; the recorded message gives the cause. |

With `require_convergence: true`, either non-qualified status preserves chain,
seed, pilot, and diagnostic evidence, then fails the workflow. No pooled root
posterior is produced. The workflow writes `result_manifest.json` with
`status: failed`, the exception message, and hashes of the preserved evidence;
this is not a completion marker. With
`require_convergence: false`, pooling is explicitly exploratory and the
non-qualified status remains recorded.

Qualification does not include a scientific acceptance-rate interval, a
relative-MCSE threshold, residual adequacy, uniqueness of the LPM, or external
field truth. Those checks belong to a case-specific protocol.

## Inspect chains and traces

The stable input for trace inspection is the set of per-chain tables, not the
one-chain `monitor` or `display_traj` options. For a single-date run:

```python
from pathlib import Path

import matplotlib.pyplot as plt
import pandas as pd

mh_dir = Path("/path/to/results/Metropolis_Hastings")
chain_files = sorted(mh_dir.glob("chains/chain_*/lpm_dist_calibrated.txt"))

fig, axes = plt.subplots(2, 1, sharex=True, figsize=(10, 6))
for chain_file in chain_files:
    chain = pd.read_csv(chain_file, sep="\t", index_col=0)
    label = chain_file.parent.name
    for axis, parameter in zip(axes, ("mu", "shift"), strict=True):
        axis.plot(chain[parameter].to_numpy(), linewidth=0.7, alpha=0.8, label=label)
        axis.set_ylabel(parameter)

axes[-1].set_xlabel("retained draw")
for axis in axes:
    axis.legend()
fig.tight_layout()
plt.show()
```

Read the numerical diagnostics separately:

```python
diagnostics = pd.read_csv(mh_dir / "mcmc_diagnostics.tsv", sep="\t")
print(diagnostics.to_string(index=False))
```

Inspect all traces for stationarity, slow excursions, different chain modes,
and persistent contact with parameter bounds. Numerical gates complement this
inspection; they do not replace it.

## Budget the calculation

The current ensemble runner executes chains sequentially. Approximate cost is
therefore the sum of all pilot and production transitions:

| Profile | Pilot transitions | Production transitions | Retained production rows |
|---|---:|---:|---:|
| Synthetic | 4 × 1,500 | 4 × 4,000 | 11,996 |
| Ploemeur F09 | 5 × 2,000 | 5 × 5,000 | 19,995 |

Wall time depends strongly on tracer histories, LPM, convolution cache,
processor, and dependency versions. These profiles are extensive scientific
checks, not fast smoke tests.

## Reproduce the executable qualifications

Run each case directly with pytest:

```bash
python -m pytest -q --run-extensive tests/examples/test_synthetic_recovery_multichain_scientific.py
python -m pytest -q --run-extensive tests/examples/test_ploemeur_multichain_scientific.py
```

Or run the complete standard-plus-extensive profile:

```bash
python run_tests.py extensive
```

For a scientific record, preserve the YAML, normalized observations, exact
source commit, environment, all chain tables, diagnostics, proposal covariance,
seed provenance, and complete result manifest. The observed qualification is
summarized in
{doc}`../reports/multichain-mh-qualification-2026-08-31`.
