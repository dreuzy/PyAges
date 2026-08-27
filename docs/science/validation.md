# Scientific Validation Strategy

PyAges separates numerical correctness, inverse-solver behavior, and field-case
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

## Executable traceability

The table maps each scientific claim category to executable evidence. Exact
module counts and short purposes are generated in {doc}`../dev/test-inventory`;
commands and selection rules are maintained in {doc}`../dev/testing`.

| Qualification layer | Executable evidence | CI scope | Supporting reference | Boundary of the evidence |
|---|---|---|---|---|
| Analytical invariants | `tests/lpm/`, `tests/tracer/`, and analytical modules in `tests/convolution/` | Standard suite on Python 3.12--3.14 | {doc}`lpm-reference` and {doc}`forward-model` | Covers declared models and sampled parameter regimes, not every possible extension |
| Independent forward calculations | `tests/convolution/test_convolution_scientific.py`, `tests/ploemeur/test_ploemeur_convolution_reference.py`, and TracerLPM reference tests | Standard suite plus `TracerLPM validation` | Independent quadrature and prepared reference fixtures | Agreement depends on documented grids and tolerances; shared inputs are not fully independent evidence |
| Cross-software inverse cases | `validation/tracerlpm/benchmark/tests/`, with the adapter compilation checked separately | `TracerLPM validation` and `.NET build` | Benchmark fixtures and mapped synthetic cases | GitHub CI does not execute Excel, the XLL, or native Solver on a qualified Windows host |
| Posterior diagnostics | Calibration proposal, prior, support, and scientific-contract modules plus article qualification helpers under `tests/scripts/` | Standard suite; selected extensive tests and reproduction campaigns | {doc}`inference` and {doc}`reproducibility` | Convergence diagnostics do not prove uniqueness, tracer consistency, or model adequacy |
| Field benchmarks | Golden and workflow modules in `tests/examples/` and `tests/ploemeur/` | Standard and scheduled extensive suites | {doc}`case-studies`, versioned case inputs, manifests, and accepted fixtures | Results qualify the documented cases only and do not generalize automatically to another aquifer |

Software delivery checks add a separate layer: CLI, configuration, package,
Conda, documentation, and workflow tests verify that the qualified scientific
code can be installed and invoked. They are documented in {doc}`../dev/ci`
and should not be presented as additional scientific validation results.

## Results reported in manuscript revision v14

| Qualification | Scope | Result |
|---|---|---|
| Forward operator | 133 independent tracer--LPM comparisons | 95% below relative discrepancy $3.6\times10^{-5}$; maximum $1.4\times10^{-4}$ at default tolerances |
| PyAges--TracerLPM inverse comparison | EMM, EPM, and DM; four tracers; 0--20% relative noise | Close recovery at zero noise and broadly comparable point recovery as noise increases; second parameters degrade faster than mean transit time |
| Shifted-exponential identifiability | 19 exact synthetic four-tracer cases with an 8% likelihood error | All pass split-$\hat R<1.01$; minimum pooled ESS 756 |
| Holten H4 | Seven wells, four observables, four age fractions | All 28 posterior-median fractions within 0.02 of the published values; mean absolute difference 0.0055 |
| Ploemeur | F09/F11, full records versus independent 2014--2015 windows | Four calibrations pass the multi-chain gates; repeated observations resolve ambiguity at F09 and expose persistent inter-tracer discrepancy at F11 |

For the historical 133-case row, relative discrepancy means
$|C_\mathrm{PyAges}-C_\mathrm{reference}|/|C_\mathrm{reference}|$ when the
reference is non-zero and `NaN` otherwise. The historical calculation did not
use a $10^{-14}$ denominator floor. Checksum-protected reports and manifests
remain unchanged; this definition corrects the active documentation only.

A subsequent 270-case forward matrix uses an explicit two-regime rule to avoid
unstable relative errors near zero. All 270 cases pass at the default grid and
at the 0.5× and 0.25× tighter grids; deliberately looser 2× and 4× grids fail
12 and 24 cases respectively. The rule and the non-archived implementation run
are documented in {doc}`../reports/forward_qualification_2026-08-27`.

The cross-software exercise is a qualification, not a ranking of optimizers.
PyAges uses an uncertainty-weighted squared-residual objective, whereas the
native TracerLPM workflow uses an absolute-relative-residual objective through
Excel Solver. Differences on noisy realizations can therefore reflect the
objective as well as discretization and optimization.

## Open qualification gaps

The refreshed Ploemeur F09 extensive golden baseline is reproducible on two
independent Ubuntu 24.04/Python 3.12 generations, but it is not yet an
independently approved scientific reference. The refresh changed 312 numerical
fields after the August 2026 calibration and reproducibility refactors. The
required review includes explaining the affected output families, comparing a
qualified Windows run or declaring Linux canonical, inspecting representative
acceptance trajectories, and checking scientific invariants independently of
the stored golden values. Track that review in [GitHub issue
#9](https://github.com/dreuzy/PyAges/issues/9).

The TracerLPM/Excel case remains only partially portable, and the external
Holten Dirichlet-sensitivity campaign remains locally unvalidated until its
chains, diagnostics, environment, seeds, and checksums are imported and
reviewed. Current case status is recorded in {doc}`reproducibility`.

These gaps do not invalidate the analytical tests or the separately qualified
cases above. They do prevent the affected baselines from being described as
fully independently validated.

## What these results do not establish

- They do not validate every possible tracer, LPM, prior, or field site.
- They do not remove structural uncertainty from choosing an LPM family.
- They do not show that posterior precision implies tracer consistency or
  hydrogeological realism.
- They do not make a stationary LPM suitable for genuinely time-varying
  transit-time distributions.

Detailed protocols and historical decisions remain in
{doc}`../reports/index`. Reproduction entry points and manifest rules are
documented in {doc}`reproducibility`. The test traceability matrix is maintained
in {doc}`../dev/testing`.
