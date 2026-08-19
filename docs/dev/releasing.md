# Releasing PyAge

Releases are built from a clean, reviewed commit. Generated scientific output
is not mixed with source changes unless it is an intentional golden fixture or
published reference artifact.

## Release gate

1. Stop or finish processes that write inside the checkout.
2. Confirm that every modified, deleted, and untracked file is intentional.
3. Update `pyage/_version.py`, `CITATION.cff`, `CHANGELOG.md`, and the
   development-status classifier together.
4. Run the standard suite:

   ```bash
   python -m ruff check .
   python -m pytest -q
   python -m sphinx -W --keep-going -b html docs docs/_build/html
   ```

5. Run the extensive scientific suite before a public release:

   ```bash
   python -m pytest -q --run-extensive
   ```

6. Build and validate both distribution formats:

   ```bash
   python -m build
   python -m twine check dist/*
   python -m zipfile -l dist/*.whl
   ```

7. Install the wheel in a new virtual environment and, from outside the
   checkout, run:

   ```bash
   pyage --version
   pyage check
   pyage list lpms
   pyage list tracers
   ```

8. Publish a release candidate to the staging package index. Validate it on at
   least two supported Python versions before publishing the final artifact.
9. Tag the exact reviewed commit and publish the wheel and source distribution
   without rebuilding them.

The GitLab pipeline implements the standard checks and retains the built
artifacts. Uploading remains a deliberate maintainer action.
