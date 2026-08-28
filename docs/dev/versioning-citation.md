# Version, manuscript, citation, and DOI identity

PyAges uses one release identity for the final article campaign:

- the Python package and CLI version is ``1.0``;
- the reviewed Git tag is exactly ``1.0`` (without a ``v`` prefix);
- ``CITATION.cff``, the changelog, the scientific archive, and the Zenodo
  bundle must all report ``1.0``;
- every calculation also records the immutable Git commit used for its stage.

The source tree may carry the ``1.0`` version while release preparation is in
progress. That does not by itself prove that the release exists. The release
becomes citable as ``1.0`` only when the exact clean, reviewed campaign commit
is tagged ``1.0`` and the release/archive gates pass.

The project naming contract is singular: ``pip install pyages``,
``import pyages``, and the ``pyages`` command all refer to this project. Former
PyAge names are historical only and are not public compatibility aliases.

## Reuse of the tag name

An earlier misleading ``1.0`` tag was deleted on 27 August 2026. Its former
target remains identifiable as commit
``5af69268da4ed1e22cc5307eac8d6f46522f8ade`` and is retained in the historical
article manifests as ``legacy_pre_refactor_commit``.

The release decision now assigns the exact tag ``1.0`` to the new reviewed
stable commit. Because some clones may have cached the deleted tag, the commit
hash is always recorded alongside the tag. Before running or publishing the
campaign, verify locally and remotely that ``1.0`` resolves to the same clean
commit. Never force-move the new tag after publication.

Historical case manifests keep ``release_tag: null`` and
``requested_stable_tag: null`` because they describe older calculations. They
must not be rewritten. The fresh campaign manifest and archive record the new
``1.0`` tag, version, and per-stage commits.

## DOI rule

No placeholder or anticipated DOI belongs in ``CITATION.cff``. Reserve the
Zenodo DOI before building the final reader-facing bundle and pass it through
``--doi``. Add a DOI to ``CITATION.cff`` only when it identifies the same
immutable source release and its landing metadata has been checked. If the
manuscript has a separate DOI, pass it as ``--article-doi`` and record it as an
article relationship rather than as the software identifier.

For the stable article archive:

1. qualify the exact source commit and create the annotated tag ``1.0``;
2. verify that local and remote ``1.0`` resolve to that commit;
3. run the complete campaign from the tagged, clean commit in the qualified
   article environment;
4. validate the campaign, editorial package, and core scientific archive;
5. reserve the Zenodo DOI and build the final bundle with ``--doi``;
6. review creators, affiliations, related identifiers, licences, version,
   commit, tag, file inventory, sizes, and SHA-256 digests;
7. upload the already validated ZIP without rebuilding or modifying it.

Until the tag and archive are public, cite calculations by the recorded commit
and environment and describe ``1.0`` as being prepared, not released.
