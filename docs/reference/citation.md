# Citing PyAges

For software functionality, cite the exact PyAges release used. The current
maintenance release is `1.0.1`; its machine-readable citation is
`CITATION.cff` at the repository root and is kept synchronized with the
package version and changelog by automated tests.

The immutable software and reproducibility archive associated with the
article campaign is version `1.0`:

> de Dreuzy, Jean-Raynald (2026). *PyAges: Groundwater Age Dating Toolkit*,
> version 1.0. Zenodo. https://doi.org/10.5281/zenodo.22150863

The version-specific DOI is
[`10.5281/zenodo.22150863`](https://doi.org/10.5281/zenodo.22150863); the
concept DOI for all versions is
[`10.5281/zenodo.22150862`](https://doi.org/10.5281/zenodo.22150862). Prefer
the version-specific DOI when citing the archived article calculations. The
archived source is the reviewed commit identified by tag `1.0`.

The Zenodo DOI is not added to `CITATION.cff` because that file now describes
maintenance release `1.0.1`, while the published Zenodo record identifies the
immutable `1.0` archive. A future Zenodo archive of `1.0.1` may be added only
with its own version-specific DOI.

## Citing calculations from an unreleased commit

For results generated from `main` or from a manuscript campaign, report both:

1. the PyAges version or prepared version identity that provides the
   functionality; and
2. the exact Git commit and environment recorded in `result_manifest.json` or
   the article case manifest.

A mutable branch name such as `main` is not sufficient to identify a
scientific calculation. See {doc}`../science/reproducibility` for the evidence
archive and {doc}`../dev/versioning-citation` for the release/DOI procedure.
