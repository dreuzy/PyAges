# Multi-chain MH refactoring audit — 2026-08-31

**Status:** integrated engineering audit of the Unreleased multi-chain surface.
The current tree registers four fixed-protocol scientific qualification
profiles, includes operational stage inspection and quarantine, builds a
self-verifying qualification archive, and exercises an installed-wheel
multi-chain smoke workflow. These results qualify the registered protocols and
the audited software contracts; they are not a general claim about MCMC
performance, model adequacy, or hydrogeological validity.

## Scope and decision

This audit covers multi-chain Metropolis--Hastings configuration, initialization,
pilot and production execution, diagnostics, immutable run records, target
identity, serialization, workflow integration, result staging and promotion,
operator recovery tools, archive construction, package smoke coverage, public
and contributor APIs, documentation, and the registered scientific profiles.

The refactoring has one canonical ensemble result record, one target-signature
module, one diagnostic-quantity contract, an intentionally small workflow
runtime facade, and no compatibility aliases for the unreleased experimental
surface. No unresolved P0 or P1 defect is known in this audited scope. Release
still requires the ordinary clean-tag, distribution, CI, and durable-evidence
steps described below.

## Registered qualification profiles

The extensive workflow expects all four profiles as one indivisible evidence
set. Each profile has a maintained YAML, executable scientific test, and
task-oriented interpretation page.

| Profile | Protocol and executable evidence | Qualified boundary |
| --- | --- | --- |
| Synthetic shifted-exponential recovery | `examples/synthetic/lpm_recovery_single_date/lpm_recovery_single_date_multichain.yaml`; `tests/examples/test_synthetic_recovery_multichain_scientific.py`; {doc}`../examples/synthetic-recovery` | Known-truth parameter and latent-response recovery for one versioned noisy realization |
| Ploemeur F09 shifted exponential | `examples/natural/ploemeur/exemple_ploemeur_multichain.yaml`; `tests/examples/test_ploemeur_multichain_scientific.py`; {doc}`../examples/ploemeur-multichain` | Fixed-seed convergence, support and joint-row integrity, and in-sample latent-fit coherence for the 2010 record |
| Ploemeur F09 prior-active `ig_shifted` | `examples/natural/ploemeur/exemple_ploemeur_ig_shifted_prior_multichain.yaml`; `tests/examples/test_ploemeur_ig_shifted_prior_multichain_scientific.py`; {doc}`../examples/ploemeur-ig-shifted-prior-multichain` | Three-parameter prior-active convergence and provenance, explicitly retaining evidence of upper-support contact |
| Ploemeur temporal shifted exponential | `examples/natural/ploemeur_temporal/ploemeur_temporal_multichain.yaml`; `tests/examples/test_ploemeur_temporal_multichain_scientific.py`; {doc}`../examples/ploemeur-temporal-multichain` | `span`-mode convergence and row/forward-model consistency for 58 observations over 20 dates under the declared relative-error policy |

The companion {doc}`multichain-mh-qualification-2026-08-31` consolidates the
four profile-level decisions, protocols, numerical evidence, and scientific
limits. Each boundary remains defined by its maintained YAML, executable test,
and interpretation page listed above; combining them does not broaden any one
case beyond its registered target.

The profiles use declared seeds and thresholds and run the current engine
sequentially. Their tests distinguish runtime convergence gates from
profile-specific regression bounds. The three field-data profiles have no known
parameter truth and provide no out-of-sample or posterior-predictive validation.

## Sufficiency of production examples

The four profiles are sufficient to qualify the implemented integration paths
as a release candidate: they cover known-truth recovery, both public workflows,
two model dimensions, inactive and active parametric priors, pilot-derived
covariance, convergence gating, and evidence serialization.

They are not sufficient to claim general scientific production validation. All
three field profiles concern Ploemeur F09; every field uncertainty is derived
from a fallback policy rather than a non-zero reported measurement error; the
checks are in-sample; only `exp_shifted` and `ig_shifted` targets of at most
three dimensions are qualified; and the temporal profile covers only one
stationary `span` target. The synthetic qualification uses one fixed noisy
realization rather than a repeated-noise coverage campaign.

Broader production evidence should be added as separate, versioned protocols,
not by broadening the interpretation of these four:

