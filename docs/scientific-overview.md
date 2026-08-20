# Scientific overview

PyAge estimates groundwater transit-time distributions from environmental
tracer observations. It combines tracer recharge histories with lumped
parameter models (LPMs), predicts concentrations by convolution, and calibrates
model parameters against measurements.

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
- LPM YAML defining parameter bounds, initialization, and calibration data.

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

Results are sample tables (`LpmDist`) from which summary statistics, selected
LPMs, diagnostics, and figures are derived. Randomized qualification paths use
fixed generators or recorded seeds.

## Scientific assurance

The test suite combines:

- analytical tests for distributions, decay, and convolution invariants;
- characterization tests for public data and workflow contracts;
- golden tests for representative tracer, LPM, convolution, calibration, and
  site results;
- optional extensive and external TracerLPM comparisons for slower validation.

Scientific changes that can alter numerical results require an explicit
migration note and reviewed golden-reference updates. See
{doc}`architecture` for code ownership and {doc}`pyage-scientific-audit` for
the detailed audit record.
