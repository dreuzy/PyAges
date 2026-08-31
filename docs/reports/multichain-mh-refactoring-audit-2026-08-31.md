# Multi-chain MH refactoring audit — 2026-08-31

**Status:** final integrated engineering audit of the Unreleased multi-chain
surface. Scientific qualification remains limited to the versioned cases in
{doc}`multichain-mh-qualification-2026-08-31`; package-build, metadata, and
installed-wheel verification passed on the audited candidate.

## Scope and decision

This audit covers the multi-chain Metropolis--Hastings engine, its immutable
configuration and result records, target identity, prior-based initialization,
retention and diagnostic limits, serialization, workflow integration, result
staging, public/contributor API, active documentation, and tests. It records the
final standard and extensive campaign results without broadening their
scientific interpretation.

The refactoring passed final standard and extensive integration testing. The previous
experimental surface has one canonical result record, one target-signature
module, private workflow helpers, normalized multi-chain metadata, isolated
result promotion, and explicit provenance. The remaining gates are preservation
of permanent scientific evidence and the normal downstream release checks on
the supported CI platforms.

## Maturity matrix

| Area | Maturity at audit | Evidence | Remaining gate |
| --- | --- | --- | --- |
| Ensemble execution and diagnostics | Qualified for registered cases | Independent initialization, pilot and production streams, target-signature checks, convergence-gated pooling, and the two fixed scientific profiles | Do not generalize the two case qualifications to arbitrary models, priors, data, or chain lengths |
| Configuration and retention schedule | Hardened | Frozen validated controls and canonical strict retained-count/maximum-ESS functions, including boundary and exhaustive small-grid tests | Preserve the same boundary coverage when controls change |
| Prior-based initialization | Hardened | Bounded marginal quantile/mode/support operations for normal, uniform, and empirical priors; the historical one-chain initialization law remains tested separately | Scientific prior choice and sensitivity remain study responsibilities |
| Target identity | Hardened | Versioned immutable signature records have one canonical module; independently prepared pilot and production problems must match | Increment the signature schema if the identity payload changes incompatibly |
| Run record and serialization | Hardened | `MHRunRecord` binds chain/ensemble configuration, seeds, target identity, samples, diagnostics, and resolved metadata; writers consume no second configuration source, use immutable byte-backed pilot arrays, and validate production and pilot integrity snapshots | Keep the integrity payload synchronized with any future result field |
| On-disk multi-chain contract | Release candidate | Canonical `burn_in`, `pilot_burn_in`, and per-chain `acceptance_rate`; stable root `success_rate` and `time_perform` retained intentionally | Treat further filename or field changes as schema changes and document migration |
| Workflow isolation and manifests | Hardened | Public workflows validate scientific inputs before staging; terminal promotion uses a process-independent hierarchy lock, a complete-tree compare-and-swap token, artifact revalidation, nested-stage protection, and rollback to the preceding tree if the commit rename fails | Interrupted stages created after validation still require deliberate inspection or cleanup; preserve failed evidence deliberately |
| Public and contributor API | Release candidate | Canonical MH facade is enumerated, removed experimental aliases are tested as absent, and the built wheel passes installed-package API and CLI smoke tests outside the source checkout | Preserve these source and installed-package checks in the release workflow |
| Documentation and Read the Docs | Validated in focused audit | Active API, output, result, architecture, method, and workflow pages agree; strict Sphinx HTML and dummy builds pass | Repeat the strict build after the final merge and regenerate autosummary from a clean checkout |
| Automated test inventory | Final integrated snapshot | 1,354 standard cases, 7 extensive cases, 1,361 core cases including extensive, and 1,426 cases across all documented pytest scopes | Regenerate the inventory after any future collection or marker change |
| Long-term scientific evidence | Partial | Fixed-seed qualification outputs can be uploaded by CI and direct runs carry hashes and provenance | The 30-day CI artifact is not a permanent archive; preserve reviewed chains, manifests, environment, source, and checksums for publication |

