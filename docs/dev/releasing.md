# Releasing PyAge

Releases are built from a clean, reviewed commit. Generated scientific output
is not mixed with source changes unless it is an intentional golden fixture or
published reference artifact.

## Release gate

1. Stop or finish processes that write inside the checkout.
2. Confirm that every modified, deleted, and untracked file is intentional.
   Install the qualified direct dependency set with
   `python -m pip install -c install/constraints.txt -e ".[dev,docs,examples]"`.
   Run `python -m scripts.check_project_metadata` to verify the qualified pip
   and Conda versions and the release identity files.
3. Update `pyage/_version.py`, `CITATION.cff`, `CHANGELOG.md`, and the
   development-status classifier together. Confirm that README and Sphinx show
   the same release and follow {doc}`versioning-citation`; the manuscript label
   “PyAge v1.0” is not a substitute for a released `1.0.0` tag.
4. Run the standard suite:

   ```bash
   python -m ruff check .
   python -m ruff format --check .
   python -m pytest -q
   python -m pytest -q validation/tracerlpm/benchmark/tests
   python -m pytest -q --cov=pyage --cov-report=term-missing --cov-fail-under=60
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
   python -m scripts.clean_release_artifacts
   python -m build
   python -m twine check dist/*
   python -m zipfile -l dist/*.whl
   ```

   Confirm that `dist/` contains exactly one wheel and one source archive and
   that both filenames carry the intended release version.

8. Install the wheel in a new virtual environment and, from outside the
   checkout, run:

   ```bash
   pyage --version
   pyage check
   pyage list lpms
   pyage list tracers
   PYAGE_RESULTS_DIR=/tmp/pyage-smoke pyage run /path/to/checkout/examples/templates/quickstart_single.yaml
   ```

   Confirm that the smoke result contains `result_manifest.json` with schema
   version 1.

9. Create an annotated, `v`-prefixed tag on the exact reviewed commit. Push the
   tag only after the protected `main` checks and extensive suite pass.
10. Dispatch the read-only GitHub Actions **Release candidate** workflow for
    that tag. Download its `release-distributions-<tag>` artifact and verify its
    digest locally. The workflow validates one build on every supported Python
    version but cannot modify repository contents or publish packages.
11. Publish that unchanged wheel and source archive to the staging package
    index using a maintainer-controlled release process. After validation,
    promote the exact same files to the final index and attach them to a GitHub
    Release; do not rebuild between destinations.
12. For an archived scientific release, mint the version DOI from that exact
    tagged artifact. Only after the DOI resolves and its metadata has been
    checked, add it to `CITATION.cff`, validate the CFF, and update the article
    citation and reproducibility manifests. Never publish a placeholder DOI.

The GitHub Actions workflows implement the standard checks and retain
candidate artifacts temporarily. They have read-only repository permissions;
publishing, release creation, tag creation, and deletion remain deliberate
maintainer actions. Actions artifacts are not the permanent scientific
archive.
