# PyAges 2.0 refactoring iteration — 2026-09-07/08

**Status:** engineering checkpoint for the Unreleased branch.

This report explains the outcome of the repository-wide review started for the
next PyAges release. It is deliberately written as a checkpoint: it records
what is already coherent and tested, while keeping the remaining work visible.
It does not certify that a 2.0 distribution is ready to publish.

## Decision: this is a 2.0 release

The changes remove 1.x configuration fields, Python names, modules, and
cardinality-dependent behavior. Existing projects must perform an explicit,
reviewed configuration migration and may obtain a different MH trajectory. Those are
intentional breaking changes, so calling the release 1.3 would understate its
impact. The appropriate next public version is **2.0**.

The source version is still `1.2.0` at this checkpoint. It should be changed
only during release preparation, once the remaining checks below are complete.

## One chain is now the one-element case

There is no longer a separate workflow concept for “single-chain MH” and
“multi-chain MH”. The `chains` field accepts a positive count, and the same
runner performs initialization, an optional pilot, production sampling, result
validation, and publication for every value.

This matters because two code paths that are intended to mean the same thing
will eventually drift. A correction can reach one path but not the other, or
the same option can acquire two subtly different meanings. A single 1..N path
makes the contract easier to explain and test.

The unification includes the following details:

- `bounds_stratified` is the default initialization strategy for every chain
  count. The former `auto` and `chain_default` strategies are removed. A fixed
  scientifically prescribed start uses `explicit`.
- production seeds are derived for every chain, including chain 1. The first
  chain therefore keeps the same production stream when the requested count is
  increased;
- each chain writes its own files below `chains/chain_<N>/`; pooled files remain
  available at the run root;
- `display_traj` controls a real per-chain trajectory figure. The old
  workflow-level `monitor` field is removed because its retained in-memory data
  was discarded by the managed workflow;
- the only remaining chain-count distinction is mathematical: diagnostics that
  compare chains are reported as `not_applicable` when only one chain exists.
  This is not a second execution engine.

The derived seed means that an old one-chain 1.x run does not reproduce the
same numerical trajectory simply by copying its root seed. The 2.0 provenance
file records the actual derived production seed. This intentional change is
covered by the migration guide.

## Compatibility names and inheritance

The installed `pyages` package no longer exposes the compatibility aliases
identified during the review. In particular, the old ensemble class/config
names, flat LPM parameter helpers, ambiguous `bounds` spelling, and obsolete
configuration object names are not parallel entry points in 2.0.

The intermediate schema migrator was ultimately removed. Runtime and tooling
now accept only schema 3, while the user-facing migration guide documents the
manual mapping and the scientific choices that cannot safely be inferred.

The remaining inheritance has a concrete role and should not be removed merely
to reduce class counts:

- `LpmBase` and `LpmScipy` define the common mathematical/model contract;
- Pydantic base models centralize validation policy;
- protocols describe structural tracer capabilities without forcing an
  artificial base class;
- exception inheritance preserves meaningful error categories.

`CalibrationMethod` was removed after this checkpoint's first review. Simplex
and MH now compose a problem and satisfy a structural
`CalibrationAlgorithm` protocol; display and serialization are separate
services.

No deep multiple-inheritance hierarchy or further compatibility-inheritance
layer was found. Composition is already used for the MH runner, sampler, and
scientific problem factory.

## Static analysis and simplification

Pyright now checks the installable package, all maintained examples and site
studies, the whole TracerLPM validation tree, and the common and maintenance
and qualification scripts, plus all article and release builders. The gate
succeeds with zero diagnostics. The LPM registration decorator was made generic, so
decorating a concrete model class preserves its constructor type instead of
erasing it to `LpmBase`.

This wider check found and corrected real ambiguity in Pandas selections,
scalar/array conversions, optional initialization, and maintenance-script data
structures. The corrections use explicit types and control flow; no global
ignore was added to make the report green.

At the beginning of the follow-up iteration, `scripts/article/` was the only
remaining Python tree outside the permanent gate: it had 288 diagnostics in 13
files. Every diagnostic was corrected before the directory was added. There is
now no known Python tree deliberately excluded from the configured Pyright
surface.