1. an independent aquifer or well with defensible non-zero uncertainties and a
   held-out sampling window;
2. an `ig_shifted` sensitivity campaign that changes the `sigma` support, prior,
   and error policy explicitly;
3. repeated synthetic realizations and seeds to measure recovery or interval
   coverage rather than one-realization success;
4. a temporal `successive` or second-LPM qualification if those routes are to
   carry the same production claim as the registered `span/exp_shifted` case.

These additions are not blockers for releasing the opt-in multi-chain feature
with its current narrow qualification statement. They are blockers for calling
the example set representative of general hydrogeological production use.

The first step toward item 1 now exists as an explicitly exploratory
Albuquerque SSW 2007 shape-free profile and extensive test. It broadens code
coverage to an independent aquifer and a four-coordinate stick-breaking LPM,
but it does not close the production-evidence gap: zero source uncertainties,
a provisional 1% fallback, a 120-year upper support, three observations for
four latent coordinates, and the absence of an archived independent reference
remain documented blockers. The run also exposes a performance priority:
shape-free convolution inside MH should precompute tracer/bin responses under
an equivalence test before longer chains are made routine.

## Maturity matrix

| Area | Current state | Evidence and remaining boundary |
| --- | --- | --- |
| Ensemble execution and diagnostics | Qualified for the four registered profiles | Independent phase seeds, fresh problems, fixed pilot-derived covariance, convergence-gated pooling, and one ordered live/persisted diagnostic contract; do not generalize beyond the registered targets |
| Configuration, retention, and initialization | Hardened | Frozen controls, canonical retained-count and maximum-ESS calculations, and bounded prior quantile/mode/support operations; prior selection and sensitivity remain scientific responsibilities |
| Target identity and immutable records | Hardened | Versioned target signatures bind independently prepared problems; `MHRunRecord` binds configurations, seeds, samples, diagnostics, metadata, and integrity fingerprints |
| Serialization and result schema | Release candidate | Qualified and rejected ensembles retain chain-level evidence with canonical metadata; incompatible filename or field changes require an explicit schema/migration decision |
| Workflow publication | Hardened | Inputs are validated before isolated staging; schema-3 journals bind CAS state and the terminal-manifest digest; promotion rehashes artifacts, rejects redirection and every nested reserved stage candidate (including a missing/corrupt journal), and attempts explicit rollback around namespace changes |
| Interrupted-stage operations | Operational | `pyages stages inspect` provides read-only human or JSON journal/seal/artifact/CAS diagnosis; `pyages stages quarantine` requires the complete run UUID and confirmation, revalidates under the hierarchy lock, and preserves the tree by sibling rename; there is deliberately no automatic purge |
| Public and contributor API | Release candidate | Canonical MH and runtime facades are enumerated, `ResultRun` is opaque and non-constructible, administrative stage APIs remain outside the contributor facade, and removed aliases are asserted absent |
| Qualification archive | Implemented, publication pending | The generic builder validates terminal manifests, qualified pooling, chain evidence, supplied YAML digests, wheel/sdist identity, source and environment evidence, complete checksums, safe ZIP paths, and deterministic ZIP metadata; CI builds a non-publishable draft, while durable publication requires a clean annotated version tag and external deposit |
| Distribution smoke | CI gate implemented | The package job installs the built wheel outside the checkout, runs CLI/resource checks, a one-chain quickstart, a two-chain smoke profile, stage inspection, and installed-distribution manifest provenance checks |
| Documentation | Validated contract | Active workflow, output, release, CI, archive, and example pages describe the current interfaces and interpretation limits; strict documentation checks must be repeated after later merges |

## Resolved findings