## Resolved findings

| Priority | Previous finding | Resolution in the audited tree |
| --- | --- | --- |
| high | Ensemble results and serializers could receive scientific controls from separate objects, permitting provenance to diverge from the run. | One `MHRunRecord` owns the exact chain and ensemble configurations consumed by validation, pooling, and serialization. |
| high | Production or pilot values could be modified after diagnostics and then pooled or serialized against stale diagnostic provenance. | Chain tables are detached and fingerprinted. Pilot covariance and saved pilot arrays use immutable byte backing, pilot fields have an integrity snapshot, and integrity is revalidated before diagnostics, pooling, and writing. |
| high | Independently prepared pilot/production problems had no versioned proof that they represented the same scientific target. | Every stage is compared against a canonical `CalibrationTargetSignature`, and its version and digest are carried into run provenance. |
| high | Reused result directories could combine artifacts from different executions or retain a misleading terminal marker. | Public workflows use isolated run-ID staging and whole-tree terminal promotion; manifests hash artifacts from one run only. |
| high | Concurrent runs could publish over a result tree changed after their staging began, and a failed commit rename could strand the previous tree under a backup name. | Staging captures a complete-tree publication token under a cross-process hierarchy lock. Promotion compares that token, revalidates terminal artifacts, refuses active nested stages, and restores the preceding tree if the staging-to-public rename fails. |
| medium | Creating staging before scientific input loading or validation could leave an orphan started tree for a run that never reached executable preparation. | Public runners now complete input loading and validation before creating the staged run context. |
| medium | Pilot, production, seed, threshold, and retained-count relationships were represented but not all cross-validated in the result object. | Run construction and integrity validation bind chain count, exact retained rows, pilot state transitions, phase seeds, explicit starts, and diagnostic decisions to frozen configuration. |
| medium | A diagnostic tuple could be incomplete, misordered, disconnected from stored chain columns, or carry a qualification flag inconsistent with configured thresholds. | The run record requires exactly the sampled parameters and declared derived moments, finite values in every chain, the canonical constant-derived inclusion policy, unique ordered names, and a qualification decision recomputed from frozen thresholds. |
| medium | Convergence rejection and unavailable diagnostics could be confused with generic runtime defects or lose their completed chain evidence. | `MHConvergenceError` and `MHDiagnosticsUnavailableError` are dedicated error types. Public workflows write and promote a terminal failure manifest only for the convergence rejection path, attach the preserved result location to the raised error, and do not reclassify unrelated exceptions. |
| medium | Prior initialization duplicated distribution-specific storage knowledge outside `Prior`. | Bounded marginal operations are canonical on `Prior`; initialization consumes a small structural protocol rather than prior storage internals. |
| medium | Retention and feasible ESS limits were duplicated across validation and execution. | Strict retention and maximum split-ESS calculations live in `pyages.calibration.sampling_schedule` and are tested independently. |
| medium | Git provenance could be attributed to an enclosing checkout even when the imported package came from an untracked environment or wheel. | Manifest provenance distinguishes a tracked worktree from installed-distribution metadata and records PEP 610/`RECORD` evidence when available. |
| low | Experimental aliases enlarged the unreleased API and preserved multiple names for one responsibility. | `MHEnsembleResult`, `ProblemFactory`, workflow builder helpers, and target-signature aliases were removed; internal builders/protocols are private and negative API assertions prevent their old public names from returning. |
| low | Multi-chain files reused the one-chain `burn-in` and `success_rate` spellings inconsistently. | Multi-chain parameters and chain metadata use `burn_in`, `pilot_burn_in`, and `acceptance_rate`; the established root summary fields remain available to existing consumers. |

No unresolved P0 or P1 defect was found in the documentation/API/test-focused
review. The case-specific scientific decision remains the qualification
record's responsibility, not evidence supplied by this structural audit.

## Composition, inheritance, and removed aliases

