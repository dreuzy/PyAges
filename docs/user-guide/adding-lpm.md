# Adding a New LPM

This guide explains how to add a new Lumped Parameter Model (LPM) to PyAges. LPMs describe probability distributions of groundwater transit times.

Adding an LPM is a source-development workflow: the Python model must be part
of the importable `pyages.lpm.models` package. Work from the root of a writable
source checkout and install it in editable mode while developing the model.
An arbitrary directory passed with `--output` is not scanned automatically;
the generated module must still be integrated into `pyages/lpm/models/` before
the registry can discover it.

## Choose the implementation path

PyAges separates the model's **scientific parameterization** from the generic
statistical operations. Choose the path from the probability measure, not from
the amount of code you expect to write.

### Distribution already available in SciPy

Inherit from `LpmScipy` and select a `scipy.stats` distribution. For the usual
statistical interface, the model-specific code is limited to:

1. declaring `scipy_dist`;
2. declaring the physical PyAges parameters and their units in `__init__()`;
3. translating those parameters to SciPy's `(shape_args, loc, scale)` convention
   in `_scipy_params()`.

`LpmScipy` then provides `pdf()`, `cdf()`, `cdf_inv()`, `mean()`, and `std()`.
Do not reimplement those methods in each model. For example, PyAges exposes the
inverse Gaussian through a mean and standard deviation in years; only
`_scipy_params()` converts those physical quantities to SciPy's dimensionless
shape and dimensional scale.

There is one additional requirement for a model used by the continuous
convolution engine: the concrete model must provide the vectorized analytical
primitive `cdf_and_partial_first_moment(t)`. It returns both `F(t)` and
`E[T 1(T <= t)]`. SciPy supplies the ordinary distribution functions, but it
does not supply this PyAges-specific convolution contract in the required
vectorized form. PyAges deliberately does not reconstruct it from sampled PDF
values.

Distribution-specific numerical workarounds remain private to the affected
model family. For example, the built-in inverse-Gaussian models share a private
quantile fallback because SciPy's inverse-Gaussian PPF can return a non-finite
value in extreme cases. New SciPy-backed models should still inherit from
`LpmScipy`; override one of its methods only when a demonstrated, tested issue
is specific to that distribution.

### Distribution requiring a specific mechanism

Inherit directly from `LpmBase` when the probability measure cannot be
represented faithfully by one continuous SciPy distribution. This includes:

- exact point masses (`DIRAC` and `DIRAC_DOUBLE`);
- mixed discrete/continuous measures (`MIXED_DIRAC_CONTINUOUS`);
- custom continuous laws such as the configurable shape-free model.

The model must then implement its probability functions and moments and select
the appropriate `ConvolutionStrategy`. A custom continuous model must also
implement `cdf_and_partial_first_moment(t)` under the exact contract described
below. See {doc}`convolution` for direct forward calculations and diagnostics.

### What is implemented where

| Location | Responsibility |
| --- | --- |
| `pyages/lpm/core/lpm_scipy.py` | Generic SciPy delegation for PDF, CDF, quantiles, mean, and standard deviation |
| `pyages/lpm/models/<name>.py` | Scientific parameterization, SciPy parameter conversion, and any distribution-specific convolution formula |
| `data_core/data_lpm/<name>/params.yaml` | Calibration bounds, initial values, proposal steps, priors, labels, units, and descriptions |
| `pyages/lpm/core/convolution_strategy.py` | Declaration of the convolution mechanism required by the probability measure |
| `pyages/convolution/` | Generic execution of the declared continuous, Dirac, double-Dirac, or mixed convolution mechanism |
| `pyages/lpm/core/registry.py` | Discovery of model classes decorated with `@register_lpm` |

The existing SciPy-backed models are `exp`, `exp_shifted`, `gamma`, `uniform`,
`weibull`, `ig`, and `ig_shifted`. The Dirac variants, the mixed
Dirac/exponential model, and the shape-free model use specific `LpmBase`
implementations.

## Quick Method: Use the Template Generator

The easiest way to create a new LPM is with the template generator (CLI):

```bash
pyages new lpm <name> [--base scipy|root] [-o <output_dir>]
```

Run this command from the root of the source checkout. `--output` changes only
the destination of the Python model file. The parameter file is always created
under `data_core/data_lpm/<name>/` relative to the current working directory.

Example for a Weibull distribution:

```bash
pyages new lpm weibull --base scipy
```

This creates:
- `pyages/lpm/models/weibull.py` – Python class (template)
- `data_core/data_lpm/weibull/params.yaml` – Parameter configuration

Then follow the "Customize the Generated Code" section below.

