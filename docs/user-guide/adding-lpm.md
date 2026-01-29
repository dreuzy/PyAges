# Adding a New LPM

This guide explains how to add a new Lumped Parameter Model (LPM) to PyAge. LPMs describe probability distributions of groundwater transit times.

## Quick Method: Use the Template Generator

The easiest way to create a new LPM is with the template generator:

```bash
python scripts/new_component.py lpm <name> --params <p1,p2,...> --scipy <distribution>
```

Example for a Weibull distribution:

```bash
python scripts/new_component.py lpm weibull --params k,lambda --scipy weibull_min
```

This creates:
- `pyage/LPM/models/weibull.py` - Python class
- `data_core/data_LPM/weibull/params.yaml` - Parameter configuration

Then follow the "Customize the Generated Code" section below.

---

## Manual Method: Step by Step

### Step 1: Create the Python Class

Create a new file `pyage/LPM/models/<name>.py`:

```python
# -*- coding: utf-8 -*-
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

from pyage.LPM.core.lpm_scipy import LpmScipy
from pyage.LPM.core.registry import register_lpm


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
        parameter_values = {'k': k, 'lambda': lambda_}
        parameter_units = {'k': '-', 'lambda': 'year'}

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
        return (self.p['k'],), 0, self.p['lambda']
```

### Step 2: Create the Parameter File

Create `data_core/data_LPM/<name>/params.yaml`:

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

The `@register_lpm("weibull")` decorator automatically registers the model. Verify with:

```bash
python scripts/run_system_check.py
```

Your new model should appear in the list of available LPMs.

---

## Customize the Generated Code

### Understanding `_scipy_params()`

The `_scipy_params()` method maps your LPM parameters to scipy's `(args, loc, scale)` format:

```python
def _scipy_params(self):
    return (args_tuple,), loc, scale
```

Common patterns:

| Distribution | scipy name | args | loc | scale |
|--------------|-----------|------|-----|-------|
| Exponential | `expon` | `()` | `0` | `mu` |
| Gamma | `gamma` | `(a,)` | `0` | `scale` |
| Normal | `norm` | `()` | `mu` | `sigma` |
| Inverse Gaussian | `invgauss` | `(mu,)` | `0` | `sigma` |
| Weibull | `weibull_min` | `(c,)` | `0` | `scale` |
| Log-normal | `lognorm` | `(s,)` | `0` | `scale` |

**Example - Gamma distribution:**

```python
# Gamma with shape α and scale θ (mean = α×θ)
def _scipy_params(self):
    # scipy.gamma(a, loc, scale) where a=shape
    alpha = self.p['mu']**2 / self.p['sigma']**2
    theta = self.p['sigma']**2 / self.p['mu']
    return (alpha,), 0, theta
```

### Base Classes

Choose the appropriate base class:

| Base Class | Use When |
|------------|----------|
| `LpmScipy` | Standard scipy distribution |
| `LpmScipySafe` | Distribution with numerical edge cases (e.g., inverse Gaussian) |
| `LpmBase` | Custom distribution not in scipy |

### Custom Convolution Strategy

For special distributions that need optimized convolution (like Dirac or exponential), set the convolution strategy:

```python
from pyage.LPM.core.convolution_strategy import ConvolutionStrategy

@register_lpm("my_special_lpm")
class MySpecialLpm(LpmScipy):
    scipy_dist = some_dist
    convolution_strategy = ConvolutionStrategy.CLASSIC  # or DIRAC, EXPONENTIAL, etc.
```

Available strategies:
- `CLASSIC`: Standard numerical integration (default)
- `DIRAC`: Direct lookup for point mass distributions
- `DIRAC_DOUBLE`: Two-point mass distributions
- `EXPONENTIAL`: Optimized for exponential distributions

---

## Testing Your LPM

### Basic Test

```python
from pyage.LPM.lpm_build import lpm_build

# Create instance
lpm = lpm_build("weibull")
print(f"Parameters: {lpm.p}")

# Test PDF
import numpy as np
t = np.linspace(0, 50, 100)
pdf = lpm.pdf(t)
print(f"PDF integral: {np.trapz(pdf, t):.4f}")  # Should be ~1.0

# Test statistics
print(f"Mean: {lpm.mean():.2f} years")
print(f"Std:  {lpm.std():.2f} years")
```

### Test with Convolution

```python
from pyage.tracer.tracer_root import Tracer, find_tracer_dir
from pyage.convolution.convolution import Convolution

# Load tracer
tracer = Tracer(find_tracer_dir(), name="cfc11")

# Create convolution
conv = Convolution(tracer, date=2010.0)

# Compute concentration
lpm = lpm_build("weibull")
concentration = conv.compute_convolution(lpm)
print(f"CFC-11 concentration: {concentration:.2f} pptv")
```

### Run System Check

```bash
python scripts/run_system_check.py
```

---

## Parameter File Reference

### Required Fields

```yaml
parameters:
  - name: mu              # Must match constructor parameter
    bounds: [0.1, 100.0]  # Valid range
    init: 10.0            # Initial value for optimization
    step: 1.0             # MCMC proposal step size
```

### Optional Fields

```yaml
parameters:
  - name: mu
    label: mean_age       # Display name
    unit: year            # Physical unit
    description: "..."    # Documentation
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
| `step` | ~5-10% of expected parameter range |
| `prior.min/max` | Wider than `bounds` to allow exploration |

---

## Complete Example: Log-Normal Distribution

### Python Class

```python
# pyage/LPM/models/lognormal.py

from scipy.stats import lognorm
from pyage.LPM.core.lpm_scipy import LpmScipy
from pyage.LPM.core.registry import register_lpm


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
        parameter_values = {'mu': mu, 'sigma': sigma}
        parameter_units = {'mu': 'year', 'sigma': 'year'}
        super().__init__("lognormal", parameter_values, parameter_units, directory_lpm)

    def _scipy_params(self):
        # Convert mean/std to lognormal parameters
        import numpy as np
        mu = self.p['mu']
        sigma = self.p['sigma']

        # Underlying normal distribution parameters
        sigma_ln = np.sqrt(np.log(1 + (sigma/mu)**2))
        mu_ln = np.log(mu) - 0.5 * sigma_ln**2

        # scipy.lognorm(s, loc, scale) where s=sigma_ln, scale=exp(mu_ln)
        return (sigma_ln,), 0, np.exp(mu_ln)
```

### Parameter File

```yaml
# data_core/data_LPM/lognormal/params.yaml

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
- Verify the file is in `pyage/LPM/models/`
- Ensure no import errors: `python -c "from pyage.LPM.models.LPM_mymodel import *"`

### "Parameter 'x' not found in bounds"

- Ensure `params.yaml` has an entry for each parameter
- Check that `name` in YAML matches the parameter name in `__init__`

### PDF doesn't integrate to 1

- Check `_scipy_params()` mapping
- Verify scipy distribution is for positive values (transit times must be ≥ 0)

### Numerical issues with CDF

- Use `LpmScipySafe` instead of `LpmScipy`
- Check for extreme parameter values
