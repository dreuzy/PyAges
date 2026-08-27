# Forward Model and Tracer Conventions

This page explains the assumptions needed to interpret a PyAges forward
calculation. The exact finite-window equation, integration formula, adaptive
tolerances, boundary behavior, and code links are defined once in the
normative {doc}`../scientific-methods` reference. Configuration examples and
file schemas are documented in {doc}`../user-guide/configuration`.

## Lumped-parameter formulation

For a sample collected at time $t$, PyAges combines the tracer response for
water recharged at $t-\tau$ with the LPM probability measure of transit time
$\tau$. PyAges assumes a **stationary** transit-time distribution: its
parameters do not change with sampling date within one calibration. The
implemented integral is limited by the available input-history window; it is
not an abstract infinite-domain integral with automatic tail renormalization.

The generic tracer response combines a recharge value $C_{T0}$, a spatially
uniform zeroth-order production rate $\alpha$, and a first-order loss rate
$\beta$:

```{math}
C_T(t-\tau,\tau) =
\begin{cases}
C_{T0}(t-\tau) + \alpha\tau, & \beta=0,\\
C_{T0}(t-\tau)e^{-\beta\tau}
+ \dfrac{\alpha}{\beta}\left(1-e^{-\beta\tau}\right), & \beta>0.
\end{cases}
```

Conservative tracers use $\alpha=\beta=0$. Radioactive decay uses
$\beta=\ln(2)/t_{1/2}$ when `half_life` is supplied, or
$\beta=1/\tau_{mean}$ when `decay_mean_lifetime` is supplied. The two decay
fields are mutually exclusive. With production and loss, the produced
component tends to $\alpha/\beta$ at large age.

This generic law does not represent spatially varying reactions, nonlinear
kinetics, isotope fractionation, or a general coupled parent--daughter system.
Such behavior requires a tracer-specific programmatic implementation. The
Holten $^3$H to tritiogenic-$^3$He response is one such case-specific model.

## Input histories, dates, and units

Time-series recharge histories are linearly interpolated inside their declared
date range and return zero outside that range. Constant-recharge tracers use the
configured value for every evaluated recharge date.

PyAges records unit metadata but does not perform physical unit conversion.
Observations, uncertainties, and tracer input histories must therefore be
prepared on mutually consistent scales before calibration. In particular,
the distributed CFC and SF6 histories are atmospheric-equivalent mixing ratios;
conversion of measured dissolved-gas concentrations belongs to preprocessing.
Dataset sources, local transformations, attribution, and redistribution limits
are listed in {doc}`../reference/data-provenance`.

## Numerical integration and finite histories

Continuous LPMs are integrated from their CDF and partial first moment on a
grid that resolves the tracer response rather than narrow features of the LPM
density. This makes narrow and shifted distributions stable without a
distribution-specific mesh. Dirac components are evaluated directly, while
mixed models keep their discrete and normalized continuous components
separate.

Probability mass older than the available tracer history contributes zero and
is not renormalized. An insufficient history can therefore reduce the modeled
value; `window_mass` and convolution diagnostics expose the represented mass.
The exact interval equation and numerical acceptance criterion are only in
{doc}`../scientific-methods` to prevent two competing definitions.

## Interpretation limits

- A fitted LPM is a compact representation of flow and mixing, not a unique
  reconstruction of the underlying aquifer velocity field.
- Posterior uncertainty is conditional on the selected LPM, tracer histories,
  kinetic assumptions, observation errors, bounds, and priors.
- Repeated sampling dates provide additional observations under the same
  stationary distribution; they do not by themselves define a time-varying
  transit-time distribution.