The 14 diagnostics originally measured in six validation files were corrected
during this iteration. The changes make numeric values, two-element optimizer
bounds, optional output paths, and the scalar independent-reference contract
explicit. The complete 65-test validation suite passed before `validation/`
was added to the permanent gate.

The 49 diagnostics in nine site files were corrected next. The main changes
validate DataFrame column cardinality, resolve optional paths once, make
numeric LPM constructor contracts accurate, and reject incomplete workflow
state before it can leave a variable undefined. The 290 focused Ploemeur and
LPM tests passed before `sites/` was added to the gate.

The 32 qualification diagnostics were then corrected. In addition to making
grouped Pandas tables unambiguous, this removed `None`-initialized strategy and
result lists from the FUQ/MH calibration benchmark. The benchmark now verifies
that both methods receive the same synthetic target and cannot return
uninitialized results. Its 31 focused tests passed before
`scripts/qualification/` was added to the gate.

Finally, the 68 release diagnostics were corrected. A shared structured-data
boundary now validates required object, list, string, and integer shapes before
article-package, reproduction-archive, promotion, or Zenodo code indexes them.
This replaces repeated assumptions about decoded JSON with contextual format
errors. The 51 focused common/release/article-support tests passed before
`scripts/release/` was added to the gate.

The article scripts were treated in increasing order of diagnostic count. The
largest single source, `scripts/article/build_final_scientific_audit.py`, had
139 diagnostics concentrated in thirteen Pandas expressions. Explicit Series
boundaries and tuple deconstruction removed them without changing the generated
scientific tables. Other corrections validate scalar model results, optional
paths, matrix shapes, workbook conversions, and specialized LPM capabilities.

## Temporal preparation profile and simplification

The Ploemeur temporal profile confirmed a concrete repeated-cost problem. A
four-chain run with an enabled pilot requested nine fresh problems: one for
initialization, four for the pilot, and four for production. Before the change,
the short controlled profile consequently initialized the same scientific
target nine times and built 522 tracer/date grids (9 Ã— 58 observations).

The workflow now prepares one template and calls
`CalibrationProblem.clone_prepared()` for every requested stage. A clone has a
deep-copied mutable LPM, new convolution evaluators, private diagnostics and a
private display configuration. It shares the already loaded tracer histories
and immutable, read-only numerical grids. `ConvolutionTracers` also loads a
tracer name only once when that name occurs at several dates.

After the change, the same controlled profile performed one initialization and
58 grid builds. The measured preparation sum on a warm-cache comparison fell
from about 0.95 s for ten full preparations (the template plus nine simulated
old-style rebuilds) to about 0.27 s for one template plus nine clones. The
end-to-end short-run wall times, 12.56 s and 12.31 s, are too close to claim a
reliable overall percentage; real publication runs spend proportionally more
time in MH transitions. The structural reduction from 580 to 58 grid builds in
that like-for-like comparison is deterministic and is the meaningful result.

Focused tests verify that ordinary continuous and piecewise-uniform clones
reuse the same immutable cache objects, retain identical scientific target
signatures, and cannot overwrite one another's diagnostics or LPM parameters.

## Verification evidence

