# PyAge Architecture Overview

## Table of Contents

1. Overview
2. Module Structure
3. Architectural Patterns
4. Data and Control Flow
5. Parameter Files
6. Multi-Well Workflows and Parallelization
7. Calibration Architecture
8. Refactoring Focus Areas

---

## 1. Overview

PyAge is a Bayesian inversion framework for groundwater age dating using chemical tracers (CFCs, SF6, tritium, etc.). It calibrates Lumped Parameter Models (LPMs) that represent distributions of water transit times in aquifers.

The modeled concentration at observation date `t_obs` is:

```
C_modeled(t_obs) = ∫0^∞ C_atm(t_obs - τ) × g(τ) × D(τ) × P(τ) dτ
```

Where:

- `C_atm(t)` is the atmospheric recharge concentration (tracer chronicle).
- `g(τ)` is the LPM PDF (transit time distribution).
- `D(τ)` is a decay factor (e.g., exp(-τ/τ_decay) for radioactive tracers).
- `P(τ)` is a geoproduction factor (optional).
- `τ` is the residence time (water age).

---

## 2. Module Structure

Top-level structure (conceptual):

```
pyage/
├── lpm/                 # LPM models and registry
├── tracer/              # Tracer definition and data loading
├── convolution/         # Convolution engine
├── concentrations/      # Observations and concentration utilities
├── calibration/         # Calibration methods + utilities
├── config/              # Paths, context, bootstrap, pydantic models
└── data_io/             # Data loading helpers
```

Key responsibilities:

- **Tracer**: reads tracer metadata and recharge chronicle, computes tracer concentration over time.
- **LPM**: defines the transit time PDF/CDF and parameter metadata.
- **Convolution**: combines tracer input and LPM to compute modeled concentrations.
- **Calibration**: fits model parameters to observations (e.g., MCMC).

---

## 3. Architectural Patterns

### 3.1 Registry Pattern for LPMs

Each LPM class registers itself using `@register_lpm("name")`. The factory
functions discover and build models dynamically.

Benefits:
- Add a model by creating a new class file.
- Automatic listing via `list_available_lpms()`.

### 3.2 Convolution Strategy (Enum)

Each LPM can declare a convolution strategy:

- `CLASSIC`: numeric integration (Simpson).
- `DIRAC`: direct lookup for point-mass models.
- `DIRAC_DOUBLE`: two-point mass models.
- `EXPONENTIAL`: refined integration near discontinuities.

The convolution engine chooses the algorithm from the LPM attribute.

### 3.3 Composition over Inheritance

`Convolution` does not inherit from `Tracer`. It uses composition:

```python
tracer = Tracer(...)
conv = Convolution(tracer, date=2010.0)
value = conv.convolution(lpm)
```

This isolates tracer data loading from convolution logic and supports synthetic tracers in tests.

---

## 4. Data and Control Flow

High-level flow:

1. Load tracer data (chronicle, decay, geoproduction).
2. Build an LPM instance (from registry + params).
3. Convolve tracer input with LPM PDF to get modeled concentration.
4. Compare modeled vs observed concentrations in calibration.
5. Produce outputs (figures, distributions, diagnostics).

---

## 5. Parameter Files

### 5.1 LPM parameters (`data_core/data_lpm/<model>/params.yaml`)

Example:

```yaml
model: exp_shifted
parameters:
  - name: mu
    bounds: [0.1, 100.0]
    init: 10.0
    step: 1.0
  - name: shift
    bounds: [0.0, 50.0]
    init: 2.0
    step: 0.5
```

### 5.2 Tracer parameters (`data_core/data_tracer/<tracer>/`)

Example keys (per tracer):

- `recharge.csv` or `recharge.txt`: atmospheric chronicle
- metadata file with:
  - `decay_time`
  - `geoproduction_rate`
  - `[tmin, tmax]`

---

## 6. Multi-Well Workflows and Parallelization

Many workflows run combinations of:

- multiple wells
- multiple dates or spans
- multiple LPMs
- multiple tracers

These combinations can lead to thousands of simulations. Parallel execution is supported using multiprocessing in some site workflows.

Key outputs are stored per run in a structured results directory:

```
results/
└── <site>/
    └── <dataset>/
        └── <mode>/
            └── <lpm>/
                ├── parameters_calibration.txt
                ├── results_calibration.txt
                └── Metropolis_Hastings/
```

---

## 7. Calibration Architecture

### 7.1 Calibration Core

The calibration system:

- builds the objective function,
- evaluates priors and likelihoods,
- stores the posterior distribution,
- provides statistics and diagnostics.

### 7.2 Metropolis-Hastings (MCMC)

The MCMC workflow:

1. Initialize parameters from YAML.
2. Propose new parameters using a random walk.
3. Accept/reject based on posterior ratio.
4. Store samples after burn-in and thinning.

Key tuning parameters:

- `nstep`: total iterations
- `burn_in`: fraction of initial samples discarded
- `nskip`: thinning interval
- `step`: proposal scale

---

## 8. Refactoring Focus Areas

1. **Configuration**: move hardcoded selectors to YAML.
2. **Errors**: replace `sys.exit()` with typed exceptions.
3. **Logging**: switch from `print()` to structured logging.
4. **Data/code separation**: clarify repository layout.
5. **Performance**: caching and vectorized convolution where safe.

---

## Summary

PyAge is structured around four core components:

- **Tracer**
- **LPM**
- **Convolution**
- **Calibration**

This separation enables extensibility (new tracers/LPMs), reuse, and testing. The refactoring plan focuses on improving maintainability and stability without changing scientific behavior.