| Previous risk | Resolution in the current tree |
| --- | --- |
| Scientific controls could diverge between execution and serialization. | One immutable `MHRunRecord` owns the exact chain and ensemble configurations consumed by validation, pooling, and writers. |
| Samples or pilot values could change after diagnostics. | Production tables, pilot arrays, covariance, states, and metadata are detached or immutable and covered by integrity snapshots revalidated before pooling and serialization. |
| Independently prepared chains had no proof of a common target. | Every pilot and production problem is compared with one versioned `CalibrationTargetSignature`, whose schema and digest enter provenance. |
| Diagnostic tuples could be incomplete, reordered, or inconsistent with thresholds. | Live computation and immutable-record validation share one canonical quantity, inclusion, ordering, and qualification contract. |
| Concurrent or failed publication could create a false mixed result tree. | Staging captures a complete-tree CAS token under a process-independent global hierarchy lock; promotion seals and rehashes the terminal tree, rejects link/junction redirection and active children, and reports public, staging, and backup paths if rollback itself fails. |
| Interrupted stages had no safe operator path. | Recursive inspection diagnoses journal, terminal seal, artifacts, CAS state, and promotability without writing. Explicit quarantine requires the full UUID, double-checks the managed sibling under the promotion lock, and never deletes evidence. |
| A short-lived CI artifact was the only archive path. | A generic qualification archive now supports explicit `draft` and strict `publishable` modes, embeds result trees, protocols, tests, reports, distributions, source and environment evidence, emits nested checksums and a ZIP sidecar, and independently verifies the completed container. |
| Installed distributions did not exercise the new workflow surface. | The Linux package job installs the wheel in an isolated environment, runs the multi-chain smoke profile, verifies chain/covariance/diagnostic outputs, checks stage inventory, and requires installed-distribution rather than checkout Git provenance. |
| Experimental names created competing supported APIs. | `MHEnsembleResult`, public `ProblemFactory`, workflow builder helpers, workflow stage helpers, and problem-module target-signature aliases were removed; negative API tests prevent their return. |
| Contributor lifecycle services exposed internal state too directly. | `pyages.workflows.runtime` exports only the canonical staged lifecycle and its opaque handle. Stage maintenance is an explicit administrative API and CLI rather than additional contributor lifecycle state. |

## Composition, inheritance, and aliases

The implementation remains composition-based. `MultiChainMetropolisHastings`
coordinates fresh `CalibrationProblem` instances, single-chain samplers, pilot
results, diagnostics, and one `MHRunRecord`; it does not inherit from a workflow,
problem, result record, or single-chain sampler. Within this scope, the only
behavioral inheritance is `MetropolisHastings(CalibrationMethod)`, which
implements the common calibration-method contract. Configuration, seed plans,
diagnostics, chain results, pilot results, and the ensemble record are composed
immutable values.

No compatibility alias is retained for the unreleased multi-chain surface.
Private underscored protocols and helpers are implementation details, not a
second supported API. The canonical user and contributor entry points are
listed in {doc}`../reference/public-api`.

## Recorded engineering decisions

1. Multi-chain execution remains opt-in; existing one-chain workflows remain
   the default.
2. Pilot chains complete before covariance construction, and all production
   chains use that one fixed covariance.
3. Sequential chain execution remains the deliberate implementation choice.
   A thread-parallel prototype reproduced scientific outputs bit for bit when
   runtime fields were excluded, but its measured speedup was too small and
   unstable: the smoke workload averaged `1.05x` with two regressions in seven
   trials, while a five-times-heavier workload averaged `1.09x` and included one
   approximately 20% regression. That evidence does not justify adding executor
   lifecycle, shared LPM-registry behavior, interleaved logs, and additional
   runtime/provenance semantics to the supported surface.
4. One global process-independent hierarchy lock is retained for safe identical
   and ancestor/descendant publication. It intentionally serializes unrelated
   staging creation and promotion.
5. A `started` journal is not proof that its process is dead. Inspection is
   read-only, quarantine requires an operator to stop or exclude the owner, and
   no age-based or automatic deletion is provided.
6. Qualification archives have two explicit states. CI and review builds are
   always non-publishable drafts; publishable mode requires a clean worktree and
   an annotated tag exactly matching the runtime/distribution version.
7. The workflow-runtime facade stays contributor-focused. Operational stage
   inspection and quarantine are available from the CLI and directly from
   `pyages.workflows.runtime.manifest`, not re-exported by that facade.
8. Incompatible changes to target signatures, run journals, public manifests,
   or documented result files require their own schema and migration decisions.

## Residual risks and interpretation limits

- The four profiles do not establish structural identifiability, LPM
  uniqueness, prior robustness, out-of-sample prediction, posterior-predictive
  calibration, or transferability to another aquifer.
