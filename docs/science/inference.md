# Bayesian Inference and Diagnostics

## Posterior and likelihood

PyAges combines an uncertainty-weighted Gaussian likelihood with the configured
parameter prior. Observation errors must be finite, strictly positive, and in
units matching their modeled values. They are treated as known standard
deviations; PyAges does not estimate an additional observation-error covariance
model automatically.

The exact $\chi^2$ equation, log target, objective transformations, and legacy
output labels are defined in {doc}`../scientific-methods`. That page is
normative whenever an output uses the generic word “objective.”

## Domains, calibration ranges, and priors

PyAges treats three restrictions separately. The mathematical domain states
where an LPM formula is defined. The finite calibration range states where an
optimizer or sampler is allowed to search for a particular analysis. The prior
weights values before the observations are used. A uniform prior contributes
no relative preference on its support; a normal prior remains informative.
The effective posterior support is the intersection of the calibration range
and prior support, and the calibration range must itself lie inside the
mathematical domain.

Default parameter files are starting configurations, not universal priors.
Report the mathematical domain, actual calibration range, prior family,
parameters, effective support, and coordinate transformation used by a
scientific analysis.

## Metropolis--Hastings workflow

The default stochastic method is a Gaussian random-walk
Metropolis--Hastings sampler. A production workflow may use a short pilot chain
to estimate posterior covariance, add a small scale-aware diagonal ridge, and
then keep that covariance fixed for independent production chains. The pilot
is used to improve proposal geometry; it is not pooled into posterior results.

For pilot chain $c$, with $n_c$ retained parameter vectors
$\theta_{ct}$ and within-chain mean $\bar\theta_c$, PyAges estimates

```{math}
\widehat\Sigma_w =
\frac{\sum_c\sum_{t=1}^{n_c}
(\theta_{ct}-\bar\theta_c)(\theta_{ct}-\bar\theta_c)^\mathsf{T}}
{\sum_c(n_c-1)}.
```

Centering each chain separately prevents dispersion between pilot-chain means
from inflating the random-walk scale. If
$\bar v=\max(\mathrm{tr}(\widehat\Sigma_w)/d,10^{-12})$, the configured ridge
produces $\widehat\Sigma=\widehat\Sigma_w+r\bar v I$; PyAges adds the smallest
numerical diagonal correction still needed if this matrix is singular. With
`proposal_multiplier: auto`, production proposes

```{math}
\theta' = \theta + \frac{2.38}{\sqrt d}Lz,
\qquad LL^\mathsf{T}=\widehat\Sigma,
\qquad z\sim\mathcal N(0,I).
```

The covariance and multiplier are common to all production chains and are
frozen before their first transition. This is adaptation between the pilot and
production stages, not adaptation within a production Markov chain. It is also
separate from the parameter prior.

Burn-in is removed before summaries are computed. Thinning may reduce storage
but does not create independent information and must not substitute for an
effective-sample-size calculation. Random seeds, proposal settings, initial
states, and retained samples are part of the reproducibility record.

One master seed generates distinct initialization, pilot, and production
streams through a stable `SeedSequence` hierarchy. A draw added to a pilot
therefore cannot advance a production stream. `master_seed: null` realizes a
fresh root seed and records it; replay requires reusing that realized value.
Random-stream separation does not imply parallel execution: the current
workflow runner executes the chains sequentially.

The transformed-coordinate Hastings correction, strict burn-in inequality,
thinning rule, repeated-state convention, and proposal symmetries are specified
only in {doc}`../scientific-methods`.

## Convergence criteria

PyAges preserves the `(chain, draw)` structure until diagnostics are complete.
It splits each chain into equal first and last halves, discarding the middle
draw when the retained length is odd. The reported R-hat is the larger of:

- rank-normalized split-R-hat, which detects location differences;
- folded rank-normalized split-R-hat, calculated from absolute deviations from
  the pooled split-sample median, which detects scale differences.

Bulk ESS is calculated from rank-normalized split draws. Tail ESS is the
smaller ESS of the empirical 5% and 95% quantile-indicator sequences. The ESS
calculation uses Geyer's initial-positive and initial-monotone sequence;
antithetic chains can legitimately produce ESS above the raw draw count, up to
the implemented $N\log_{10}(N)$ ceiling. These definitions follow Vehtari et
al. (2021),
[doi:10.1214/20-BA1221](https://doi.org/10.1214/20-BA1221).

The default workflow qualification gates are:

- split-$\hat R < 1.01$ for every reported parameter or derived quantity;
- bulk ESS $\geq 300$ and tail ESS $\geq 300$ before qualified pooling.

PyAges also reports the Monte Carlo standard error of the mean,
$\mathrm{MCSE}=s/\sqrt{\mathrm{ESS}}$. It measures simulation error in the
estimated mean, not posterior spread or observation uncertainty. The generic
workflow requires a finite MCSE but has no configurable relative-MCSE gate. The
four maintained scientific example tests add the case-specific requirement
`MCSE / posterior_sd <= 0.10`.

A derived LPM quantity that is constant across all retained production draws
is reported but excluded from the ensemble gate because R-hat and ESS are not
meaningful for it. A constant native sampled parameter remains a failed
diagnostic: identical stuck chains are not evidence of convergence.

These are qualification gates used by the manuscript workflows, not proof
that the LPM is scientifically adequate. Trace plots, boundary behavior,
posterior geometry, sensitivity to initialization, and the observation fit
must still be examined. More demanding applications may require a larger ESS.

The fitted concentration columns are latent model responses evaluated at the
observations used by the likelihood. PyAges does not draw a new observation
error for each retained state, so those columns and their intervals must not be
called posterior predictive draws. Case checks using them are in-sample checks
of fitted latent predictions.

## Fit is not identifiability

An excellent tracer fit can coexist with weakly identified parameters. In the
shifted-exponential benchmark, `mu` and `shift` are often strongly negatively
correlated: changes in one compensate changes in the other, while their sum is
better constrained. Derived quantities must therefore be calculated row by row
from paired posterior samples. Summing marginal medians or independently
resampling marginal distributions destroys posterior dependence.

A concentrated posterior also does not establish model adequacy. Persistent,
tracer-specific residuals can indicate inconsistent input histories,
transformations, uncertainties, or LPM structure even when MCMC convergence is
excellent.
