# Forward Model and Tracer Conventions

This page defines the scientific calculation performed by PyAge. Configuration
examples and file schemas are documented separately in {doc}`../user-guide/configuration`.

## Lumped-parameter formulation

For a sample collected at location $x$ and time $t$, the modeled tracer value is

```{math}
C(x,t) = \int_0^\infty C_T(t-\tau,\tau)\,p(x,\tau)\,\mathrm d\tau,
```

where $\tau$ is transit time, $p(x,\tau)$ is the LPM transit-time density, and
$C_T(t-\tau,\tau)$ is the response at sampling after recharge at $t-\tau$.
PyAge assumes a **stationary** transit-time distribution: its parameters do not
change with sampling date within one calibration.

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

PyAge records unit metadata but does not perform physical unit conversion.
Observations, uncertainties, and tracer input histories must therefore be
prepared on mutually consistent scales before calibration. In particular,
the distributed CFC and SF6 histories are atmospheric-equivalent mixing ratios;
conversion of measured dissolved-gas concentrations belongs to preprocessing.

## CDF--partial-first-moment integration

For a fixed sampling date, define $K(\tau)=C_T(t-\tau,\tau)$. Continuous LPMs
are integrated on a grid designed to resolve changes in $K$, not peaks in the
LPM density. Let $F$ be the LPM cumulative distribution and

```{math}
M(u)=E[T\,\mathbf 1_{T\leq u}]
```

its raw partial first moment. For one interval $[a_i,b_i]$,

```{math}
w_i = F(b_i)-F(a_i), \qquad m_i=M(b_i)-M(a_i).
```

If $K$ is approximated linearly with slope
$s_i=[K(b_i)-K(a_i)]/(b_i-a_i)$, the interval contribution is

```{math}
C_i = K(a_i)w_i+s_i\left(m_i-a_iw_i\right).
```

The expression is exact whenever the tracer response is linear within the
interval, regardless of the width of the LPM density. The tracer grid is
prepared once per tracer and sampling date and reused during calibration.
Discrete Dirac components are evaluated directly.

Probability mass older than the available tracer history is not renormalized.
Consequently, an insufficient input-history window can reduce the modeled
concentration and must be interpreted through the reported covered-mass and
truncation diagnostics.

The exact closed-window convention, adaptive-grid tolerances, floating-point
guards, implementation entry points, and validation tests are cross-referenced
in {doc}`../scientific-methods`.

## Interpretation limits

- A fitted LPM is a compact representation of flow and mixing, not a unique
  reconstruction of the underlying aquifer velocity field.
- Posterior uncertainty is conditional on the selected LPM, tracer histories,
  kinetic assumptions, observation errors, bounds, and priors.
- Repeated sampling dates provide additional observations under the same
  stationary distribution; they do not by themselves define a time-varying
  transit-time distribution.
