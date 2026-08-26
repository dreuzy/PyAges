# Scientific Validation Strategy

PyAge separates numerical correctness, inverse-solver behavior, and field-case
interpretation. A golden test alone only detects change; it cannot establish
that a scientific calculation is correct.

## Qualification layers

1. **Analytical invariants** verify distribution normalization, moments,
   decay, production, Dirac mixtures, and known convolution identities.
2. **Independent forward calculations** compare the production convolution
   with high-accuracy quadrature and independently prepared references.
3. **Cross-software inverse cases** compare mapped LPM parameterizations on
   identical synthetic tracer data.
4. **Posterior diagnostics** verify sampling convergence and expose parameter
   correlations and effective information.
5. **Field benchmarks** test the complete preparation, forward, inference, and
   reporting workflow against published or internally consistent cases.

## Results reported in manuscript revision v14

| Qualification | Scope | Result |
|---|---|---|
| Forward operator | 133 independent tracer--LPM comparisons | 95% below relative discrepancy $3.6\times10^{-5}$; maximum $1.4\times10^{-4}$ at default tolerances |
| PyAge--TracerLPM inverse comparison | EMM, EPM, and DM; four tracers; 0--20% relative noise | Close recovery at zero noise and broadly comparable point recovery as noise increases; second parameters degrade faster than mean transit time |
| Shifted-exponential identifiability | 19 exact synthetic four-tracer cases with an 8% likelihood error | All pass split-$\hat R<1.01$; minimum pooled ESS 756 |
| Holten H4 | Seven wells, four observables, four age fractions | All 28 posterior-median fractions within 0.02 of the published values; mean absolute difference 0.0055 |
| Ploemeur | F09/F11, full records versus independent 2014--2015 windows | Four calibrations pass the multi-chain gates; repeated observations resolve ambiguity at F09 and expose persistent inter-tracer discrepancy at F11 |

The cross-software exercise is a qualification, not a ranking of optimizers.
PyAge uses an uncertainty-weighted squared-residual objective, whereas the
native TracerLPM workflow uses an absolute-relative-residual objective through
Excel Solver. Differences on noisy realizations can therefore reflect the
objective as well as discretization and optimization.

## What these results do not establish

- They do not validate every possible tracer, LPM, prior, or field site.
- They do not remove structural uncertainty from choosing an LPM family.
- They do not show that posterior precision implies tracer consistency or
  hydrogeological realism.
- They do not make a stationary LPM suitable for genuinely time-varying
  transit-time distributions.

Detailed protocols and historical decisions remain in
{doc}`../reports/index`. Reproduction entry points and manifest rules are
documented in {doc}`reproducibility`.
