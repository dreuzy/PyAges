# Scientific and numerical conventions

This page is the implementation-level methods reference for PyAge. It states
the equations and conventions needed to reproduce a scientifically equivalent
calculation. User inputs are described in the {doc}`user guide
<user-guide/index>`; the longer qualification records are linked in
{doc}`reports/index`. It is the normative source for equations, numerical
defaults, boundary behavior, and output transformations. The thematic pages on
the {doc}`scientific overview <scientific-overview>` explain interpretation,
validation, field cases, and reproducibility without redefining those
implementation contracts.

## Forward model and units

For an observation at decimal year $t$, PyAge predicts tracer concentration

```{math}
:label: forward-convolution

C(t;\theta)=\int_{0}^{T_{max}}K(t,\tau)\,dF_\theta(\tau),
\qquad T_{max}=t-t_{min}.
```

$\tau$ is water age in years, $F_\theta$ is the LPM transit-time probability
measure, and $K(t,\tau)$ is the complete response supplied by the tracer at
recharge date $t-\tau$. $K$ includes configured radioactive decay or in-situ
production. $C$ and $K$ retain the concentration unit declared by the tracer;
$F$ and all objective values are dimensionless.

The integration window is the closed interval $[0,T_{max}]$. Mass older than
the available recharge record contributes zero and is **not renormalized**.
Consequently, a constant unit tracer returns the represented window mass, not
necessarily one. The value is available from
{py:meth}`pyage.convolution.convolution.Convolution.window_mass` and, after a
continuous or mixed convolution, from ``diagnostics.window_mass``. This
choice exposes rather than hides truncation of old LPM tails.

Continuous, point-mass, and mixed probability measures use separate paths:

- continuous LPMs use the CDF/partial-moment method below;
- a Dirac mass at age $\tau_0$ contributes $K(t,\tau_0)$ when
  $0\leq\tau_0\leq T_{max}$ and zero otherwise;
- two-Dirac models sum both weighted contributions;
- mixed models evaluate the point mass directly and the normalized continuous
  component separately, then apply each mixture weight exactly once.

The implementation entry point is
{py:class}`pyage.convolution.convolution.Convolution`. The derivation,
performance evidence, and migration from PDF/Simpson integration are recorded
in {doc}`convolution-method-evolution-report`.

## Continuous convolution

The cached age grid resolves variation in $K$, not narrow features in the LPM
PDF. At every bin $[a_i,b_i]$, the LPM supplies

```{math}
F(t)=P(T\leq t),\qquad
M(t)=E[T\,1(T\leq t)].
```

PyAge computes the exact probability mass and centered first moment

```{math}
w_i=F(b_i)-F(a_i),\qquad
q_i=M(b_i)-M(a_i)-a_iw_i.
```

For the affine tracer representation
$K(\tau)=K(a_i)+s_i(\tau-a_i)$, its contribution is

```{math}
C_i=K(a_i)w_i+s_iq_i.
```

This expression is exact for affine $K$ regardless of the width or position of
the LPM density. When the sampled midpoint curvature is too large for the
affine assumption, the code uses $K((a_i+b_i)/2)w_i$ in that bin. CDF
non-monotonicity and inconsistent partial moments raise a
``ConvolutionError``; only negative values compatible with floating-point
roundoff are clipped.

### Adaptive-grid controls

{py:class}`pyage.convolution.settings.TracerGridSettings` accepts a bin when

```{math}
\max(K_a,K_m,K_b)-\min(K_a,K_m,K_b)
\leq f_a\max(K_g,\epsilon)+f_rK_{local}.
```

| Setting | Default | Meaning and numerical implication |
| --- | ---: | --- |
| ``absolute_tolerance_factor`` | $5\times10^{-4}$ | Global tracer-response scale $f_a$ |
| ``relative_tolerance`` | $2\times10^{-2}$ | Local response scale $f_r$ |
| ``linear_curvature_factor`` | $0.1$ | Fraction of that tolerance allowed for affine midpoint curvature |
| ``max_subdivisions`` | 20 | Maximum bisections of an initial interval; failure is explicit |
| ``max_bins`` | 20,000 | Hard memory/run-time bound; failure is explicit |
| ``floating_weight_epsilon_factor`` | 64 | Machine-epsilon multiplier for roundoff clipping only |

These values are dimensionless numerical controls, not fitted or physical
parameters, and they do not constitute a formal global error bound. A
publication using non-default values should archive them and demonstrate that
scientific conclusions are insensitive to further refinement. Chronicle knots
seed the grid, and a one-sided value is preserved at the newest-data boundary
because the tracer response is zero outside its declared record.

## Inverse-Gaussian convention

The ``ig`` model uses physical mean transit time $M=\mathtt{mu}$ and standard
deviation $S=\mathtt{sigma}$, both in years:

```{math}
g(x)=\sqrt{\frac{\lambda}{2\pi x^3}}
\exp\left[-\frac{\lambda(x-M)^2}{2M^2x}\right],
\quad x>0,\qquad \lambda=\frac{M^3}{S^2}.
```

