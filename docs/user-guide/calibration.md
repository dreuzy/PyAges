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
| deterministic inversion | point estimation under an explicit L1/L2 loss and residual scale | a posterior or uncertainty distribution |
| Simplex/FUQ | repeated optimization after drawing observations from their error distributions | a Bayesian posterior or convergence |
| Metropolis--Hastings (MH) | sampling the configured posterior while preserving joint parameter states | model adequacy or identifiability by itself |

The installed single-date workflow runs deterministic inversion, FUQ, and MH
routes selected independently in its configuration. The temporal workflow runs
MH either once over the complete span or independently for each observation
date.

## Run a deterministic inversion

For a configured single-date workflow, enable the route and choose its
objective explicitly:

```yaml
run:
  deterministic_inversion: true
calibration:
  deterministic_inversion:
    loss: l1
    scale: relative
    relative_floor: 1.0e-12
    optimizer: powell
```

The same one-run selection is available without editing the YAML:

```bash
pyages run config.yaml --deterministic-inversion \
  --objective-loss l1 --objective-scale relative
```

The complete YAML field contract is in {doc}`configuration`. Python callers
can use the lower-level public interface directly:

The public deterministic interface separates three decisions:

1. `CalibrationProblem` prepares the observations, tracer histories, LPM, and
   common physical forward operator;
2. `ObjectiveSpec` defines how residuals are scaled and aggregated;
3. `invert_lpm()` runs the bounded optimizer and returns the selected solution,
   every start attempted, residuals, comparison metrics, and target identity.

For example, an uncertainty-weighted L2 inversion uses the historical PyAges
criterion:

```python
from pyages.calibration import CalibrationProblem, ObjectiveSpec, invert_lpm
from pyages.concentrations import Concentrations

observations = Concentrations.from_file("observations.csv")
problem = CalibrationProblem(
    observations,
    "exp",
    explore_objective=False,
    explore_reachable=False,
).prepare()

result = invert_lpm(
    problem,
    objective=ObjectiveSpec.pyages_default(),
    starts=[{"mu": 5.0}, {"mu": 25.0}, {"mu": 100.0}],
)

print(result.parameters, result.objective_value, result.metrics)
# Detached JSON-compatible provenance for a review table or archive:
serializable = result.to_dict()
```

The objective has two independent components:

| Setting | Definition of the signed residual $r_i$ |
| --- | --- |
| `scale="uncertainty"` | $(m_i-y_i)/\sigma_i$ |
| `scale="relative"` | $(m_i-y_i)/\max(|y_i|,\epsilon)$ |
| `scale="absolute"` | $m_i-y_i$ in the concentration unit |

`loss="l1"` minimizes $\sum_i |r_i|`; `loss="l2"` minimizes
$\sum_i r_i^2$. Thus `ObjectiveSpec.relative_l1()` and
`ObjectiveSpec.relative_l2()` can be run with the same `problem`, optimizer,
and `starts` for a controlled L1/L2 comparison. They use exactly the same
forward model; only residual scoring changes. Absolute aggregation should be
used only when the combined tracers have commensurable units and scales.

The result always reports both relative and uncertainty-standardized L1/L2
diagnostics, regardless of the criterion optimized. Sums, means, RMS values,
and maximum absolute residuals are available. In particular, `relative_l1`,
`mean_absolute_relative_residual`, `relative_l2_squared`, `chi_square`, and
`normalized_residual_rms` can be compared after either inversion without
silently redefining the selected objective. `target_sha256` verifies that two
runs used the same prepared scientific target, and `attempts` preserves every
declared initial point and optimizer outcome. `to_dict()` returns a detached,
JSON-compatible representation of the complete result.

The workflow result and its manifest expose `objective_name`,
`objective_value`, `loss`, `scale`, `relative_floor`, `chi_square`, and
`normalized_residual_rms`. `obj_function` remains a compatibility alias for
the last of these, not the selected deterministic criterion.

This entry point is deterministic and does not change the Simplex/FUQ or MH
targets. In particular, MH retains its independent-Gaussian likelihood based
on uncertainty-weighted chi-square; selecting L1 here does not define a new
posterior likelihood.

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
3. LPM calibration ranges are scientifically defensible search choices, while
   mathematical domains encode formula validity;
4. observation errors describe known standard deviations under the independent
   Gaussian likelihood assumed by PyAges.

## Configure a single-date run

This example enables both calibration routes while disabling the two optional
parameter-space explorations:

```yaml
schema_version: 3

workflow:
  kind: single_date

