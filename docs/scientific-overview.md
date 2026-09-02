# Scientific overview

PyAges estimates groundwater transit-time distributions from environmental
tracer observations. It combines tracer recharge histories with lumped
parameter models (LPMs), predicts concentrations by convolution, and calibrates
model parameters against measurements.

This overview summarizes the workflow. The pages below define the scientific
contract in enough detail to interpret and audit a calculation. They are
aligned with revision v14 of the PyAges v1.0 manuscript and checked against the
current implementation; manuscript-specific numerical results remain clearly
identified as validation records rather than general software guarantees.

## Forward model

For an observation date $t$, the modeled concentration is conceptually

```{math}
C(t) = \int_0^\infty C_{in}(t-\tau)\,g(\tau;\theta)\,d\tau,
```

where $C_{in}$ is the tracer input history, $g$ is the LPM transit-time
distribution, $\theta$ contains the LPM parameters, and $\tau$ is water age.
Radioactive decay and in-situ production are part of the tracer response.

The implementation selects an integration strategy from the probability
measure exposed by the LPM:

- continuous distributions use a cached tracer grid and vectorized cumulative
  quantities;
- Dirac models evaluate one or two point masses directly;
- mixed models combine direct point-mass evaluation with a normalized
  continuous component.

## Scientific inputs

An analysis combines three explicit inputs:

- observation rows with tracer, concentration, uncertainty, unit, and date;
- tracer YAML plus a recharge chronicle or constant recharge value;
- LPM YAML defining mathematical domains, calibration ranges, initialization,
  and prior metadata.

Tracer decay uses exactly one documented convention: `half_life` or
`decay_mean_lifetime`. The two fields are mutually exclusive. New tracers are
normally data additions; new LPMs are registered implementations of the shared
model contract.

## Inference

`CalibrationProblem` prepares the forward model and objective from observations
and an LPM type. A calibration method then searches that problem:

- Simplex provides deterministic optimization;
- Metropolis-Hastings provides posterior sampling with explicit burn-in,
  thinning, prior, likelihood, and proposal settings.

Results are sample tables (`LpmSampleTable`) from which summary statistics, selected
LPMs, diagnostics, and figures are derived. Randomized qualification paths use
fixed generators or recorded seeds.

The exact equations, units, finite-window convention, objective transformations,
and Metropolis-Hastings acceptance rule are specified in
{doc}`scientific-methods`. That page is normative when a short API description
or a legacy output label is ambiguous.

## Scientific assurance

The test suite combines:

- analytical tests for distributions, decay, and convolution invariants;
- characterization tests for public data and workflow contracts;
- golden tests for representative tracer, LPM, convolution, calibration, and
  site results;
- optional extensive and external TracerLPM comparisons for slower validation.

Scientific changes that can alter numerical results require an explicit
migration note and reviewed golden-reference updates. See
{doc}`architecture` for code ownership, {doc}`science/validation` for the
current assurance strategy, and {doc}`reports/scientific_documentation_audit`
for the GMD documentation audit.

## Scientific reference

```{toctree}
:maxdepth: 1

science/forward-model
science/lpm-reference
science/inference
science/validation
science/case-studies
science/reproducibility
```
