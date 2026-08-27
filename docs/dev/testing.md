# Testing

PyAges separates fast software checks, scientific regression tests,
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
| pandas compatibility | CI `pandas-compatibility` job | Changes to tables, data types, indexing, assignment, or serialization |
| TracerLPM validation | `python run_tests.py validation` | Changes to LPM mappings, tracer observations, comparison logic, or the adapter |
| Test collection | `python run_tests.py collect` | Inspecting the exact standard-suite node IDs without executing them |
| Golden update | `python run_tests.py standard update` | Only after independently justifying an intentional numerical-contract change |

The direct pytest equivalents used by GitHub Actions are:

```bash
python -m pytest -q
python -m pytest -q --run-extensive
python -m pytest -q --cov=pyages --cov-branch --cov-report=term-missing --cov-report=xml --cov-fail-under=75
python -m pytest -q validation/tracerlpm/benchmark/tests
python -m pytest --collect-only -q tests
```

The pandas compatibility job runs the standard suite on the supported 2.2.3
lower bound with `FutureWarning` promoted to errors. It then repeats the suite
with future string inference and Copy-on-Write diagnostics enabled. The normal
Python matrix and coverage job exercise the qualified pandas 3 version from
`install/constraints.txt`.

`python run_tests.py` without a mode remains a backward-compatible alias for
`python run_tests.py standard`. The standard suite collects extensive tests
but skips them unless `--run-extensive` is present. It is therefore not the
complete scientific qualification by itself.

## Traceability matrix

This matrix explains why each family exists and how it contributes evidence.
It complements the generated module-by-module {doc}`test-inventory`.

| Qualification area | Contract and purpose | Test locations | Scope and CI | Evidence or reference | Important limit |
|---|---|---|---|---|---|
| Repository and public API | Protect metadata, manifests, documented imports, paths, cleanup, and repository-wide contracts | Root `tests/test_*.py` modules | Standard suite; package and documentation jobs add non-pytest evidence | {doc}`../reference/public-api`, package metadata, manifest schema | Passing tests do not guarantee backward compatibility for an undocumented interface |
| LPM analytical behavior | Verify distributions, normalization, moments, mixtures, parameter files, registries, and generated values | `tests/lpm/` | Standard suite | Analytical identities and accepted compact golden values | The sampled parameter combinations are not the full mathematical domain |
| Tracers and convolution | Verify decay, distributed inputs, concentration chronicles, convolution identities, settings, and tracer coupling | `tests/tracer/`, `tests/concentrations/`, `tests/convolution/` | Standard suite | Analytical invariants and independent high-accuracy calculations described in {doc}`../science/validation` | Numerical agreement is tolerance- and grid-dependent |
| Calibration and inference | Protect objectives, priors, proposals, parameter grids, initialization, diagnostics, and public calibration APIs | `tests/calibration/` | Standard suite; selected cases require `--run-extensive` | Synthetic cases, proposal qualification, posterior and support contracts | Solver convergence does not establish hydrogeological realism or identifiability for every dataset |
| Installed interfaces and workflows | Exercise validated configuration, CLI behavior, plotting runtime, installed single-date execution, and wheel use outside the checkout | `tests/config/`, `tests/cli/`, `tests/workflows/`; package smoke test | Standard suite plus Conda and package CI jobs | CLI contract, quickstart configuration, result-manifest schema | The Linux runner does not cover every operating system or interactive backend |
| Examples and field cases | Detect changes in runnable examples, Holten, Fontainebleau, and Ploemeur preparation and outputs | `tests/examples/`, `tests/ploemeur/` | Standard suite; selected Ploemeur cases are extensive | Reviewed golden fixtures, published or internally consistent case data, {doc}`../science/case-studies` | A golden match detects stability, not independent scientific correctness |
| Reproducibility orchestration | Verify article registries, campaign preparation, qualification helpers, paths, and resumable execution contracts | `tests/scripts/` | Standard suite; complete campaigns run through documented reproduction commands | {doc}`../science/reproducibility`, case manifests, checksums, and expected artifacts | Unit tests cannot replace absent raw chains, external archives, or independent review |
| TracerLPM cross-software validation | Verify parameter mappings, inputs, observations, reference outputs, pilots, comparisons, and robustness summaries | `validation/tracerlpm/benchmark/tests/` | Dedicated `TracerLPM validation` CI job; .NET build is separate | Benchmark README, reference fixtures, mapped synthetic cases | CI does not run the proprietary Excel/XLL integration or rank optimizer quality |

See {doc}`../science/validation` for what each scientific qualification layer
does and does not establish. Repository-only research entry points are listed
in `scripts/README.md`; they are not automatically tests merely because they
produce scientific output.

## Description levels

Test intent is documented at four complementary levels:

1. this page records the family-level purpose, evidence, execution scope, and
   limitations;
2. {doc}`test-inventory` records every collected module, its generated short
   purpose, type, case count, and extensive-case count;
3. `python run_tests.py collect` exposes every parametrized pytest node ID;
4. test names, parametrization IDs, docstrings, fixtures, and assertions remain
   the authoritative description of an individual case.

Descriptions are intentionally not copied into a manually maintained list of
hundreds of node IDs. That list would drift as parametrization changes. The
inventory generator fails when a new test area has no declared contract, and
CI fails when the generated inventory is stale.

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
