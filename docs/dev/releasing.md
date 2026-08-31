# Releasing PyAges

Releases are built from a clean, reviewed commit. Generated scientific output
is not mixed with source changes unless it is an intentional golden fixture or
published reference artifact.

The test scopes and GitHub jobs referenced below are defined in
{doc}`testing` and {doc}`ci`.

## Release gate

1. Stop or finish processes that write inside the checkout.
2. Confirm that every modified, deleted, and untracked file is intentional.
   Install the qualified direct dependency set with
   `python -m pip install -c install/constraints.txt -e ".[dev,docs,examples]"`.
   Run `python -m scripts.maintenance.check_project_metadata` to verify that the qualified
   pip and Conda pins satisfy the declared compatibility ranges and that the
   release identity files agree. The article-reproduction environment is
   stricter: its direct versions must match `install/environment.yml` exactly.
3. Update `pyages/_version.py`, `CITATION.cff`, `CHANGELOG.md`, and the
   development-status classifier together. Confirm that README and Sphinx show
   the same release and follow {doc}`versioning-citation`. The tag must equal
   the package version exactly, without a `v` prefix; the historical article
   release uses `1.0` and maintenance releases use their patch version.
4. Run the standard suite:

   ```bash
   python -m ruff check .
   python -m ruff format --check .
   python -m scripts.maintenance.check_qualified_docstrings
   python -m pytest -q
   python -m pytest -q validation/tracerlpm/benchmark/tests
   python -m pytest -q --cov=pyages --cov-branch --cov-report=term-missing --cov-fail-under=75
   python -m sphinx -W --keep-going -b html docs docs/_build/html
   python -m sphinx -E -a -W --keep-going -b linkcheck docs docs/_build/linkcheck
   ```

   The link checker may encounter publisher bot protection. Any exclusion must
   target one verified URL exactly; do not ignore an entire DOI or publisher
   domain.

5. Run the extensive scientific suite before a public release:

   ```bash
   python -m pytest -q --run-extensive
   ```

6. On the qualified Windows/.NET host, compile the TracerLPM adapter:

   ```powershell
   dotnet build validation/tracerlpm/src/TracerLpmRunner/TracerLpmRunner.csproj -c Release -p:Platform=x64
   ```

   This checks the adapter itself; Excel/XLL integration remains a separate,
   machine-specific qualification because it requires Microsoft Excel and the
   authorized TracerLPM installation.

7. Build and validate both distribution formats:

   ```bash
   python -m scripts.maintenance.clean_release_artifacts
   python -m build
   python -m twine check dist/*
   python -m zipfile -l dist/*.whl
   ```

   The default cleanup preserves test caches, documentation builds, coverage
   files, local editor settings, and scientific results. Maintainers may use
   `python -m scripts.maintenance.clean_release_artifacts --include-caches` for a deeper
   reproducible-artifact cleanup, including nested project `__pycache__`
   directories and TracerLPM `bin/`/`obj/` outputs. This option still never
   removes `results/`, `.claude/`, or `.vscode/`.

   Confirm that `dist/` contains exactly one wheel and one source archive and
   that both filenames carry the intended release version.

8. Install the wheel in a new virtual environment and, from outside the
   checkout, run:

   ```bash
   pyages --version
   pyages check
   pyages list lpms
   pyages list tracers
   PYAGES_RESULTS_DIR=/tmp/pyages-smoke pyages run /path/to/checkout/examples/templates/quickstart_single.yaml
   ```

   Confirm that the smoke result contains `result_manifest.json` with schema
   version 2.

9. Create an annotated tag equal to the package version on the exact reviewed
   commit. For the historical `1.0` tag, verify its local and remote commit
   explicitly because an earlier tag with that name was deleted. Push any tag
   only after the protected `main` checks and extensive suite pass, and never
   move it afterward.
10. Dispatch the read-only GitHub Actions **Release candidate** workflow for
    that tag. Download its `release-distributions-<tag>` artifact and verify its
    digest locally. The workflow validates one build on every supported Python
    version but cannot modify repository contents or publish packages.
11. Attach the validated wheel and source archive to a GitHub Release. Dispatch
    the **Publish package** workflow for that exact tag and select `testpypi`.
    The workflow downloads those existing release assets, verifies their
    metadata and GitHub-recorded SHA-256 digests, and publishes them unchanged.
    After installation and smoke validation from TestPyPI, dispatch the same
    workflow with `pypi` and approve its protected environment. Never rebuild
    between destinations.
