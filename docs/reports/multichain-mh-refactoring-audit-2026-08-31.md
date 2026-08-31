# Multi-chain MH refactoring audit — 2026-08-31

**Status:** final integrated engineering audit of the Unreleased multi-chain
surface. Scientific qualification remains limited to the versioned cases in
{doc}`multichain-mh-qualification-2026-08-31`. The final standard, extensive,
and focused campaigns passed. Strict documentation, package-build, metadata,
and installed-wheel verification also passed on this consolidated tree.

## Scope and decision

This audit covers the multi-chain Metropolis--Hastings engine, its immutable
configuration and result records, target identity, prior-based initialization,
retention and diagnostic limits, serialization, workflow integration, result
staging, public/contributor API, active documentation, and tests. It records the
final standard and extensive campaign results without broadening their
scientific interpretation.

The refactoring passed final standard, extensive, and focused integration
testing. The previous experimental surface has one canonical result record, one
target-signature module, private workflow helpers, normalized multi-chain
metadata, isolated result promotion, and explicit provenance. No unresolved P0
or P1 defect remains. The remaining gates are preservation of permanent
scientific evidence and the normal downstream release checks on every supported
CI platform; this local qualification used Windows and Python 3.12.

## Maturity matrix

| Area | Maturity at audit | Evidence | Remaining gate |
| --- | --- | --- | --- |
| Ensemble execution and diagnostics | Qualified for registered cases | Independent initialization, pilot and production streams, target-signature checks, convergence-gated pooling, and one canonical diagnostic-quantity contract shared by live calculation and immutable-record validation | Do not generalize the two case qualifications to arbitrary models, priors, data, or chain lengths |
| Configuration and retention schedule | Hardened | Frozen validated controls and canonical strict retained-count/maximum-ESS functions, including boundary and exhaustive small-grid tests | Preserve the same boundary coverage when controls change |
| Prior-based initialization | Hardened | Bounded marginal quantile/mode/support operations for normal, uniform, and empirical priors; the historical one-chain initialization law remains tested separately | Scientific prior choice and sensitivity remain study responsibilities |
| Target identity | Hardened | Versioned immutable signature records have one canonical module; independently prepared pilot and production problems must match | Increment the signature schema if the identity payload changes incompatibly |
| Run record and serialization | Hardened | `MHRunRecord` binds chain/ensemble configuration, seeds, target identity, samples, diagnostics, and resolved metadata; writers consume no second configuration source, use immutable byte-backed pilot arrays, and validate production and pilot integrity snapshots | Keep the integrity payload synchronized with any future result field |
| On-disk multi-chain contract | Release candidate | Canonical `burn_in`, `pilot_burn_in`, and per-chain `acceptance_rate`; stable root `success_rate` and `time_perform` retained intentionally | Treat further filename or field changes as schema changes and document migration |
| Workflow isolation and manifests | Hardened | Public workflows validate scientific inputs before staging; internal journal schema 3 seals the terminal-manifest digest; promotion rejects symlink/junction redirection and active children in both public and incoming trees, distinguishes nested control-file homonyms from valid journals, revalidates artifacts under a process-independent hierarchy lock, and rolls back both namespace changes after a failed commit | Interrupted stages created after validation still require deliberate inspection or cleanup; the global lock deliberately serializes promotions |
| Public and contributor API | Release candidate | Canonical MH and workflow-runtime facades are enumerated, `ResultRun` is an opaque non-constructible handle, removed experimental aliases are tested absent, non-verbose CLI failures print preserved-evidence notes exactly once, and the installed wheel passes the same facade checks outside the checkout | Preserve the installed-package smoke checks in the release workflow |
| Documentation and Read the Docs | Validated in focused audit | Active API, output, result, architecture, method, and workflow pages agree; strict Sphinx HTML and dummy builds pass; the direct-Python example was exercised manually and is protected by syntax and AST contracts; a progressive NumPy-docstring gate covers the qualified calibration/runtime surface | Repeat the strict build after any later source merge; the long example and repository-wide legacy docstrings remain outside standard CI execution |
| Automated test inventory | Final integrated snapshot | 1,374 standard cases, 7 extensive cases, 1,381 core cases including extensive, and 1,446 cases across all documented pytest scopes | Regenerate the inventory after any future collection or marker change |
| Long-term scientific evidence | Partial | Fixed-seed qualification outputs can be uploaded by CI and direct runs carry hashes and provenance | The 30-day CI artifact is not a permanent archive; preserve reviewed chains, manifests, environment, source, and checksums for publication |

