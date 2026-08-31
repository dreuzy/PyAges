# Calibrating an LPM

Calibration estimates lumped-parameter model (LPM) parameters from tracer
observations. This page describes the operational choices, validation gates,
outputs, and interpretation limits. The equations are normative in
{doc}`../scientific-methods`; the YAML field reference remains
{doc}`configuration`.

## Choose the calculation

| Calculation | Use it for | It does not establish |
| --- | --- | --- |
| objective map | inspecting parameter sensitivity and possible minima | an optimum or a posterior |
| Simplex/FUQ | repeated optimization after drawing observations from their error distributions | a Bayesian posterior or convergence |
| Metropolis--Hastings (MH) | sampling the configured posterior while preserving joint parameter states | model adequacy or identifiability by itself |

The installed single-date workflow runs the FUQ and MH routes selected in its
configuration. The temporal workflow runs MH either once over the complete
span or independently for each observation date.

## Prepare observations

Each observation must provide a tracer name, finite concentration, explicit
unit, decimal sampling date, and a finite non-negative one-sigma error. A zero
error may enter the concentration container only while a workflow derives an
error; calibration requires every final error to be strictly positive.

Observation units must exactly match the modeled tracer unit. PyAges checks
the labels before entering optimization or sampling and never converts values.
See {doc}`concentrations` for the table schema and preprocessing boundary.

Before a production run, confirm that:

1. the tracer histories cover the recharge dates relevant to the LPM tails;
2. concentration values, errors, and tracer histories use the same physical
   scale;
3. LPM bounds are scientifically defensible and not merely broad numerical
   defaults;
4. observation errors describe known standard deviations under the independent
   Gaussian likelihood assumed by PyAges.

## Configure a single-date run

This example enables both calibration routes while disabling the two optional
parameter-space explorations:

```yaml
dataset:
  name: ploemeur_F09_2010.txt
  year: 2010
  data_dir: examples/natural/ploemeur/data
  verbose: false

lpm:
  model_name: exp_shifted
  data_directory: data_core/data_lpm

run:
  reachable_concentrations: false
  objective_function: false
  calibration_metropolis_hastings: true
  calibration_simplex: true

calibration_metropolis_hastings:
  nstep: 5000
  burn_in: 0.2
  nskip: 10
  seed: 12345
  prior_option: false
  likelihood: true
  monitor: false
  display_traj: false

calibration_simplex:
  init_multiples_n: 3
  fuq_n: 30
```

Run it with:

```bash
pyages run path/to/config.yaml
```

Both `init_multiples_n` and `fuq_n` must be positive. FUQ performs their
Cartesian product: the example runs 90 optimizations. Every uncertainty draw
uses all configured starts. A failed or inconsistent optimizer result stops
the workflow instead of being serialized as a calibrated model.

The single-date launcher exposes the production length, burn-in fraction,
thinning interval, and one-chain seed. With no `multichain` mapping, it keeps
the historical one-chain behavior. The temporal workflow exposes the same
retention controls as `mh_nsteps`, `burn_in`, and `nskip`.

## Configure independent chains and proposal tuning

```{note}
This multi-chain workflow is **Unreleased** and is not included in the
`pyages==1.0.1` package from PyPI. Use a development-branch source installation
and record its exact commit until the next release.
```

Multiple chains are opt-in through the presence of a `multichain` mapping. Its
`enabled` field defaults to `true`; `enabled: false` explicitly disables a
retained block. Add the following mapping below
`calibration_metropolis_hastings` for a single-date run, or below `calibration`
for a temporal run:

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

`chains` is the additional parameter that controls how many independent
production chains are run. The default ensemble start policy,
`bounds_stratified`, randomly disperses those starts with a Latin hypercube
over the physical parameter bounds. `prior_sample` instead draws independently
from an enabled prior. `explicit` accepts exactly one complete mapping per
chain. The deterministic `model_default` and `prior_map` policies exist for
compatibility but do not provide dispersed starts.

