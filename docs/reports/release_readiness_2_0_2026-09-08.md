# PyAges 2.0 release-readiness checkpoint — 2026-09-08

**Status:** locally qualified engineering checkpoint; not yet a release
candidate.

This report separates what has been demonstrated on the current working tree
from what still requires a committed Git revision and the external CI
platforms. It prevents a successful test run on one developer machine from
being mistaken for complete release evidence.

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

The artifacts built during this checkpoint still identify themselves as
version `1.2.0`. This is intentional: their purpose was to test packaging, not
to create a publishable 2.0 artifact before the final release identity exists.

The developer's pre-existing global Python environment contains several older
but compatible libraries and therefore does not satisfy the stricter
*exact-version* qualification check. The clean environment does satisfy it.
This distinction is useful: an editable working environment can remain usable,
while release evidence must be produced in a reproducible qualified
environment.

## What remains before release

The remaining work is release qualification, not another general source-code
cleanup.

1. **Create and push a reviewable commit.** CI evidence must refer to an exact
   Git revision. Results obtained from an uncommitted working tree cannot serve
   as durable release evidence.
2. **Run the GitHub CI matrix.** The local Python 3.12 result does not establish
   Python 3.13 or 3.14 compatibility, the Conda environment, the Linux .NET
   build, or packaging on a clean GitHub runner.
3. **Run the extensive scientific workflow for that revision.** The focused
   local validation and smoke run demonstrate the affected paths, but the
   canonical workflow must create the complete four-case evidence set.
4. **Finalize the release identity only after those gates are green.** Update
   the source version to `2.0.0`, finalize the changelog date and citation
   metadata, then commit that identity. Build the release candidate from the
   resulting exact tag rather than reusing the provisional artifacts described
   above.
5. **Publish only the verified candidate artifacts.** TestPyPI and then PyPI
   must receive the unchanged wheel and source distribution attached to the
   reviewed GitHub release, following {doc}`../dev/releasing`.

Items 2 and 3 are the highest-value next checks. Further renaming or removal is
lower priority unless review or CI identifies a concrete ambiguity, duplicate
execution path, stale compatibility contract, or defect.

## Decision boundary

This checkpoint is sufficient to stop the broad simplification audit. It is
not sufficient to tag or publish PyAges 2.0. The next decision should be based
on the external CI and extensive-test evidence for the committed revision, not
on the discovery of more cosmetic refactoring opportunities.
