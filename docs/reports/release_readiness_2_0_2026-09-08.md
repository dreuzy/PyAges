# PyAges 2.0 release-readiness checkpoint — 2026-09-08

**Status:** technically qualified `2.0.0` release-identity candidate;
independent review, protected-main qualification, and the release tag are still
required.

**Updated 9 September 2026:** the source and citation metadata now carry the
`2.0.0` candidate identity. Its release date must be refreshed if the final tag
is created after 9 September.

This report separates what has been demonstrated locally and on GitHub from the
human and protected-branch gates that still remain. A green feature branch is
strong technical evidence, but it is not by itself authorization to tag and
publish a public release.

## What this iteration stabilized

The current branch deliberately targets PyAges 2.0 rather than 1.3. It removes
public compatibility names and configuration spellings, treats one MH chain
as the one-element case of the common multi-chain workflow, and delegates the
Ploemeur workflow to the same maintained execution path. Historical
article-specific diagnostics are isolated from the reusable package and site
workflow code.

The user-visible migration is documented in
{doc}`../user-guide/migrating-to-2.0`. The guide does not promise an automatic
conversion: old configurations can contain choices about random seeds,
priors, initial states, paths, and temporal calibration that need scientific
review.

## Evidence obtained locally

The following checks succeeded on Windows with Python 3.12.4:

- Ruff lint and formatting checks;
- Pyright over the maintained package, examples, studies, validation code, and
  maintenance, qualification, release, and article scripts: zero diagnostics;
- strict Sphinx HTML build;
- strict Sphinx external-link check, including the successful configured
  retry for two initially slow Zenodo DOI redirects;
- standard suite with branch coverage: **1,665 passed, 22 skipped**, total
  coverage **86.57%**, above the required 75% threshold;
- TracerLPM benchmark validation: **65 passed**;
- focused documentation-contract and project-metadata tests: **44 passed**.

A distribution was also tested independently of the checkout:

1. a source distribution and wheel were built from the current working tree;
2. `twine check` accepted both artifacts;
3. a fresh temporary virtual environment installed the wheel with the exact
   qualified `dev`, `docs`, and `examples` constraints;
4. the imported `pyages` module was confirmed to come from that environment's
   `site-packages`, not from the repository;
5. `pyages check`, `pyages list`, a generated quickstart, and a real
   multi-chain smoke run all succeeded;
6. `pip check` found no inconsistent installed requirement;
7. the exact installed direct dependencies matched the qualified metadata;
8. `pip-audit` found no known vulnerability in the installed third-party
   environment.

The provisional artifacts used for the first local packaging check identified
themselves as version `1.2.0`; they are qualification evidence only and must
not be published. The source tree now carries the `2.0.0` identity so the next
build can verify the real candidate metadata.

The developer's pre-existing global Python environment contains several older
but compatible libraries and therefore does not satisfy the stricter
*exact-version* qualification check. The clean environment does satisfy it.
This distinction is useful: an editable working environment can remain usable,
while release evidence must be produced in a reproducible qualified
environment.

## Evidence obtained on GitHub

The committed revision `6d5d6b4` passed both external qualification layers on
8 September 2026:

- [standard CI run 34279473131](https://github.com/dreuzy/PyAges/actions/runs/34279473131):
  Ruff, portable Pyright, dependency audit, Conda, Python 3.12 through 3.14,
  lower-bound SciPy, pandas 2.2, coverage, TracerLPM, .NET, package, docs, and
  the aggregate CI gate;
- [extensive scientific run 34279473134](https://github.com/dreuzy/PyAges/actions/runs/34279473134):
  complete extensive tests, distributions, draft multi-chain qualification
  archive, and preserved scientific evidence.

The portable typing correction introduced immediately before those runs is
therefore exercised on Linux as well as by the local Windows checks. The
`2.0.0` identity commit must pass the same gates because version metadata and
release-facing documentation are part of the candidate.

## What remains before release

The remaining work is release governance and final qualification, not another
general source-code cleanup.

1. **Qualify the `2.0.0` identity commit.** Push it and require both standard CI
   and the extensive scientific workflow to pass on that exact revision.
2. **Complete the independent continuity review.** The maintainership policy
   requires a second person to perform the documented setup/recovery drill and
   to be represented in ownership routing before a public major release. At
   this checkpoint, pull request 34 has no independent review and
   `.github/CODEOWNERS` lists only `@dreuzy`.
3. **Merge through the protected branch.** After review, merge the candidate
   into `main` and require the protected-main checks, including the extensive
   workflow, to pass on the exact merge commit.
4. **Create the immutable release identity.** Create and push the annotated tag
   `2.0.0` on that qualified `main` commit, then run the release-candidate
   workflow from the exact tag.
5. **Publish only the verified candidate artifacts.** If publication is later
   authorized, TestPyPI and then PyPI must receive the unchanged wheel and
   source distribution attached to the reviewed GitHub release, following
   {doc}`../dev/releasing`.

Further renaming or removal is lower priority unless review or CI identifies a
concrete ambiguity, duplicate execution path, stale compatibility contract, or
defect.

## Decision boundary

This checkpoint is sufficient to stop the broad simplification audit and to
prepare the `2.0.0` identity. It is not sufficient to tag or publish PyAges 2.0
until the identity commit, independent continuity review, and protected-main
qualification are complete.