## Resolved findings

| Priority | Previous finding | Resolution in the audited tree |
| --- | --- | --- |
| high | Ensemble results and serializers could receive scientific controls from separate objects, permitting provenance to diverge from the run. | One `MHRunRecord` owns the exact chain and ensemble configurations consumed by validation, pooling, and serialization. |
| high | Production or pilot values could be modified after diagnostics and then pooled or serialized against stale diagnostic provenance. | Chain tables are detached and fingerprinted. Pilot covariance and saved pilot arrays use immutable byte backing, pilot fields have an integrity snapshot, and integrity is revalidated before diagnostics, pooling, and writing. |
| high | Independently prepared pilot/production problems had no versioned proof that they represented the same scientific target. | Every stage is compared against a canonical `CalibrationTargetSignature`, and its version and digest are carried into run provenance. |
| high | Reused result directories could combine artifacts from different executions or retain a misleading terminal marker. | Public workflows use isolated run-ID staging and whole-tree terminal promotion; manifests hash artifacts from one run only. |
| high | Concurrent runs could publish over a result tree changed after their staging began, redirect through a link-like path, admit an active child from the incoming tree, or strand the previous tree under a backup name after a failed commit. | Staging captures a complete-tree publication token under a cross-process hierarchy lock. Internal journal schema 3 seals the terminal manifest, promotion rejects symlinks and junctions, scans both public and incoming trees for valid active child journals while preserving ordinary homonymous artifacts, revalidates terminal artifacts, and rolls back both namespace changes after a failed rename. |
| medium | Creating staging before scientific input loading or validation could leave an orphan started tree for a run that never reached executable preparation. | Public runners now complete input loading and validation before creating the staged run context. |
| medium | Pilot, production, seed, threshold, and retained-count relationships were represented but not all cross-validated in the result object. | Run construction and integrity validation bind chain count, exact retained rows, pilot state transitions, phase seeds, explicit starts, and diagnostic decisions to frozen configuration. |
| medium | A diagnostic tuple could be incomplete, misordered, disconnected from stored chain columns, or carry a qualification flag inconsistent with configured thresholds. | Live computation and run-record validation share one canonical ordered quantity/inclusion contract. The record requires exactly the sampled parameters and declared derived moments, finite values in every chain, the constant-derived inclusion policy, and a qualification decision recomputed from frozen thresholds. |
| medium | Convergence rejection and unavailable diagnostics could be confused with generic runtime defects or lose their completed chain evidence. | `MHConvergenceError` and `MHDiagnosticsUnavailableError` are dedicated error types. Public workflows write and promote a terminal failure manifest only for the convergence rejection path, attach the preserved result location to the raised error, print that note once in the non-verbose CLI, and do not reclassify unrelated exceptions. |
| medium | Prior initialization duplicated distribution-specific storage knowledge outside `Prior`. | Bounded marginal operations are canonical on `Prior`; initialization consumes a small structural protocol rather than prior storage internals. |
| medium | Retention and feasible ESS limits were duplicated across validation and execution. | Strict retention and maximum split-ESS calculations live in `pyages.calibration.sampling_schedule` and are tested independently. |
| medium | Git provenance could be attributed to an enclosing checkout even when the imported package came from an untracked environment or wheel. | Manifest provenance distinguishes a tracked worktree from installed-distribution metadata and records PEP 610/`RECORD` evidence when available. |
| low | Experimental aliases enlarged the unreleased API and preserved multiple names for one responsibility. | `MHEnsembleResult`, `ProblemFactory`, workflow builder helpers, and target-signature aliases were removed; internal builders/protocols are private and negative API assertions prevent their old public names from returning. |
| low | Multi-chain files reused the one-chain `burn-in` and `success_rate` spellings inconsistently. | Multi-chain parameters and chain metadata use `burn_in`, `pilot_burn_in`, and `acceptance_rate`; the established root summary fields remain available to existing consumers. |
| low | Contributor workflow services were discoverable only through their implementation module, and callers could treat staged-run state as a constructible data model. | A canonical runtime facade exposes only the staged lifecycle; `ResultRun` is an opaque handle created by `begin_staged_result_run()` and validated again during promotion. |
| low | Direct Python use of the ensemble had no maintained task-oriented example. | The multi-chain guide now contains a facade-only example with a fresh prepared problem per stage/chain, guarded pooling, and failed-diagnostic inspection; it was run manually and its syntax and control-flow markers are checked in CI. |

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
- Two tests that create real directory symlinks are skipped on the qualified
  Windows host when it lacks link-creation privilege. Junction-specific tests
  and mocked link/junction classification still exercise the rejection logic,
  but a privileged Windows CI lane would provide stronger end-to-end evidence.