`master_seed` makes the entire ensemble replayable. PyAges derives distinct
streams for every chain and for initialization, pilot, and production. Set it
to `null` to generate a fresh root seed; the realized value is recorded so the
run can still be replayed. The ordinary `seed` fields apply only to one-chain
execution.

The pilot phase estimates one proposal covariance from all pilot chains after
centering each chain separately. It therefore measures within-chain movement,
does not borrow a covariance from the first chain, and does not confuse
between-chain separation with proposal scale. A small diagonal ridge makes
the estimate positive definite. The covariance and multiplier are then fixed
for every production chain; `auto` uses the conventional
$2.38/\sqrt{d}$ standard-deviation multiplier for $d$ parameters. Pilot draws
are tuning data and are never pooled into the posterior.

This proposal covariance is separate from the prior. An independent prior is
still evaluated only when `prior_option` is enabled; no production chain is
used to define either the prior or its covariance. The complete field and
strategy reference is in
{ref}`optional-multi-chain-mh-configuration`.
The complete execution, qualification, failure, cost, and trace-inspection
procedure is in {doc}`multichain-mh`.

## Understand MH retention

`nstep` counts transitions, including rejected proposals. With a zero-based
transition index $i$, a state is retained only when

```{math}
i > bN \quad\text{and}\quad i \bmod k = 0,
```

where $N$ is `nstep`, $b$ is `burn_in`, and $k$ is `nskip`. The first retained
index is therefore

```{math}
i_0=k\left(\left\lfloor\frac{bN}{k}\right\rfloor+1\right).
```

A configuration that retains no state is rejected before the chain is
allocated. Rejected proposals remain repeated states when their iteration is
retained; deleting those repeats biases the sample. Thinning reduces stored
rows but does not improve the underlying chain or replace effective sample
size (ESS).

Parameter files record `nstep`, `burn_in`, `nskip`, and the derived
`retained_sample_count`. They also record the seed, initialization source,
proposal definition, and resolved prior metadata.

## Priors and proposals

Parameter bounds always define the target support. When `prior_option` is
enabled, PyAges additionally evaluates either the parametric prior declared by
the LPM parameter schema or an explicitly supplied empirical prior family.
Configured defaults and initial values are not evidence that the prior is
appropriate for a particular aquifer.

The core MH interface supports componentwise, diagonal, correlated,
sum/difference, and inverse-Gaussian transformed proposals. Scale and
covariance fields are mutually exclusive and are validated against the chosen
proposal. In the workflow-level ensemble, all pilot chains contribute to one
common covariance, which is fixed before production starts; pilot draws are
not production posterior draws.

## Read and qualify the result

The standard files and exact schemas are listed in {doc}`../reference/outputs`.
In particular:

- `obj_function` is $\sqrt{\chi^2/n}$, not raw $\chi^2$ or a log posterior;
- every table row is one joint parameter and modeled-concentration state;
- `success_rate` is a transition acceptance fraction, not a convergence test;
- marginal summaries must not be recombined to construct derived quantities.

For MH, run multiple independent chains and inspect trace behavior, boundary
contact, rank-normalized split-$\hat R$, ESS, and Monte Carlo uncertainty. The
article qualification thresholds are described in {doc}`../science/inference`.
Also compare residuals by tracer and test sensitivity to priors, initialization,
proposal geometry, LPM family, and observation-error assumptions. A converged
chain can still describe an inadequate or weakly identifiable model.

## Reproducibility checklist

Archive the configuration, normalized observation table, tracer and LPM input
files, PyAges version or commit, dependency environment, random seeds,
proposal settings, raw joint samples, result manifest, and diagnostic report.
Do not report a posterior run as complete when its workflow directory lacks a
complete `result_manifest.json`.

Contributors who call `CalibrationProblem`, `Simplex`, or
`MetropolisHastings` directly should follow {doc}`../dev/extending-calibration-workflows`.
Only `CalibrationProblem` is currently exported from the small public
`pyages.calibration` facade; method modules are contributor interfaces rather
than a stable top-level compatibility promise.