12. For an archived scientific release, mint the version DOI from that exact
    tagged artifact. Only after the DOI resolves and its metadata has been
    checked, add it to `CITATION.cff`, validate the CFF, and update the article
    citation and reproducibility manifests. Never publish a placeholder DOI.

## Archive a multi-chain qualification

`scripts.qualification.build_ci_multichain_archive` packages the four canonical
multi-chain qualifications independently of the historical article/tag-1.0
archive machinery. It rejects a missing, duplicate, invalid, or additional
qualified case. The lower-level `build_multichain_archive` command remains
available for explicitly non-canonical review bundles. Every supplied result
tree must have a complete
`result_manifest.json` whose artifact inventory matches byte for byte. Each MH
directory must record `qualification_status=qualified`, qualified pooling, at
least two retained chain tables, and multi-chain provenance. A supplied YAML
must match every configuration digest recorded by the result manifests.

After running the extensive suite with an explicit `--basetemp` and building
the wheel and sdist, build a review archive. Draft is the wrapper default:

```bash
python -m scripts.qualification.build_ci_multichain_archive \
  --basetemp .artifacts/extensive-pytest \
  --dist-dir dist \
  --mode draft \
  --output /path/to/pyages-multichain-qualification-draft.zip
```

A draft is always marked **not publishable** in its README and manifest. It
records the Git commit, tags, dirty status, tracked binary diff, and untracked
file inventory. The embedded Git archive contains committed `HEAD`; untracked
source is listed but cannot be reconstructed unless it was also supplied as an
explicit YAML, test, report, or environment file.

After the release commit is clean and carries the annotated tag exactly equal
to the PyAges version, rerun the four extensive qualifications from that tag,
rebuild the distributions, then build the publishable archive with:

```bash
python -m scripts.qualification.build_ci_multichain_archive \
  --basetemp .artifacts/extensive-pytest \
  --dist-dir dist \
  --mode publishable \
  --expected-tag <version> \
  --output /path/to/pyages-<version>-multichain-qualification.zip
```

The publishable output path must be outside the source repository. Publishable
mode checks the Git state both before assembly and immediately before sealing.
It refuses a dirty worktree, missing or lightweight tag, a tag different from
the runtime version, any result not produced from that exact clean HEAD,
mismatched result versions, or wheel/sdist metadata for another build. The
archive contains the four qualified result trees,
protocol YAML and executable tests, reports, exact wheel and sdist, a Git source
archive, runtime metadata, normalized `pip freeze`, a complete file inventory,
and `CHECKSUMS.sha256`. ZIP member order, timestamps, permissions, JSON ordering,
and compression are fixed so identical inputs on the same qualified environment
produce identical bytes. The adjacent `.zip.sha256` sidecar checks the complete
container's integrity; it is not an origin signature.

Verify both the sidecar and every nested evidence layer before transfer or
deposit:

```bash
python -m scripts.qualification.build_multichain_archive verify \
  /path/to/pyages-<version>-multichain-qualification.zip
```

Verification rejects unsafe POSIX or Windows paths, symlinks, missing or
additional members, altered hashes, non-qualified result metadata, and result
artifacts that no longer match their original terminal manifests. Keep the ZIP
and its sidecar together. This generic qualification archive does not replace the
article reproduction archive or its DOI-specific bundle.

## Trusted Publishing setup

PyPI and TestPyPI use separate accounts and publisher registries. Before the
first publication, add a pending Trusted Publisher on each index with the
following exact identity:

| Field | PyPI | TestPyPI |
|---|---|---|
| PyPI project name | `pyages` | `pyages` |
| GitHub owner | `dreuzy` | `dreuzy` |
| GitHub repository | `PyAges` | `PyAges` |
| Workflow filename | `publish-package.yml` | `publish-package.yml` |
| GitHub environment | `pypi` | `testpypi` |

Create the publishers at
<https://pypi.org/manage/account/publishing/> and
<https://test.pypi.org/manage/account/publishing/>. The GitHub environments
must accept deployments from the protected default branch only. The `pypi`
environment must require maintainer approval; `testpypi` may run without an
approval gate. Do not create or store an API token for this workflow.

Dispatch the workflow from `main` with the exact release tag, first to
TestPyPI and then to PyPI. Verify the installed TestPyPI package and compare
the hashes reported by both runs before approving PyPI. Package-index versions
are immutable, so a failed or incorrect upload cannot be replaced under the
same version.

The validation workflows retain read-only repository permissions. Only the
two isolated package publishing jobs can request short-lived OpenID Connect
identity tokens, and neither receives repository write permission. Release
creation, tag creation, and deletion remain deliberate maintainer actions.
Actions artifacts are not the permanent scientific archive.
