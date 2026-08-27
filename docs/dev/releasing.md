# Releasing PyAges

Releases are built from a clean, reviewed commit. Generated scientific output
is not mixed with source changes unless it is an intentional golden fixture or
published reference artifact.

## Release gate

1. Stop or finish processes that write inside the checkout.
2. Confirm that every modified, deleted, and untracked file is intentional.
   Install the qualified direct dependency set with
   `python -m pip install -c install/constraints.txt -e ".[dev,docs,examples]"`.
3. Update `pyages/_version.py`, `CITATION.cff`, `CHANGELOG.md`, and the
   development-status classifier together. Confirm that README and Sphinx show
   the same release and follow {doc}`versioning-citation`; the manuscript label
   “PyAges v1.0” is not a substitute for a released `v1.0.0` tag.
4. Run the standard suite:

   ```bash
   python -m ruff check .
   python -m ruff format --check .
   python -m pytest -q
   python -m pytest -q validation/tracerlpm/benchmark/tests
   python -m pytest -q --cov=pyages --cov-report=term-missing --cov-fail-under=60
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
   pyages --version
   pyages check
   pyages list lpms
   pyages list tracers
   PYAGES_RESULTS_DIR=/tmp/pyages-smoke pyages run /path/to/checkout/examples/templates/quickstart_single.yaml
   ```

   Confirm that the smoke result contains `result_manifest.json` with schema
   version 1.

9. Publish a release candidate to the staging package index. Validate it on at
   least two supported Python versions before publishing the final artifact.
10. Tag the exact reviewed commit and publish the wheel and source distribution
    without rebuilding them.
11. For an archived scientific release, mint the version DOI from that exact
    tagged artifact. Only after the DOI resolves and its metadata has been
    checked, add it to `CITATION.cff`, validate the CFF, and update the article
    citation and reproducibility manifests. Never publish a placeholder DOI.

The GitHub Actions workflows implement the standard checks and retain the
built artifacts. Uploading remains a deliberate maintainer action.
