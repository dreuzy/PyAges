# Scientific Scope of the Field Benchmarks

These pages summarize the assumptions needed to interpret the two field
benchmarks in the PyAges v1.0 manuscript. They are demonstrations of the
documented workflows, not universally applicable preprocessing recipes.

## Holten H4

The Holten benchmark reproduces the four-bin interpretation of seven
production wells sampled in April 2010. It uses four observables: $^3$H,
corrected tritiogenic $^3$He, $^{85}$Kr, and $^{39}$Ar.

Scientific conventions:

- site-specific time-dependent inputs are used for $^3$H and $^{85}$Kr;
- $^{39}$Ar uses normalized modern atmospheric abundance and radioactive
  decay;
- tritiogenic $^3$He is derived from $^3$H decay, not loaded as an independent
  recharge history;
- a two-year unsaturated-zone delay is applied to the $^3$H--$^3$He pair;
- published $^3$He values are already corrected for noble-gas, degassing, and
  radiogenic effects, so those corrections are not repeated;
- a 0.5 TU $^3$He uncertainty is imputed for well 59-05 because its source
  uncertainty is absent; this is a benchmark convention, not a new analytical
  estimate.

The age classes are 0--20, 20--40, 40--60, and `>60 yr`. The first three use
uniformly discretized ages. The open-ended class uses the prescribed published
old-water signature: $^3$H and tritiogenic $^3$He at 310 years, zero $^{85}$Kr,
and $^{39}$Ar equal to 0.45 fraction modern. Its fitted fraction therefore
means mixing with that end member; it is **not** a fraction of water having
exactly age 310 years.

Four fractions are obtained from three bounded stick-breaking latent variables
so that they remain non-negative and sum to one. This article-specific helper
is distinct from the generic finite-bin `shapefree_n_oldbin` LPM. The maintained
example layout is described in {doc}`../examples/holten/README`.

The manuscript discusses a sensitivity experiment using a
Dirichlet(1,1,1,1) prior. The fresh external campaign now includes its immutable
manifest, retained chains, diagnostics and Figure C1. All diagnostic groups pass
the registered split-Rhat and ESS thresholds. This evidence remains a distinct
robustness analysis and does not replace the canonical latent-logit-uniform
Holten campaign.

## Ploemeur

The Ploemeur demonstration uses CFC-11, CFC-12, and CFC-113 records from wells
F09 and F11, with 20% relative observation uncertainty. It compares two
inference problems per well:

- calibration to every available observation in the monitoring record;
- an independent calibration using only the 2014--2015 sampling window.

Both use the same shifted-exponential LPM, tracer histories, likelihood, and
stationary-distribution assumption. Groundwater age is summarized for each
posterior sample by the distribution median
$t_{50}=\mathrm{shift}+\mu\ln(2)$.

At F09, the longer record resolves an ambiguity that remains in the isolated
window and favors a younger solution. At F11, the longer record yields a
concentrated posterior but persistent discrepancies among CFC-11, CFC-12, and
CFC-113. The latter is a model-adequacy warning: posterior concentration and
multi-chain convergence do not imply that all tracers are explained by the
adopted model.

The comparison measures the information supplied by different temporal
sampling extents under one stationary LPM. It does not infer a time-varying age
distribution and does not compare alternative LPM families for the site.
