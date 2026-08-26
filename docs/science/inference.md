# Bayesian Inference and Diagnostics

## Posterior and likelihood

PyAge combines an uncertainty-weighted Gaussian likelihood with the configured
parameter prior. Observation errors must be finite, strictly positive, and in
units matching their modeled values. They are treated as known standard
deviations; PyAge does not estimate an additional observation-error covariance
model automatically.

The exact $\chi^2$ equation, log target, objective transformations, and legacy
output labels are defined in {doc}`../scientific-methods`. That page is
normative whenever an output uses the generic word “objective.”

## Priors and bounds

Bounds define the admissible parameter domain. A uniform prior contributes no
relative preference inside that domain and zero probability outside it.
Informative priors may encode independent hydrogeological knowledge, but their
effect must be distinguished from information supplied by the tracers.

Default parameter files are starting configurations, not universal priors.
Report the actual bounds, prior family, parameters, and coordinate
transformation used by a scientific analysis.

## Metropolis--Hastings workflow

The default stochastic method is a Gaussian random-walk
Metropolis--Hastings sampler. A production workflow may use a short pilot chain
to estimate posterior covariance, add a small scale-aware diagonal ridge, and
then keep that covariance fixed for independent production chains. The pilot
is used to improve proposal geometry; it is not pooled into posterior results.

Burn-in is removed before summaries are computed. Thinning may reduce storage
but does not create independent information and must not substitute for an
effective-sample-size calculation. Random seeds, proposal settings, initial
states, and retained samples are part of the reproducibility record.

The transformed-coordinate Hastings correction, strict burn-in inequality,
thinning rule, repeated-state convention, and proposal symmetries are specified
only in {doc}`../scientific-methods`.

## Convergence criteria

The article qualification uses multiple independent chains and evaluates the
rank-normalized split-$\hat R$ statistic together with effective sample size
(ESS):

- split-$\hat R < 1.01$ for every reported parameter or derived quantity;
- pooled ESS $\geq 300$ before chains are combined for final article results.

These are qualification gates used by the manuscript workflows, not proof
that the LPM is scientifically adequate. Trace plots, boundary behavior,
posterior geometry, sensitivity to initialization, and the observation fit
must still be examined. More demanding applications may require a larger ESS.

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
