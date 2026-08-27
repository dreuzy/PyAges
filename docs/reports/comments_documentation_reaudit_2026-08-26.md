# Re-audit of code comments and documentation

> **Current-state notice (27 August 2026).** This report is retained as a
> dated audit trail. Its statements that the fresh numerical campaign,
> editorial package, and archive are absent have been superseded. See
> {doc}`reproduction_campaign_status_2026-08-27` for the current two-layer
> status: historical evidence remains unavailable locally (0/6), while the
> fresh core campaign validates 8/8 stages.

**Date:** 26 August 2026  
**Base commit:** `04e6ebaa4b7a67154bbb4532e112e543563790ad`  
**Scope:** versioned Python code and documentation; the untracked
`submission_candidate/` directory was excluded.

During final validation, concurrent work appeared outside the audit, including
`.github/workflows/ci.yml`, `scripts/_runtime_probe.py`,
`scripts/run_ploemeur_targeted_ig_reproduction.py`,
`sites/ploemeur/workflows/ploemeur_workflow.py`,
`tests/ploemeur/test_ploemeur_workflow.py`, and
`tests/scripts/test_article_support.py`. Those changes were preserved and
excluded from this audit.

## Executive conclusion

The documentation builds cleanly and its CLI, LPM, and tracer inventories are
consistent with the runtime. The re-audit nevertheless found semantic drift
that structural Sphinx checks could not detect: incomplete LPM extension
examples, incorrect temporal required-field labels, an overly specific result
layout, overstated environment provenance, stale docstring types, and several
unresolved maintainer notes.

The locally correctable findings have been addressed in the working tree. The
remaining blockers are external scientific evidence, not prose or source-code
comments.

## Corrections made

| Area | Correction |
| --- | --- |
| LPM generator | Standardized generated modules on `pyages/lpm/models/<name>.py`, generated a conventional `<Name>Lpm` class, and made the final verification instruction portable. |
| LPM extension guide | Added complete Weibull and log-normal partial-first-moment implementations required by continuous convolution and replaced deprecated `np.trapz` guidance. |
| Temporal configuration | Marked `lpm_models.list` and `lpm_models.directory` optional and documented their runtime fallbacks. |
| Result layout | Replaced the fixed `ploemeur_temporal` namespace with configurable `<study_name>` and documented method-specific subdirectories. |
| Result provenance | Replaced “exact environment” with the actual schema-2 contract: platform plus selected direct-dependency versions; constraint files remain the reproducible environment definition. |
| Code documentation | Corrected Pydantic parameter types, path-resolution rules, a `Path` return type, stale synthetic-output prose, and public package/object docstrings. |
| Internal notes | Removed unresolved `#JR` annotations and an obsolete golden-helper migration note. |
| Regression coverage | Added checks for Pydantic required fields, generator filename and syntax, public docstring presence, complete LPM-contract guidance, and configurable result-layout prose. |

## Deliberate compatibility change

`pyages new lpm <name>` now writes `<name>.py` rather than `LPM_<name>.py`.
This matches the existing model modules, the extension guide, and normal Python
module naming. The change is recorded under `Unreleased` in `CHANGELOG.md` and
is protected by a CLI regression test.

## Current article-evidence status

All six read-only `article/run_case.py check` commands still fail in this
checkout:

| Case | Current local result |
| --- | --- |
| `s3_forward_verification` | Missing Supplement S1 and historical run manifest; one runner checksum differs. |
| `s3_1_tracerlpm` | Missing Supplement S2, launch manifest, and historical run manifest; one report-builder checksum differs. |
| `s3_2_shifted_exponential` | Missing chains, pilots, and historical manifest; runner checksum differs. |
| `s4_1_holten` | Missing chains, pilots, and historical manifest; runner checksum differs. |
| `s4_2_ploemeur` | Missing chains, data-audit evidence, and historical manifest; runner checksum differs. |
| `holten_prior_dirichlet1` | Missing chains, pilots, and historical manifest; runner checksum differs. |

This confirms the broad conclusion of the earlier documentation audit, but its
case-by-case details remain historical because that report audited commit
`17b3857`, not the current base commit.

## Remaining work that cannot be created from this checkout

- Import or immutably reference the missing MCMC chains and manifests.
- Import the qualified TracerLPM/Excel outputs and Supplement S2.
- Integrate and independently review the external Dirichlet campaign package.
- Build the final article package and scientific archive from those inputs.
- Assign and document an archive DOI only after the immutable deposit exists.

Absent numerical evidence must not be replaced by reconstructed prose or by a
new checksum attached to an old result.

## Verification contract

The corrective change is accepted only if all of the following remain green:

```powershell
python -m ruff check .
python -m ruff format --check <changed-python-files>
python -m pytest -q
python -m sphinx -E -a -W --keep-going -b html docs docs/_build/html
python -m sphinx -E -a -W --keep-going -b linkcheck docs docs/_build/linkcheck
```

The public-docstring regression test covers presence, not a mechanical
pydocstyle score. Style-only rewrites should remain incremental and must not
obscure scientific changes.

## Validation results

- Ruff: all audit files passed. The whole repository passed before the
  concurrent files above appeared; it now reports an import-order finding in
  the excluded `scripts/_runtime_probe.py`.
- Formatting: all changed Python files passed `ruff format --check`.
- Targeted documentation contracts: 38 tests passed.
- Full test suite, before the concurrent files appeared: 623 tests passed and 5
  were skipped.
- Sphinx HTML build: passed with warnings treated as errors.
- Sphinx link check: passed with warnings treated as errors.