---

## Manual Method: Step by Step

### Step 1: Create the Python Class

Create a new file `pyages/lpm/models/<name>.py`:

```python
# -*- coding: utf-8 -*-
# Copyright (c) YEAR COPYRIGHT HOLDER
# SPDX-License-Identifier: CECILL-2.1

"""
LPM Weibull distribution model.

Purpose
-------
Wrap the SciPy Weibull distribution as an LPM with metadata.

Reference
---------
[Add your academic reference here]

Author
------
Your Name
"""

from scipy.stats import weibull_min
from scipy.special import gamma as gamma_function
from scipy.special import gammainc

import numpy as np
import numpy.typing as npt

from pyages.lpm.core.lpm_scipy import LpmScipy
from pyages.lpm.core.registry import register_lpm


@register_lpm("weibull")  # This name is used in YAML configs
class WeibullLpm(LpmScipy):
    """Lumped Parameter Model - Weibull distribution."""

    scipy_dist = weibull_min  # The scipy.stats distribution

    def __init__(self, k=1.5, lambda_=10.0, directory_lpm=None):
        """
        Constructor.

        Parameters
        ----------
        k : float
            Shape parameter (k > 0).
        lambda_ : float
            Scale parameter (lambda > 0), represents characteristic time.
        directory_lpm : str, optional
            Directory for LPM parameter files.
        """
        # Map parameter names to values
        parameter_values = {"k": k, "lambda": lambda_}
        parameter_units = {"k": "-", "lambda": "year"}

        super().__init__("weibull", parameter_values, parameter_units, directory_lpm)

    def _scipy_params(self):
        """
        Map LPM parameters to scipy distribution parameters.

        Returns
        -------
        tuple
            (args, loc, scale) for scipy.stats calls.
        """
        # weibull_min takes: c (shape), loc, scale
        # Our k = shape, lambda = scale
        return (self.p["k"],), 0, self.p["lambda"]

    def cdf_and_partial_first_moment(self, t: npt.ArrayLike):
        """Return F(t) and E[T 1(T <= t)] for convolution."""
        shape = float(self.p["k"])
        scale = float(self.p["lambda"])
        values = np.asarray(t, dtype=float)
        cdf = np.asarray(self.cdf(values), dtype=float)
        first_moment = np.zeros_like(values, dtype=float)
        positive = values > 0.0
        if np.any(positive):
            reduced_age = np.power(values[positive] / scale, shape)
            moment_shape = 1.0 + 1.0 / shape
            first_moment[positive] = (
                scale
                * gamma_function(moment_shape)
                * gammainc(moment_shape, reduced_age)
            )
        if values.ndim == 0:
            return float(cdf), float(first_moment)
        return cdf, first_moment
```

### Step 2: Create the Parameter File

Create `data_core/data_lpm/<name>/params.yaml`:

```yaml
# LPM parameters for model "weibull"

model: weibull
version: 1

parameters:
  - name: k
    label: shape
    unit: "-"
    description: "Shape parameter (k > 0). k < 1: decreasing hazard, k = 1: constant (exponential), k > 1: increasing hazard."
    bounds: [0.1, 10.0]
    init: 1.5
    step: 0.2
    prior:
      type: uniform
      min: 0.1
      max: 10.0
      unit: "-"

  - name: lambda
    label: scale
    unit: year
    description: "Scale parameter representing characteristic transit time."
    bounds: [0.1, 100.0]
    init: 10.0
    step: 2.0
    prior:
      type: uniform
      min: 0.1
      max: 200.0
      unit: year

notes: |
  Weibull distribution for transit time modeling.
  - k < 1: Young water dominates
  - k = 1: Equivalent to exponential (well-mixed reservoir)
  - k > 1: Old water dominates
```

### Step 3: Verify the Registration

The `@register_lpm("weibull")` decorator registers the model when its module is
discovered inside `pyages.lpm.models`. In the editable development environment,
verify with:

```bash
pyages list lpms
```

Your new model should appear in the list of available LPMs.

## Minimal checklist (what must exist)

1) A Python class in `pyages/lpm/models/<name>.py` with `@register_lpm("<name>")`.
2) A parameter YAML file in `data_core/data_lpm/<name>/params.yaml`.
3) Parameter names in the YAML match constructor parameter names.
4) `build_lpm("<name>")` succeeds (no import errors).

---

## Customize the Generated Code

### Understanding `_scipy_params()`

The `_scipy_params()` method maps your LPM parameters to scipy's `(args, loc, scale)` format:

```python
def _scipy_params(self):
    return shape_args, loc, scale
```

Common patterns:

