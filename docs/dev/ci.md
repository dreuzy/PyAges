# Continuous integration

GitHub Actions is the canonical continuous-integration service for PyAges. The
workflow files remain the executable source of truth, while this page explains
their intent, triggers, outputs, and failure semantics. Validation workflows
use read-only repository permissions. Package publication is confined to two
manual, environment-protected jobs with OpenID Connect identity tokens; no
workflow modifies Git references.

## Workflow overview

| Workflow | Triggers | Purpose |
|---|---|---|
| [CI](https://github.com/dreuzy/PyAges/actions/workflows/ci.yml) | Pull requests targeting `main`, pushes to `main`, version tags matching `*.*`, and manual dispatch | Fast required checks for every supported Python version, packaging, documentation, and validation infrastructure |
| [Extensive tests](https://github.com/dreuzy/PyAges/actions/workflows/extensive-tests.yml) | Manual dispatch, every Monday at `01:17 UTC`, and pull requests changing selected calibration, LPM, workflow, configuration, data, example, test, or workflow paths | Run the opt-in scientific qualifications when their target or executable evidence can change |
| [Release candidate](https://github.com/dreuzy/PyAges/actions/workflows/release-candidate.yml) | Manual dispatch for an existing release tag matching the package version | Build one candidate, validate its metadata, smoke-test the same wheel on all supported Python versions, and require extensive scientific qualification of the tagged source |
| [Publish package](https://github.com/dreuzy/PyAges/actions/workflows/publish-package.yml) | Manual dispatch for an existing GitHub Release tag and a selected package index | Verify the existing release assets and their SHA-256 digests, then publish the unchanged files through the protected `testpypi` or `pypi` environment |

The weekly extensive run starts at 02:17 in metropolitan France during winter
time and 03:17 during summer time. GitHub may send failure notifications at
those hours. A notification identifies the workflow run, branch, commit, and
failed job; always inspect a later run on the same branch before assuming that
the default branch is still failing.

## Standard CI jobs

The standard workflow runs the following independent jobs and then a final
gate:

| Job | Main checks | Result or artifact |
|---|---|---|
| `Ruff` | `ruff check`, `ruff format --check`, progressive Pyright check, scoped qualified-surface docstring check, generated test-inventory check | Lint, formatting, selected core type contracts, API prose, and test documentation must be current |
| `Dependency audit` | Qualified install, `pip check`, `pip-audit` | Dependency consistency and known-vulnerability check |
| `Conda environment` | Create `install/environment.yml`, install PyAges without dependency replacement, exercise CLI discovery | Conda environment and packaged entry points are usable |
| `Tests (Python …)` | Standard pytest suite on Python 3.12, 3.13, and 3.14 | Supported-version compatibility |
| `Coverage` | Standard suite with branch measurement | XML artifact retained for 14 days; total coverage must be at least 75% |
| `TracerLPM validation` | Dedicated benchmark tests under `validation/tracerlpm/benchmark/tests` | Mapping, reference-data, and comparison infrastructure remains valid |
| `.NET build` | Build the TracerLPM runner with .NET 8 | The adapter compiles on the GitHub Linux runner with Windows targeting enabled |
| `Documentation` | Strict Sphinx HTML build and external-link check | HTML artifact retained for 14 days; warnings and unignored broken links fail the job |
| `Package` | Build wheel and source distribution, run `twine check`, install the wheel outside the checkout, exercise CLI and quickstart | Distribution artifact retained for 14 days |
| `CI gate` | Require every preceding job to succeed | Single required branch-protection status |

Jobs have explicit maximum durations so a stalled runner cannot consume the
full GitHub Actions default: 15 minutes for Ruff and dependency audit; 20
minutes for documentation, package, and .NET; 30 minutes for Conda, Python
tests, coverage, and TracerLPM validation; and 5 minutes for the final CI gate.

The `CI gate` does not perform an additional scientific test. It deliberately
fails when any prerequisite fails, is cancelled, or is skipped. Consequently,
a notification can report both the original failed job and `CI gate`; these
are not two independent defects.

Runs for the same workflow and Git reference are grouped. A newer standard CI
run cancels an older in-progress run for that reference. Extensive and release
candidate runs are not cancelled by a newer run.

## Extensive scientific tests

The extensive workflow installs the qualified development environment and
runs:

```bash
python -m pytest -q --run-extensive \
  --basetemp "$RUNNER_TEMP/pyages-extensive-$GITHUB_RUN_ID"
```

The CI base directory is deliberately under the runner's external temporary
root, not below the checkout. This both gives pytest an existing parent and
prevents temporary test trees from changing repository-root and provenance
semantics.

The marker is opt-in. The same tests are collected by the standard suite but
skipped unless `--run-extensive` is present. The workflow is scheduled for
early-morning capacity, can be dispatched explicitly, and runs on pull requests
whose selected paths can change the scientific target or its qualification
evidence. See {doc}`testing` for the test taxonomy and
{doc}`../science/validation` for the qualification strategy.

Those pull-request paths include Python, YAML, tabular inputs, and workbooks
under ``examples/``; the complete ``sites/ploemeur/`` study tree; the shared
MCMC, provenance, and reporting helpers; and the multichain archive facade and
its private implementation modules. A change to an executable script, a study input, or
the code that packages its evidence therefore cannot silently bypass this
workflow.

After pytest succeeds, the job builds one wheel and one sdist, then runs:

```bash
python -m scripts.qualification.build_ci_multichain_archive \
  --basetemp "$RUNNER_TEMP/pyages-extensive-$GITHUB_RUN_ID" \
  --dist-dir dist \
  --output .artifacts/multichain-qualification-draft.zip
```

The wrapper does not accept a best-effort subset. It discovers exactly the four
expected qualified terminal manifests below that pytest base directory:

- synthetic shifted-exponential recovery;
- natural Ploemeur F09 shifted-exponential qualification;
- natural Ploemeur F09 prior-active `ig_shifted` qualification;
- Ploemeur temporal shifted-exponential qualification.

For each result, the wrapper finds the YAML actually written and executed by
the extensive test, matches its SHA-256 to the configuration digest in the
terminal manifest, and rejects missing, duplicate, invalid, or additional
qualified results. It then supplies the four canonical extensive tests and
their four `docs/examples/` qualification reports, plus the freshly built wheel
and sdist, to the generic archive builder. Its default `draft` mode is used by
the scheduled workflow. The resulting ZIP is byte-inventoried, contains nested
result-manifest validation and
`CHECKSUMS.sha256`, and has an adjacent ZIP SHA-256 sidecar. Draft mode is
intentional for the scheduled untagged branch run. The same strict four-case
wrapper accepts `--mode publishable --expected-tag <version>` after all four
qualifications have been rerun from that exact clean tagged HEAD; it also
requires an output path outside the repository. See
{doc}`releasing` for that promotion boundary.

The job uses `if: always()` to upload all four executed YAML files, all four raw
result trees, the draft ZIP, and its sidecar as
`multichain-scientific-evidence-<run-id>` for 30 days. If pytest fails, raw or
partial trees remain available but the distribution and
archive steps do not run. If strict discovery or archive validation fails, the
job fails and still uploads the raw trees; an absent ZIP therefore cannot be
mistaken for complete qualification evidence. Missing upload paths produce a
warning rather than masking the original failure. This is temporary CI storage,
not a durable publication archive.

## Release candidate validation

The release candidate workflow accepts an existing protected tag. It checks
release and dependency metadata, builds the distributions once, uploads them
as a temporary artifact, and installs the same wheel on Python 3.12, 3.13, and
3.14. In parallel, Python 3.12 runs the complete opt-in extensive suite from
that exact tagged source. The final gate requires the build, every wheel smoke
test, and scientific qualification to succeed. The workflow has `contents:
read` permission only: tag creation, package publication, GitHub Release
creation, and deletion remain maintainer actions. The complete procedure is in
{doc}`releasing`.

## Package publication

The package publication workflow never builds a distribution. It checks out
the requested tag, verifies the release identity, downloads the wheel and
source archive already attached to that GitHub Release, and compares each
download with the digest recorded by GitHub. A temporary Actions artifact
transfers only those verified files to one isolated publishing job.

The `testpypi` and `pypi` jobs receive `id-token: write` only at job scope and
authenticate through Trusted Publishing. They receive no repository write
permission and use no long-lived PyPI token. The `pypi` GitHub environment
requires maintainer approval. See {doc}`releasing` for the one-time publisher
identity and the required TestPyPI-first sequence.

## Reproducing checks locally

Install the qualified contributor environment first:

```bash
python -m pip install -c install/constraints.txt -e ".[dev,docs,examples]"
```

Then use the commands in {doc}`testing`. The closest local equivalent to the
standard Python checks is:

```bash
python -m ruff check .
python -m ruff format --check .
python -m pyright
python -m scripts.maintenance.check_qualified_docstrings
python run_tests.py standard
python run_tests.py coverage
python run_tests.py validation
python -m scripts.maintenance.generate_test_inventory --check
python -m sphinx -W --keep-going -b html docs docs/_build/html
python -m sphinx -W --keep-going -b linkcheck docs docs/_build/linkcheck
```

The docstring command intentionally covers more than the installed package.
In addition to the qualified calibration and workflow API, it checks the
shared provenance, MCMC, and reporting helpers, the multichain archive
implementation, the extracted Holten/Ploemeur diagnostics, and the maintained HYP-26-0172
run/product modules.  Historical one-off scripts remain under normal Ruff
checks until their responsibilities are similarly isolated.

The CI documentation job retries the same cached linkcheck once when the first
invocation fails. This absorbs a transient remote timeout while preserving a
failure for a persistent broken link. Publisher endpoints known to reject
automated clients remain narrowly listed in `docs/conf.py`.

Conda, wheel isolation, and .NET exercise different environments and must not
be inferred solely from a successful editable-install test run.

## Maintaining the workflow contract

When a workflow job, supported Python version, trigger, schedule, command,
coverage threshold, permission, or retained artifact changes:

1. update this page in the same pull request;
2. update {doc}`testing` if test selection changes;
3. regenerate {doc}`test-inventory` when collection changes;
4. update `CONTRIBUTING.md` or {doc}`releasing` when the contributor or release
   procedure changes;
5. preserve read-only defaults unless a separately reviewed operation requires
   a narrower temporary write permission.