The multi-chain design remains composition-based. `MultiChainMetropolisHastings`
orchestrates fresh problems, pilot and production samplers, diagnostics, and an
`MHRunRecord`; it does not inherit from a workflow, result, problem, or
single-chain sampler. Within the MH scope, the only behavioral inheritance is
`MetropolisHastings(CalibrationMethod)`. That relationship is legitimate
because the single-chain sampler implements the common calibration-method
contract. Configuration and result records use immutable value composition,
while workflow contexts compose paths, inputs, and runtime services.

No compatibility alias is retained for the unreleased surface. In particular,
`MHEnsembleResult`, public `ProblemFactory`, public
`build_mh_ensemble_config`, public `mh_stage_directory`, and the former
problem-module target-signature aliases are absent. Private implementation
names beginning with an underscore are not a second supported API, and
negative public-API tests prevent the removed public spellings from returning.

## Residual risks and interpretation limits

- Immutable byte backing and integrity snapshots cover the current proposal,
  pilot, and production-result fields. A future field added to these records
  must be included deliberately in the copy/freeze or fingerprint contract;
  frozen dataclass syntax alone is not sufficient for nested mutable values.
- `time_perform` and the summed pilot/production runtime fields do not prove
  wall-clock parallelism. The current engine's reproducibility and audit
  contracts must not be presented as a parallel-speedup claim.
- Passing convergence thresholds on the two registered profiles does not prove
  identifiability, model adequacy, prior robustness, out-of-sample prediction,
  or performance on another aquifer.
- A failure manifest proves that a required gate rejected preserved evidence;
  it never authorizes pooling or scientific use of those chains.
- Manifest package and dependency evidence improves traceability but is not a
  complete environment lock. Publication archives still need the exact package
  artifact and a reproducible environment description.
- Private implementation names and negative removal assertions can contain the
  old lexical stems without recreating a supported alias.

## Validation evidence

The documentation/API/test review and final integrated campaigns provide the
following evidence.

| Check | Result |
| --- | --- |
| Search for removed MH result/factory/helper aliases and obsolete multi-chain metadata | No old public alias or old per-chain field remains; only removal prose, negative assertions, intentional root/one-chain compatibility fields, and private implementation names remain |
| Post-hardening proposal, pilot-result, MH serialization, and public-API selection | 54 passed |
| Final generated inventory | 1,354 standard; 7 extensive; 1,361 core including extensive; 1,426 across all documented pytest scopes |
| Standard profile | 1,354 passed, 7 skipped in 455.41 seconds |
| Extensive profile | 7 passed, 1,354 deselected in 928.54 seconds |
| Combined standard and extensive elapsed time | 1,383.95 seconds |
| Strict Sphinx HTML and dummy builds with warnings treated as errors | Passed |
| Package build and metadata verification | sdist and `py3-none-any` wheel built; `twine check` passed for both archives |
| Installed-wheel smoke verification outside the source checkout | Version, complete canonical MH facade, removed-alias assertion, scheduling helper, and CLI version/LPM/tracer commands passed |

The fixed-seed scientific evidence and its interpretation boundary are recorded
in {doc}`multichain-mh-qualification-2026-08-31`.

## Post-merge and release actions

1. Repeat the strict documentation, package, and installed-wheel checks if
   source or documentation changes after this audited candidate.
2. Preserve the immutable-backing and integrity-snapshot regression tests,
   including attempts to re-enable NumPy writes, and extend the fingerprint
   contract whenever a result field is added.
3. Preserve the final qualified chain trees, terminal manifests, exact source
   revision, built package, environment, and checksums in a permanent archive
   before using the results in a publication claim.
4. Increment and document the appropriate schema before any incompatible
   change to target signatures, manifests, or documented result files.

Operational guidance is in {doc}`../user-guide/multichain-mh`; the public and
contributor surface is in {doc}`../reference/public-api`; file and manifest
contracts are in {doc}`../reference/outputs` and {doc}`../reference/results`.
