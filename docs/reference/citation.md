# Citing PyAge

For software functionality, cite the exact PyAge release used. The current
software identity is `0.1.0b1`:

> de Dreuzy, Jean-Raynald (2026). *PyAge: Groundwater Age Dating Toolkit*,
> version 0.1.0b1. CeCILL 2.1. https://github.com/dreuzy/pyage

The machine-readable citation is `CITATION.cff` at the repository root. It is
kept synchronized with the package version and changelog by automated tests.

No software DOI has been minted yet. Do not invent or anticipate one. When a
DOI is available, the citation file, release tag, archive metadata, and this
page must be updated together.

## Citing calculations from an unreleased commit

For results generated from `main` or from a manuscript campaign, report both:

1. the released PyAge version that provides the supported functionality; and
2. the exact Git commit and environment recorded in `result_manifest.json` or
   the article case manifest.

A mutable branch name such as `main` is not sufficient to identify a
scientific calculation. See {doc}`../science/reproducibility` for the evidence
archive and {doc}`../dev/versioning-citation` for the release/DOI procedure.