| Distribution | scipy name | args | loc | scale |
|--------------|-----------|------|-----|-------|
| Exponential | `expon` | `()` | `0` | `mu` |
| Gamma | `gamma` | `(a,)` | `0` | `scale` |
| Normal | `norm` | `()` | `mu` | `sigma` |
| Inverse Gaussian | `invgauss` | `((sigma / mu)**2,)` | `0` | `mu**3 / sigma**2` |
| Weibull | `weibull_min` | `(c,)` | `0` | `scale` |
| Log-normal | `lognorm` | `(s,)` | `0` | `scale` |

**Example - Gamma distribution:**

```python
# Gamma with shape α and scale θ (mean = α×θ)
def _scipy_params(self):
    # scipy.gamma(a, loc, scale) where a=shape
    alpha = self.p["mu"] ** 2 / self.p["sigma"] ** 2
    theta = self.p["sigma"] ** 2 / self.p["mu"]
    return (alpha,), 0, theta
```

### Base Classes

Choose the appropriate base class:

| Base Class | Use When |
|------------|----------|
| `LpmScipy` | Standard scipy distribution |
| `LpmBase` | Custom continuous, discrete, or mixed probability measure |

### Convolution contract

Continuous distributions use the common CDF–partial-first-moment engine. They
must provide a vectorized `cdf_and_partial_first_moment(t)` returning
`(F(t), E[T 1(T <= t)])`:

```python
from pyages.lpm.core.convolution_strategy import ConvolutionStrategy


@register_lpm("my_special_lpm")
class MySpecialLpm(LpmScipy):
    scipy_dist = some_dist
    convolution_strategy = ConvolutionStrategy.CONTINUOUS

    def cdf_and_partial_first_moment(self, t): ...
```

Available strategies:

- `CONTINUOUS`: CDF and partial-first-moment convolution (default)
- `DIRAC`: Direct lookup for point mass distributions
- `DIRAC_DOUBLE`: Two-point mass distributions
- `MIXED_DIRAC_CONTINUOUS`: Direct point mass plus normalized continuous part

PyAges does not reconstruct a production CDF from sampled PDF values. A
continuous model without a trustworthy vectorized CDF and partial first moment
is rejected explicitly.

For every finite, non-negative vector `t`, the provider must satisfy all of the
following conditions:

- return two finite arrays with exactly the same shape as `t`;
- return a CDF `F(t)` in `[0, 1]`, monotonically non-decreasing;
- return the raw partial moment `M(t) = E[T 1(T <= t)]` in years;
- for each interval `[a, b]` with mass `w = F(b) - F(a)`, satisfy
  `a*w <= M(b) - M(a) <= b*w`, up to floating-point roundoff;
- describe the same normalized continuous distribution through `cdf()`,
  `pdf()`, and `cdf_and_partial_first_moment()`.

For `MIXED_DIRAC_CONTINUOUS`,
`continuous_cdf_and_partial_first_moment()` describes the normalized continuous
component before the mixture weight is applied. The `rate` parameter is the
Dirac weight and must remain in `[0, 1]`.

Tests for a new continuous LPM should cover a unit constant tracer, an affine
tracer, a truncated history, probability bounds, moment consistency, and a
comparison with an independent quadrature or analytical expectation.

---

## Testing Your LPM

### Basic Test

```python
from pyages.lpm import build_lpm

# Create instance
lpm = build_lpm("weibull")
print(f"Parameters: {lpm.p}")

# Test PDF
import numpy as np

t = np.linspace(0, 50, 100)
pdf = lpm.pdf(t)
print(f"PDF integral: {np.trapezoid(pdf, t):.4f}")  # Should be ~1.0

# Test statistics
print(f"Mean: {lpm.mean():.2f} years")
print(f"Std:  {lpm.std():.2f} years")
```

### Test with Convolution

```python
from pyages.config.paths import DIRECTORY_TRACER_DATA
from pyages.convolution import Convolution
from pyages.tracer.tracer_root import Tracer

# Load tracer
tracer = Tracer(DIRECTORY_TRACER_DATA, name="cfc11")

# Create convolution
conv = Convolution(tracer, date=2010.0)

# Compute concentration
lpm = build_lpm("weibull")
concentration = conv.convolve(lpm)
print(f"CFC-11 concentration: {concentration:.2f} pptv")
```

### Run the system check

```bash
pyages check
```

---

## Parameter File Reference

### Required Fields

```yaml
parameters:
  - name: mu              # Must match constructor parameter
    bounds: [0.1, 100.0]  # Valid range
    init: 10.0            # Initial value for optimization
```

### Optional Fields