| Check | Result | What the check establishes |
| --- | --- | --- |
| Standard pytest suite | 1,676 passed; 21 skipped | Fast unit, contract, integration, and non-opt-in regression behavior is coherent. |
| Extensive scientific selection | 15 of 15 effective cases passed | Maintained slow notebook, synthetic, Holten, and Ploemeur scenarios run successfully. |
| TracerLPM validation | 65 passed | Versioned cross-software mappings, inputs, reference data, and comparison infrastructure remain coherent. It does not execute a local proprietary Excel/XLL installation. |
| Ruff lint | passed | The configured error, import, and complexity rules find no violation. |
| Ruff format | all configured Python files compliant | Python formatting matches the repository policy. |
| Pyright maintained gate | 0 errors, 0 warnings | Package, examples, sites, validation, and common/article/maintenance/qualification/release scripts satisfy the current static type contract. |
| Dependency consistency | passed | Installed requirements do not contradict one another. |
| Exact dependency pins | passed | The qualified runtime, development, documentation, and example environments match declared constraints. |
| `pip-audit --local --skip-editable` | no known vulnerability | The installed third-party environment has no vulnerability known to the audit database at check time. |
| Metadata, docstrings, licences, architecture | passed | The repository-specific quick development policies remain satisfied. |
| Test inventory | current | The maintained summary agrees with pytest collection. |
| Coverage | 86.40% total; threshold 75% | The complete standard suite exercises substantially more than the enforced minimum. The newly changed `CalibrationProblem`, `ConvolutionTracers`, and `Convolution` modules reached 100%, 98%, and 91%. |
| Sphinx strict HTML and linkcheck builds | 131 sources passed | References, directives, parsing, output writing, warning policy, and maintained links are valid. |
| Wheel and source distribution | built; `twine check` passed | Both published artifact formats contain valid package metadata and descriptions. |
| Installed-wheel smoke test | passed on Python 3.12 | From outside the checkout, the CLI diagnostic, generated quickstart, one-chain template, and two-chain/pilot template completed with packaged data and installed-distribution provenance. |
| TracerLPM .NET adapter build | 0 warnings, 0 errors | The maintained open adapter compiles; this does not execute the proprietary Excel/XLL engine. |
| `git diff --check` | passed | No whitespace error was introduced in the working diff. |

The final extensive invocation collected 1,697 tests. All 15 opt-in scientific
cases passed; one ordinary configuration test still expected the removed
checkout-relative LPM default. That stale assertion was changed to the
canonical packaged-resource contract, rerun with its CLI and workflow
neighbors (29 passed), and then included in a complete green standard run.
Repeating the hour-long scientific calculations would not exercise changed
runtime code, because only this assertion changed after their successful run.

The optional stricter “nitpicky” Sphinx mode is not part of the current
contract and reports 376 mostly external generated-API type references. That
is a separate documentation backlog; it is not being presented as a green
check for this iteration.

## Defect found by the slow tests

The extensive Ploemeur golden workflow exposed a maintained site script still
constructing `MHConfig` with the removed `nstep` spelling. The script now uses
`nsteps`, and a focused test instantiates the real runner so this interface
drift cannot hide behind mocks. The affected golden evidence was regenerated
only after the seed-contract change and immediately replayed successfully.

This is why the slow selection remains valuable even when the standard suite
is green: it executes longer paths and repository-local study code that is not
part of the installed package.

## Defect found by the installed-wheel smoke test

The first isolated wheel run exposed a different packaging boundary. A project
created by `pyages new config` omitted `lpm.directory`, but the single-date
model supplied the relative default `data_core/data_lpm`. Schema 3 correctly
resolved that path beside the generated YAML, where no such directory exists,
instead of selecting the data shipped in the wheel.

The default now uses the canonical package resource directly. A relative path
still means an intentional project-local override, while an omitted path means
the packaged standard LPM collection. A focused configuration test verifies
that the resolved default contains the requested model parameters. The wheel
was rebuilt and retested in a clean virtual environment from outside the Git
checkout: `pyages check`, the generated quickstart, the maintained one-chain
template, and the two-chain pilot smoke profile all completed. Their manifests
record `package.source: installed_distribution` and no repository commit.

## Remaining work, in recommended order

1. **Run the external platform matrix.** The local Windows/Python 3.12
   qualification is complete. CI must still exercise the documented supported
   Python and operating-system matrix, including the lower-bound and Conda
   environments. A local run cannot honestly replace those environments.
2. **Create the release identity.** After that matrix is green, change the
   source version from 1.2.0 to 2.0.0, date the changelog, build from the exact
   release commit, and tag it. This checkpoint deliberately does not invent a
   release commit or tag while broad parallel changes remain in the working
   tree.

The working tree contained broad, legitimate parallel work during this
iteration. No commit, reset, cleanup, or push is part of this checkpoint.