data:
  name: ploemeur_F09_2010.txt
  year: 2010
  data_dir: data
  verbose: false

lpm:
  models: [exp_shifted]
  directory: ../../../data_core/data_lpm

run:
  reachable_concentrations: false
  objective_function: false
  deterministic_inversion: false
  metropolis_hastings: true
  simplex: true

calibration:
  metropolis_hastings:
    nsteps: 5000
    burn_in: 0.2
    thinning: 10
    seed: 12345
    prior_option: false
    likelihood: true
    display_traj: false

  simplex:
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

Both workflows expose the same `nsteps`, `burn_in`, `thinning`, `seed`, and
`chains` controls. One production chain is simply `chains: 1`.

## Configure independent chains and proposal tuning

Set `chains` above one in the common MH section. There is no separate enable
switch or nested multi-chain configuration:

```yaml
calibration:
  metropolis_hastings:
    nsteps: 5000
    thinning: 1
    chains: 4
    seed: 12345
    initialization:
      strategy: bounds_stratified
    pilot:
      enabled: true
      nsteps: 2000
      burn_in: 0.5
      relative_ridge: 1.0e-6
      proposal_multiplier: auto
    diagnostics:
      max_rhat: 1.01
      min_bulk_ess: 300
      min_tail_ess: 300
      require_convergence: true
```

`chains` controls how many independent production chains are run and may be
one or greater. Inter-chain diagnostics and their qualification gate apply
only from two chains upward. The default `bounds_stratified` policy applies the
same rule for one or several chains. It randomly disperses starts with a Latin hypercube
over the finite parameter calibration ranges. `prior_sample` instead draws
independently from each enabled prior marginal conditioned on its calibration
range.
`explicit` accepts exactly one complete mapping per chain. The deterministic
duplicate-start policies are not supported because they do not provide an
independent convergence check.

`seed` makes the entire run replayable. PyAges derives distinct
streams for every chain and for initialization, pilot, and production. Set it
to `null` to generate a fresh root seed; the realized value is recorded so the
run can still be replayed. The same field applies for every chain count; a sole
production chain uses that exact seed.

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
{ref}`one-to-many-chain-mh-configuration`.
The complete execution, qualification, failure, cost, and trace-inspection
procedure is in {doc}`multichain-mh`.

## Understand MH retention

`nsteps` counts transitions, including rejected proposals. With a zero-based
transition index $i$, a state is retained only when

```{math}
i > bN \quad\text{and}\quad i \bmod k = 0,
```

where $N$ is `nsteps`, $b$ is `burn_in`, and $k$ is `thinning`. The first retained
index is therefore

```{math}
i_0=k\left(\left\lfloor\frac{bN}{k}\right\rfloor+1\right).
```

A configuration that retains no state is rejected before the chain is
allocated. Rejected proposals remain repeated states when their iteration is
retained; deleting those repeats biases the sample. Thinning reduces stored
rows but does not improve the underlying chain or replace effective sample
size (ESS).

Parameter files record `nsteps`, `burn_in`, `thinning`, and the derived
`retained_sample_count`. They also record the seed, initialization source,
proposal definition, and resolved prior metadata.

## Priors and proposals

Calibration ranges always restrict the target support and are themselves
contained in mathematical formula domains. When `prior_option` is enabled,
PyAges additionally evaluates either the parametric prior declared by the LPM
parameter schema or an explicitly supplied empirical prior family.
Configured defaults and initial values are not evidence that the prior is
appropriate for a particular aquifer.

The core MH interface supports componentwise, diagonal, correlated,
sum/difference, and inverse-Gaussian transformed proposals. Scale and
covariance fields are mutually exclusive and are validated against the chosen
proposal. In the workflow-level run, all pilot chains contribute to one
common covariance, which is fixed before production starts; pilot draws are
not production posterior draws.

## Read and qualify the result

The standard files and exact schemas are listed in {doc}`../reference/outputs`.
In particular:

- `obj_function` is the historical compatibility field for
  $\sqrt{\chi^2/n}$, not raw $\chi^2$, a log posterior, or the configurable
  deterministic `objective_value`;
- every table row is one joint parameter and modeled-concentration state;
- `acceptance_rate` is a transition acceptance fraction, not a convergence test;
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
`CalibrationProblem`, `ObjectiveSpec`, `invert_lpm()`, and their immutable
result records are exported from the small public `pyages.calibration` facade.
Simplex and MH method modules remain contributor interfaces rather than a
stable top-level compatibility promise.