```yaml
parameters:
  - name: mu
    label: mean_age       # Display name
    unit: year            # Physical unit
    description: "..."    # Documentation
    step: 1.0             # For componentwise_source="model"
    prior:
      type: uniform
      min: 0.0
      max: 200.0
```

### Tips for Setting Parameters

| Field | Guideline |
|-------|-----------|
| `bounds` | Physical constraints (e.g., ages > 0) |
| `init` | Reasonable starting point for your application |
| `step` | Positive finite value; needed only for model-configured MH steps |
| `prior.min/max` | Wider than `bounds` to allow exploration |

---

## Complete Example: Log-Normal Distribution

### Python Class

```python
# pyages/lpm/models/lognormal.py

import numpy as np
import numpy.typing as npt
from scipy.special import ndtr
from scipy.stats import lognorm
from pyages.lpm.core.lpm_scipy import LpmScipy
from pyages.lpm.core.registry import register_lpm


@register_lpm("lognormal")
class LognormalLpm(LpmScipy):
    """Lumped Parameter Model - Log-normal distribution."""

    scipy_dist = lognorm

    def __init__(self, mu=10.0, sigma=5.0, directory_lpm=None):
        """
        Log-normal distribution parameterized by mean and std of transit time.

        Parameters
        ----------
        mu : float
            Mean transit time (years).
        sigma : float
            Standard deviation of transit time (years).
        """
        parameter_values = {"mu": mu, "sigma": sigma}
        parameter_units = {"mu": "year", "sigma": "year"}
        super().__init__("lognormal", parameter_values, parameter_units, directory_lpm)

    def _scipy_params(self):
        # Convert mean/std to lognormal parameters
        mu = self.p["mu"]
        sigma = self.p["sigma"]

        # Underlying normal distribution parameters
        sigma_ln = np.sqrt(np.log(1 + (sigma / mu) ** 2))
        mu_ln = np.log(mu) - 0.5 * sigma_ln**2

        # scipy.lognorm(s, loc, scale) where s=sigma_ln, scale=exp(mu_ln)
        return (sigma_ln,), 0, np.exp(mu_ln)

    def cdf_and_partial_first_moment(self, t: npt.ArrayLike):
        """Return F(t) and E[T 1(T <= t)] for convolution."""
        mean = float(self.p["mu"])
        std = float(self.p["sigma"])
        sigma_ln = np.sqrt(np.log1p((std / mean) ** 2))
        mu_ln = np.log(mean) - 0.5 * sigma_ln**2
        values = np.asarray(t, dtype=float)
        cdf = np.asarray(self.cdf(values), dtype=float)
        first_moment = np.zeros_like(values, dtype=float)
        positive = values > 0.0
        if np.any(positive):
            z = (np.log(values[positive]) - mu_ln - sigma_ln**2) / sigma_ln
            first_moment[positive] = mean * ndtr(z)
        if values.ndim == 0:
            return float(cdf), float(first_moment)
        return cdf, first_moment
```

### Parameter File

```yaml
# data_core/data_lpm/lognormal/params.yaml

model: lognormal
version: 1

parameters:
  - name: mu
    label: mean_age
    unit: year
    description: "Mean transit time."
    bounds: [0.1, 100.0]
    init: 10.0
    step: 2.0
    prior:
      type: uniform
      min: 0.0
      max: 200.0
      unit: year

  - name: sigma
    label: std_age
    unit: year
    description: "Standard deviation of transit time."
    bounds: [0.1, 50.0]
    init: 5.0
    step: 1.0
    prior:
      type: uniform
      min: 0.0
      max: 100.0
      unit: year

notes: |
  Log-normal distribution, common for heterogeneous aquifers.
  Parameterized by mean and std (not log-space parameters).
```

---

## Troubleshooting

### "Unknown LPM type: 'mymodel'"

- Check that `@register_lpm("mymodel")` decorator is present
- Verify the file is in the importable checkout at `pyages/lpm/models/`
- Ensure the checkout is installed in editable mode in the active environment
- Ensure no import errors: `python -c "import pyages.lpm.models.mymodel"`

### "Parameter 'x' not found in bounds"

- Ensure `params.yaml` has an entry for each parameter
- Check that `name` in YAML matches the parameter name in `__init__`

### PDF doesn't integrate to 1

- Check `_scipy_params()` mapping
- Verify scipy distribution is for positive values (transit times must be ≥ 0)

### Numerical issues with CDF or inverse CDF

- Check the physical-to-SciPy parameter conversion and extreme parameter values
- Keep `LpmScipy` as the generic base and add a distribution-specific override
  only when a focused regression test demonstrates that SciPy needs one
