# Complete SciPy-backed external LPM example

This directory is a standalone Python package. It provides `gamma_mean`, a
gamma transit-time distribution implemented by adapting `scipy.stats.gamma`.
The public parameters are the mean age and the gamma shape, while SciPy expects
a shape and scale. The example makes that short conversion explicit.

## Try the example

From this directory, run:

```console
python -m pip install -e .
pyages list lpms
pyages check lpm gamma_mean
pytest
```

The editable installation records the `pyages.lpms` entry point from
`pyproject.toml`. Listing models reads that metadata without importing the
plugin. PyAges imports `model:definition` only when `gamma_mean` is built or
checked.

## Read the files in this order

1. `pyproject.toml` declares the package, SciPy dependency, entry point, and
   YAML package data.
2. `src/pyages_lpm_gamma_mean/model.py` selects `scipy.stats.gamma`, converts
   the public parameters, and implements the convolution partial moment.
3. `src/pyages_lpm_gamma_mean/data_lpm/gamma_mean/params.yaml` defines domains,
   calibration ranges, initial values, proposal steps, and priors.
4. `tests/test_model.py` checks exact moments, a quantile round trip, and the
   partial moment required by continuous convolution.

## Understand the model step by step

The model is intentionally short, but each part has a different role:

1. `GammaMeanLpm(LpmScipy)` says that the ordinary probability operations are
   delegated to a SciPy distribution.
2. `scipy_dist = gamma` selects `scipy.stats.gamma`.
3. `__init__()` exposes two readable parameters to PyAges: mean age `mu` and
   gamma shape `shape`.
4. `_scipy_params()` converts those parameters to SciPy's notation:

   ```text
   SciPy shape = shape
   SciPy scale = mu / shape
   resulting mean = shape * scale = mu
   ```

5. `LpmScipy` uses that conversion to provide `pdf()`, `cdf()`, `cdf_inv()`,
   `mean()`, and `std()`.
6. `cdf_and_partial_first_moment()` adds the analytical quantity required by
   continuous PyAges convolution.
7. `definition = LpmDefinition(...)` tells PyAges which class and packaged
   parameter directory belong to the entry point.

## Read `params.yaml`

The Python constructor and the YAML file describe the same two public
parameters. Consider the domain of `mu`:

```yaml
domain: {min: 0.0, min_inclusive: false, max: null}
calibration_range: [0.1, 200.0]
init: 10.0
```

These three lines have distinct meanings:

- `domain` is the mathematical validity domain of the formula;
- `min: 0.0` with `min_inclusive: false` means `mu > 0`, because zero is
  excluded;
- `max: null` means that the mathematical domain has no finite upper bound;
- `calibration_range: [0.1, 200.0]` is the finite interval PyAges may explore
  during this calibration configuration;
- `init: 10.0` is the starting value and must lie inside that calibration
  range.

If `min_inclusive` were `true`, the boundary would be allowed: `mu >= 0`.
`max_inclusive` has the analogous meaning for a finite maximum. Both
inclusivity fields default to `true` when omitted.

The remaining fields are:

| Field | Purpose |
| --- | --- |
| `name` | Must match a parameter name used by the Python model |
| `label` | Short human-readable identifier |
| `unit` | Physical unit; keep it consistent with the constructor |
| `description` | Explanation for readers |
| `step` | Optional positive proposal step for model-configured sampling |
| `prior` | Optional `uniform` or `normal` prior definition |

The complete user reference is in
[`adding-lpm.md`](../../../docs/user-guide/adding-lpm.md#parameter-file-reference).
The executable validation rules are in
[`_lpm_parameter_schema.py`](../../../pyages/data_io/_lpm_parameter_schema.py),
and their focused tests are in
[`test_lpm_params.py`](../../../tests/data_io/test_lpm_params.py).

## What SciPy supplies

Inheriting from `LpmScipy` supplies `pdf()`, `cdf()`, `cdf_inv()`, `mean()`, and
`std()`. This plugin only provides:

- `scipy_dist = gamma`;
- `_scipy_params()`, which translates mean and shape to SciPy shape and scale;
- the analytical partial first moment needed by PyAges convolution.

The partial moment is not supplied by the generic SciPy adapter because its
formula is specific to each distribution.

## Understand the tests

There are two complementary commands:

```console
pyages check lpm gamma_mean
pytest
```

`pyages check lpm gamma_mean` performs general integration checks shared by
all external LPMs: entry-point loading, YAML consistency, scalar and vector
evaluation, probability invariants, moments, the convolution strategy, and
constant and affine tracer convolutions.

`pytest` runs the scientific tests owned by this plugin. Here they verify:

- the exact mean and standard deviation;
- a CDF/quantile round trip;
- the zero-age limits of the CDF and partial moment;
- convergence of the CDF to one and of the partial moment to the full mean.

Passing the general checker proves that the plugin is technically integrated.
Passing these example tests proves a few analytical identities. Neither result
alone qualifies the model for a particular scientific study; add reference
cases covering the parameter ranges and limiting regimes used in that study.

For the PyAges test suite as a whole, see
[`testing.md`](../../../docs/dev/testing.md) and the generated
[`test-inventory.md`](../../../docs/dev/test-inventory.md).

## Start a different plugin

Generate a fresh project instead of copying names by hand:

```console
pyages new lpm my_model --layout plugin --base scipy
```

Use `--base root` when no suitable `scipy.stats` law exists. Whichever base you
choose, replace the starter formulas, parameter ranges, and tests with
scientifically justified values before using the model in a study.

See `docs/user-guide/external-lpm-quickstart.md` for the shortest guided path
and `docs/user-guide/external-lpm-models.md` for the complete plugin contract.
