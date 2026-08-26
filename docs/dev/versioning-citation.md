# Version, manuscript, citation, and DOI identity

PyAge currently has two different identifiers that must not be conflated:

- ``0.1.0b1`` is the released beta software version. It is the value in
  ``pyage/_version.py``, package metadata, CLI output, documentation, README,
  changelog, and ``CITATION.cff``.
- “PyAge v1.0” in the article layer is the **target manuscript/reproducibility
  package name** for the future stable release. It is not evidence that
  ``1.0.0`` has been released.

The article manifests deliberately store ``requested_v1.0_tag: null`` until an
exact reviewed ``v1.0.0`` tag exists. While that value is null, results must be
cited by their recorded Git commit and environment, not as software release
``1.0.0``.

## DOI rule

No placeholder or anticipated DOI belongs in ``CITATION.cff``. A DOI is added
only after the repository release/archive has minted it and the landing-page
metadata has been checked. The DOI must resolve to the same immutable source
artifact, version, authorship, license, and release date named by the citation
file. If the manuscript itself has a separate DOI, record it as the article
citation rather than as the software identifier.

For the future stable archive:

1. qualify and tag the exact source commit as ``v1.0.0``;
2. build release artifacts once from that commit and publish those unchanged
   artifacts;
3. create the immutable software archive and obtain its version DOI;
4. update ``CITATION.cff`` to ``version: 1.0.0`` with ``date-released`` and the
   minted software DOI, then validate the CFF;
5. replace each manifest's null requested tag with the exact tag/commit only
   after verifying its recorded inputs and outputs against that source;
6. cite the version DOI in the manuscript and retain any concept DOI only as a
   general project identifier.

Until those steps are complete, the scientifically precise citation is the
``0.1.0b1`` software release for released functionality plus the manifest Git
commit for manuscript calculations.
