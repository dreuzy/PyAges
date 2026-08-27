# Testing

PyAge separates fast software checks, scientific regression tests,
cross-software validation, and release smoke tests. No single number describes
all of these layers. The generated {doc}`test-inventory` is the current
collection summary; pytest collection remains the authoritative detailed
list.

## Test scopes

| Scope | Command | When to run |
|---|---|---|
| Standard suite | `python run_tests.py standard` | Every pull request and local code change |
| Detailed standard suite | `python run_tests.py standard detail` | Diagnosing a failure or reviewing parametrized cases |
| Extensive suite | `python run_tests.py extensive` | Scientific changes, golden changes, nightly qualification, and releases |
| Coverage | `python run_tests.py coverage` | Changes that add behavior or alter tested paths |
| TracerLPM validation | `python run_tests.py validation` | Changes to LPM mappings, tracer observations, comparison logic, or the adapter |
| Test collection | `python run_tests.py collect` | Inspecting the exact standard-suite node IDs without executing them |
| Golden update | `python run_tests.py standard update` | Only after independently justifying an intentional numerical-contract change |

The direct pytest equivalents used by GitHub Actions are:

```bash
python -m pytest -q
python -m pytest -q --run-extensive
python -m pytest -q --cov=pyage --cov-report=term-missing --cov-report=xml --cov-fail-under=60
python -m pytest -q validation/tracerlpm/benchmark/tests
python -m pytest --collect-only -q tests
```

`python run_tests.py` without a mode remains a backward-compatible alias for
`python run_tests.py standard`. The standard suite collects extensive tests
but skips them unless `--run-extensive` is present. It is therefore not the
complete scientific qualification by itself.

## Test families

| Area | Primary location | Contract covered |
|---|---|---|
| Calibration and inference | `tests/calibration/` | Objectives, priors, proposals, parameter grids, public calibration interfaces |
| LPMs | `tests/lpm/` | Analytical distributions, moments, mixtures, parameter files, generated values |
| Tracers and convolution | `tests/tracer/`, `tests/convolution/`, `tests/concentrations/` | Decay, chronology, convolution identities, concentration handling |
| Configuration and CLI | `tests/config/`, `tests/cli/`, root test modules | Configuration validation, paths, manifests, public API, command behavior |
| Workflows and examples | `tests/workflows/`, `tests/examples/` | Installed workflows, examples, reproducibility helpers, golden outputs |
| Field cases | `tests/ploemeur/` | Preparation, configuration, convolution references, temporal and full-workflow regressions |
| Scientific scripts | `tests/scripts/` | Article campaigns, qualification scripts, and reproduction orchestration |
| Cross-software validation | `validation/tracerlpm/benchmark/tests/` | PyAge/TracerLPM mappings, inputs, observations, pilots, references, and summaries |

See {doc}`../science/validation` for what each scientific qualification layer
does and does not establish. Repository-only research entry points are listed
in `scripts/README.md`; they are not automatically tests merely because they
produce scientific output.

## Discovering the exact tests

Use pytest rather than a manually maintained list of hundreds of parametrized
node IDs:

```bash
python run_tests.py collect
python -m pytest --collect-only -q -m extensive tests
python -m pytest --collect-only -q validation/tracerlpm/benchmark/tests
```

The repository keeps a generated summary in {doc}`test-inventory`. Regenerate
it after adding, deleting, moving, parametrizing, or re-marking tests:

```bash
python -m scripts.generate_test_inventory
```

CI verifies the committed summary without rewriting it:

```bash
python -m scripts.generate_test_inventory --check
```

## Golden files

Golden tests detect a change relative to an accepted output; they do not prove
that either the old or new value is scientifically correct. Never update a
golden file only to make CI green.

Before using `update`:

1. identify the equation, input, tolerance, seed, or public contract that
   intentionally changed;
2. compare against an analytical invariant, independent calculation,
   cross-software result, or reviewed scientific expectation;
3. run the affected test without updating and inspect the difference;
4. regenerate only the relevant reference values;
5. document the justification and numerical effect in the pull request;
6. run the standard and extensive scopes applicable to the change.

Small golden fixtures live under `tests/golden/` or beside their field/example
test support. Large scientific results belong in the qualified archive and
must be referenced by immutable manifests rather than copied into the test
tree.

## Writing and selecting tests

- Put reusable package behavior under the closest `tests/<area>/` directory.
- Mark genuinely slow scientific cases with `@pytest.mark.extensive`; do not
  use the marker to hide an unstable test.
- Keep tests deterministic by fixing seeds and documenting tolerances.
- Prefer analytical or independently prepared expectations over copying the
  implementation result.
- Exercise public behavior through installed interfaces when packaging or CLI
  behavior matters.
- Add or update documentation when a test establishes a user-visible or
  scientific contract.

The Excel/XLL integration is not exercised by the Linux CI runner. CI compiles
the .NET adapter and validates the Python-side benchmark infrastructure; full
Excel integration requires the qualified Windows host described in
{doc}`releasing`.