- The NumPy-docstring gate is intentionally progressive over the qualified
  calibration and workflow-runtime surface; it is not a repository-wide
  pydocstyle claim for legacy modules.
- The direct-Python ensemble example is long-running. It was exercised manually,
  while standard CI protects its syntax, canonical configuration spelling, and
  guarded control flow through compilation and AST assertions rather than
  executing every chain.
- One global process-independent lock deliberately serializes staged-run
  creation and promotion, including unrelated result roots. This favors a
  simple hierarchy-wide safety contract over concurrent publication throughput.

## Validation evidence

The documentation/API/test review and final integrated campaigns provide the
following evidence.

| Check | Result |
| --- | --- |
| Search for removed MH result/factory/helper aliases and obsolete multi-chain metadata | No old public alias or old per-chain field remains; only removal prose, negative assertions, intentional root/one-chain compatibility fields, and private implementation names remain |
| Final focused hardening selection | 179 passed, 2 symlink tests skipped on unprivileged Windows, in 106.59 seconds |
| Manifest lifecycle subset | 30 passed, 2 real-symlink tests skipped; journal sealing, link/junction rejection, nested public and incoming stages, homonymous nested artifacts, CAS, locking, and rollback covered |
| MH and documentation contract subset | 43 passed; canonical diagnostics, direct-example syntax/AST contract, facade selection, CLI evidence note, and progressive docstrings covered |
| Progressive qualified-surface docstring check | Passed; this is intentionally not a repository-wide pydocstyle claim |
| Final generated inventory | 1,374 standard; 7 extensive; 1,381 core including extensive; 1,446 across all documented pytest scopes |
| Standard profile | 1,372 passed, 9 skipped (7 opt-in extensive and 2 unprivileged-Windows symlink tests) in 629.02 seconds |
| Extensive profile | 7 passed, 1,374 deselected in 948.35 seconds |
| Combined standard and extensive elapsed time | 1,577.37 seconds |
| Strict Sphinx HTML and dummy builds with warnings treated as errors | Passed from a fresh environment and complete source reread |
| Package build and metadata verification | sdist and `py3-none-any` wheel built; `twine check` passed for both archives |
| Installed-wheel smoke verification outside the source checkout | Passed for version/import location, exact canonical MH/runtime facades, removed aliases, opaque-handle construction rejection, scheduling helper, dependency check, and CLI version/LPM/tracer commands |

The fixed-seed scientific evidence and its interpretation boundary are recorded
in {doc}`multichain-mh-qualification-2026-08-31`.

## Post-merge and release actions

1. Repeat the strict documentation, package, and installed-wheel checks if the
   consolidated candidate changes before release.
2. Preserve the immutable-backing and integrity-snapshot regression tests,
   including attempts to re-enable NumPy writes, and extend the fingerprint
   contract whenever a result field is added.
3. Preserve the diagnostic-contract, opaque-handle, manifest-sealing,
   link/junction, incoming-child, rollback, CLI-note, direct-example, and
   progressive-docstring regression checks.
4. Preserve the final qualified chain trees, terminal manifests, exact source
   revision, built package, environment, and checksums in a permanent archive
   before using the results in a publication claim.
5. Increment and document the appropriate schema before any incompatible
   change to target signatures, the internal run journal, manifests, or
   documented result files.

Operational guidance is in {doc}`../user-guide/multichain-mh`; the public and
contributor surface is in {doc}`../reference/public-api`; file and manifest
contracts are in {doc}`../reference/outputs` and {doc}`../reference/results`.