- The temporal residual checks use the profile's declared 20% relative-error
  transformation; they do not validate laboratory uncertainty estimates.
- The two single-date Ploemeur profiles replace zero uncertainty placeholders
  with 1% and 20% of the tracer-history mean, respectively. They use different
  likelihood scales and are not a controlled comparison between LPM families.
- The temporal workflow currently forces registered parametric priors rather
  than exposing the single-date prior toggle in its YAML API.
- Integrity snapshots cover the fields known today. Every future nested mutable
  result field must be added deliberately to the freeze/fingerprint contract.
- The global lock favors simple hierarchy safety over publication throughput.
  Chain computation occurs outside it, and neither an available lock nor stage
  age proves that a writer has stopped.
- Quarantine preserves evidence but is not automatic resume, rollback, or
  deletion. Corrupt journals still require manual examination.
- CI's draft ZIP and raw result artifact have finite retention. The archive
  machinery is ready, but no durable DOI or external scientific deposit is
  implied until a publishable tag-built archive is transferred and verified.
- Manifest package metadata and `pip freeze` improve traceability but do not by
  themselves guarantee future binary reproducibility on every platform.
- Real directory-symlink tests can be skipped on an unprivileged Windows host.
  Junction and mocked classification coverage reduce, but do not eliminate,
  the value of a privileged Windows lane.
- The installed-wheel multi-chain smoke is deliberately short and exploratory;
  it validates packaging and integration, not scientific convergence.
- The measured thread prototype establishes deterministic scientific values
  for the tested cases, not a worthwhile or generally safe parallel backend.
  Process parallelism would add further Windows serialization and contributor
  factory constraints and remains unimplemented.
- The direct-Python ensemble example is syntax/control-flow protected in
  standard CI; its long scientific execution remains outside the pull-request
  smoke path.

## Validation evidence without inventory counts

The audited tree contains and exercises the following gates. Exact pytest case
counts are intentionally omitted because collection continues to evolve before
release.

| Gate | Verified contract |
| --- | --- |
| Four extensive scientific profiles | Required configurations, fixed protocols, convergence/precision assertions, forward and row integrity, prior provenance, and terminal manifests |
| Standard integration profiles | Multi-chain engine, diagnostics, configuration, serialization, temporal and single-date workflow integration, and failure evidence |
| Manifest and stage operations | CAS, sealing, artifact rehash, link/junction and nested-stage rejection, rollback diagnostics, read-only inventory, JSON CLI output, exact-UUID quarantine, and no automatic purge |
| Qualification archive tests | Reproducible draft bytes, strict publishable identity, result/YAML/distribution validation, sidecar and member tamper detection, safe paths, and four-result CI discovery |
| Package workflow | Wheel and sdist build/metadata checks plus isolated installed-wheel one-chain and multi-chain smoke execution and provenance assertions |
| Documentation | Strict Sphinx builds, CLI option documentation, and links among CI, release, archive, output, API, and example guidance |
| Parallel prototype | Bit-for-bit scientific outputs outside runtime fields, but low and unstable measured speedups; sequential execution retained |

## Release and preservation actions

1. Run the standard, extensive, strict-documentation, package, metadata, and
   installed-wheel gates on the final release commit.
2. Build wheel and sdist once from the clean annotated release tag, then use
   those exact distributions and the four reviewed result trees to build the
   qualification archive in `publishable` mode.
3. Verify the ZIP and sidecar after transfer, deposit them in the chosen durable
   repository, and record a DOI only after it resolves and its metadata has been
   checked. The scheduled CI draft is not a substitute.
4. Preserve regression coverage for integrity snapshots, diagnostic ordering,
   target signatures, failure manifests, stage inspection/quarantine, archive
   tamper detection, removed aliases, and installed-distribution provenance.
5. Keep sequential execution unless new representative benchmarks demonstrate
   a material, stable gain large enough to justify the concurrency, registry,
   logging, and provenance surface.
6. Reassess the global-lock design only if measured publication contention
   justifies the additional lock-domain complexity.

Operational workflow guidance is in {doc}`../user-guide/multichain-mh`;
interrupted-stage contracts are in {doc}`../reference/outputs`; archive and
release commands are in {doc}`../dev/releasing`; CI behavior is in
{doc}`../dev/ci`.
