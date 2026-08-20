# Releasing PyAge

Releases are built from a clean, reviewed commit. Generated scientific output
is not mixed with source changes unless it is an intentional golden fixture or
published reference artifact.

## Release gate

1. Stop or finish processes that write inside the checkout.
2. Confirm that every modified, deleted, and untracked file is intentional.
   Install the qualified direct dependency set with
   `python -m pip install -c install/constraints.txt -e ".[dev,docs,examples]"`.
3. Update `pyage/_version.py`, `CITATION.cff`, `CHANGELOG.md`, and the
   development-status classifier together.
4. Run the standard suite:

   ```bash
   python -m ruff check .
   python -m ruff format --check .
   python -m pytest -q
   python -m pytest -q validation/tracerlpm/benchmark/tests
   python -m pytest -q --cov=pyage --cov-report=term-missing --cov-fail-under=60
   python -m sphinx -W --keep-going -b html docs docs/_build/html
   ```

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

9. Publish a release candidate to the staging package index. Validate it on at
   least two supported Python versions before publishing the final artifact.
10. Tag the exact reviewed commit and publish the wheel and source distribution
   without rebuilding them.

The GitLab pipeline implements the standard checks and retains the built
artifacts. Uploading remains a deliberate maintainer action.
