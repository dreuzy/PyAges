# Citing PyAges

For software functionality, cite the exact PyAges release used. The stable
software identity is `1.0`:

> de Dreuzy, Jean-Raynald (2026). *PyAges: Groundwater Age Dating Toolkit*,
> version 1.0. CeCILL 2.1. https://github.com/dreuzy/PyAges

The machine-readable citation is `CITATION.cff` at the repository root. It is
kept synchronized with the package version and changelog by automated tests.

The released source is the reviewed commit identified by tag `1.0`.
`CITATION.cff` intentionally does not anticipate a software DOI. When the
Zenodo record is published, use the DOI shown by its verified landing page; a
later metadata update may add it to the source citation only after the DOI
identifies this same immutable release.

## Citing calculations from an unreleased commit

For results generated from `main` or from a manuscript campaign, report both:

1. the PyAges version or prepared version identity that provides the
   functionality; and
2. the exact Git commit and environment recorded in `result_manifest.json` or
   the article case manifest.

A mutable branch name such as `main` is not sufficient to identify a
scientific calculation. See {doc}`../science/reproducibility` for the evidence
archive and {doc}`../dev/versioning-citation` for the release/DOI procedure.
