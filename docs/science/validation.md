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
| Posterior diagnostics | Calibration proposal, prior, support, and scientific-contract modules plus the extensive synthetic, single-date, prior-active, and temporal multi-chain qualifications | Standard suite; selected extensive tests and reproduction campaigns | {doc}`inference`, {doc}`../user-guide/multichain-mh`, and {doc}`reproducibility` | Convergence diagnostics do not prove uniqueness, tracer consistency, or model adequacy |
| Field benchmarks | Golden and workflow modules in `tests/examples/` and `tests/ploemeur/`, including the three Ploemeur multi-chain qualifications | Standard and scheduled extensive suites | {doc}`case-studies`, {doc}`../examples/ploemeur-multichain`, {doc}`../examples/ploemeur-ig-shifted-prior-multichain`, {doc}`../examples/ploemeur-temporal-multichain`, versioned case inputs, manifests, and accepted fixtures | Results qualify the documented cases only and do not generalize automatically to another aquifer |

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

## Qualification decisions and remaining gaps

The refreshed Ploemeur F09 extensive golden is reproducible on Ubuntu and on
the qualified Windows/Python 3.12 environment. The review in
{doc}`../reports/ploemeur_f09_golden_qualification_2026-08-29` found exact
agreement with the committed values and confirmed finite, bounded outputs, but
also found that the deliberately short 200-transition chains have insufficient
acceptance and state diversity for posterior interpretation. The fixture is
therefore qualified as a deterministic software-regression baseline only; it
is not an independently converged scientific posterior reference.

Four separate opt-in tests now add scientific evidence for the current
multi-chain examples. They qualify the **Unreleased** development-branch
implementation, not the `pyages==1.0.1` package from PyPI:

- `test_synthetic_recovery_multichain_scientific.py` runs four dispersed
  chains, requires the article R-hat/ESS gates, and checks marginal and joint
  recovery of the versioned `mu=28`, `shift=4` truth together with the four
  fitted latent tracer predictions;
- `test_ploemeur_multichain_scientific.py` runs five dispersed chains on the
  historical F09 2010 three-observation example, requires the same convergence
  gates, checks support and joint-row integrity, independently recomputes
  representative forward predictions, and evaluates in-sample standardized
  residuals of fitted latent concentrations;
- `test_ploemeur_ig_shifted_prior_multichain_scientific.py` exercises the
  active parametric prior, three-parameter shifted inverse Gaussian geometry,
  and records contact with the upper `sigma` support rather than
  interpreting convergence as identifiability;
- `test_ploemeur_temporal_multichain_scientific.py` runs the canonical temporal
  workflow over 58 observations and 20 dates, checking convergence, prior and
  proposal provenance, joint-row integrity, independent forward evaluations,
  and in-sample residual limits.

The synthetic result qualifies this one fixed noisy realization; it is not a
frequentist coverage experiment over repeated noise draws. Ploemeur has no
known field parameter truth, so its tests establish reproducible convergence
and internal coherence of fitted latent predictions in-sample, not uniqueness
of an LPM or independent hydrogeological validation. None of these tests draws
new observation noise, so their concentration intervals are not posterior
predictive distributions. Exact protocols, descriptive diagnostics, commands,
and costs are recorded in
{doc}`../reports/multichain-mh-qualification-2026-08-31`.

The single-date shifted-exponential and inverse-Gaussian profiles replace zero
uncertainty placeholders with 1% and 20% of the tracer-history mean,
respectively. The temporal profile instead uses 20% of the absolute observed
concentration. These policies are case assumptions rather than validated
laboratory errors, and the two single-date profiles are not a controlled
cross-LPM comparison.

The scheduled and manually dispatched extensive CI job places pytest temporary
outputs under `.artifacts/extensive-pytest` and uploads all multi-chain result
trees even if the job fails. GitHub retains the raw chain, diagnostic, proposal,
and provenance files for 30 days. This makes a run reviewable, but the expiry
means that a publication must still deposit a durable, checksum-addressed copy
with the exact inputs, environment, source commit, and run metadata.

The TracerLPM/Excel case remains only partially portable, and the external
Holten Dirichlet-sensitivity campaign remains locally unvalidated until its
chains, diagnostics, environment, seeds, and checksums are imported and
reviewed. Current case status is recorded in {doc}`reproducibility`.

The remaining external gaps do not invalidate the analytical tests or the
separately qualified cases above. They do prevent the affected external
baselines from being described as fully independently validated.

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