SciPy receives dimensionless ``shape = (S/M)^2`` and
``scale = M^3/S^2``. SciPy's argument named ``mu`` is therefore not PyAge's
physical ``mu``. For ``ig_shifted``, $T=t_0+X$: support begins at ``shift``,
the complete mean is ``shift + mu``, and its standard deviation is ``sigma``.
The raw partial moment used in convolution is

```{math}
E[T1(T\leq t)]
=t_0F_X(t-t_0)+E[X1(X\leq t-t_0)].
```

The CDF's reflected normal term is evaluated in log space to avoid overflow
for narrow distributions. The historical coordinate migration and result
impact are in {doc}`scientific-migration-ig-decay`. The density convention
follows Waugh and Hall (2002), [doi:10.1029/2000RG000101](https://doi.org/10.1029/2000RG000101).

## Objective and likelihood conventions

For ordered observations $y_i$, model values $m_i(\theta)$, and reported
one-standard-deviation errors $\sigma_i>0$ in matching units, the calibration
objective is

```{math}
\chi^2(\theta)=\sum_{i=1}^{n}
\left(\frac{m_i(\theta)-y_i}{\sigma_i}\right)^2.
```

This assumes independent, unbiased Gaussian errors with known standard
deviations. PyAge does not currently represent an observation-error covariance
matrix. Parameter bounds and priors are separate from $\chi^2$.

Three legacy output names must not be interchanged:

| Context | Stored name | Quantity |
| --- | --- | --- |
| optimization and MH target internally | not exported directly | $\chi^2$ |
| ``LpmDist`` result tables | ``obj_function`` | $\sqrt{\chi^2/n}$, dimensionless; no degrees-of-freedom correction |
| systematic parameter maps | ``half_log_chi_square`` | $\tfrac12\log(\max(\chi^2,\mathrm{tiny}))$ |

The function ``normalized_residual_norm`` computes $\sqrt{\chi^2/n}$ after
normalization by uncertainty; it is not an RMSE in concentration units.

## Metropolis-Hastings target and sampling

Within LPM parameter bounds, the enabled target is

```{math}
\log\pi(\theta)=-\frac12\chi^2(\theta)+\log p(\theta)+c.
```

Disabled likelihood or prior terms are omitted. Out-of-bounds states and
parameters outside the configured prior support have log density $-\infty$.
Prior densities are evaluated directly in log space after an exact zero check;
no positive probability floor is substituted for zero support. Given proposal
density $q$, acceptance uses

```{math}
\log u < \log\pi(\theta')-\log\pi(\theta)
+\log q(\theta\mid\theta')-\log q(\theta'\mid\theta),
\quad u\sim U(0,1).
```

Native and linear sum/difference fixed Gaussian proposals are symmetric. The
``scipy_ig_correlated`` proposal is symmetric in SciPy shape/scale/shift
coordinates but not in physical $(M,S,t_0)$ coordinates. Since
$|\partial(shape,scale)/\partial(M,S)|=2/S$, its Hastings correction is
$\log(S_{proposed}/S_{current})$.

``nstep`` counts accepted and rejected transitions. With zero-based iteration
``i``, PyAge retains the current state when
``i > burn_in * nstep`` and ``i % nskip == 0``. Rejected proposals therefore
appear as repeated states, as required for an unbiased chain sample. The seed
initializes NumPy ``default_rng``. Burn-in, thinning, and an acceptance fraction
are not convergence diagnostics: publication runs should report multiple-chain
$\hat R$, effective sample size, and Monte Carlo uncertainty. Proposal
qualification evidence is in {doc}`reports/mh_proposal_qualification`.

## Traceability matrix

| Scientific claim | Code contract | User/manual entry | Qualification evidence |
| --- | --- | --- | --- |
| finite-window convolution and mass | ``pyage/convolution/convolution.py`` | this page; {doc}`user-guide/configuration` | ``tests/convolution/test_convolution_scientific.py``; {doc}`convolution-method-evolution-report` |
| adaptive tolerance semantics | ``pyage/convolution/settings.py`` and ``continuous.py`` | this page | ``tests/convolution/test_convolution_settings.py`` |
| IG physical moments and shift | ``pyage/lpm/models/inverse_gaussian*.py`` | this page; {doc}`user-guide/adding-lpm` | ``tests/lpm/test_inverse_gaussian_analytics.py``; {doc}`scientific-migration-ig-decay` |
| normalized-residual objective | ``pyage/calibration/problem.py`` and ``utils/objective_functions.py`` | this page | ``tests/calibration/test_calibration_problem.py`` |
| MH target, priors, proposals, and retention | ``pyage/calibration/methods/metropolis_hastings.py``, ``methods/prior.py``, and ``mh_proposals.py`` | {doc}`user-guide/configuration`; this page | ``tests/calibration/test_mh_proposals.py``; {doc}`reports/mh_proposal_qualification` |

For every published result, archive the PyAge release or commit, configuration,
input checksums, random seeds, dependency versions, numerical settings, and raw
chains or deterministic outputs. The article wrappers under ``article/`` and
workflow ``result_manifest.json`` files record these links for the current
manuscript calculations.
