# PyAge Refactoring Plan

## Objectives

1. **Maintainability**: Reduce duplicate code and clarify architecture.
2. **Extensibility**: Make it easy to add new sites/wells/tracers/LPMs.
3. **Robustness**: Improve error handling and test coverage.
4. **Performance**: Targeted optimizations without breaking behavior.

## Current State (Revised Structure)

- `pyage/` contains `convolution/` (singular), `concentrations/`,
  `calibration/{methods,utils,workflows}`, `config/`, and other core modules.
- `data_core/` stores LPM and tracer data (core datasets).
- `examples/` contains demo scenarios and datasets (fontainebleau, ploemeur).
- `docs/` holds user and developer documentation.

---

## Phases Overview

```
PHASE 0: PREPARATION (1-2 days)
  Characterization tests + golden references
        |
PHASE 1: EXTERNAL CONFIG (2-3 days)
  wells_config.yaml + selector() refactor
        |
PHASE 2: ERROR HANDLING (1-2 days)
  Custom exceptions + remove sys.exit()
        |
PHASE 3: LOGGING (1 day)
  Structured logging system
        |
PHASE 4: DATA/CODE SEPARATION (2-3 days)
  Repository layout + hierarchical config
        |
PHASE 5: OPTIMIZATIONS (optional, 2-3 days)
  Vectorized convolution + caching
```

---

## Phase 0: Preparation - Characterization Tests

### Goal
Capture the current behavior before any refactoring to prevent regressions.

### Actions

#### 0.1 Create test structure

```
tests/
├── conftest.py
├── golden_references/
│   ├── lpm/
│   ├── convolution/
│   └── selector/
├── characterization/
│   └── test_capture_golden.py
├── regression/
│   └── test_regression.py
└── unit/
```

#### 0.2 Capture golden references

- Create a one-time capture test for:
  - LPM PDF/CDF/mean/std
  - Convolutions for a few tracer/LPM/date combinations
  - `selector()` results for known wells

#### 0.3 Regression tests

- Compare current outputs to golden files with strict tolerances.

#### 0.4 Test runner

```bash
python tests/run_tests.py capture     # Capture golden references
python tests/run_tests.py regression  # Verify non-regression
python tests/run_tests.py all         # Run everything
```

---

## Phase 1: Externalized Configuration

### Goal
Move hardcoded well configuration into YAML and reuse it across workflows.

### Actions

1. Create `wells_config.yaml` containing:
   - defaults (shared settings)
   - per-well overrides (dates, tracers, LPM list)
2. Add a config loader with:
   - validation
   - defaults merging
   - stable API for selection
3. Replace `selector()` with a wrapper that loads YAML.
4. Keep a fallback `_selector_legacy()` temporarily.

### Validation

```bash
python tests/run_tests.py regression
python -c "from pyage.site_config import get_wells_config; print(get_wells_config().list_wells())"
```

---

## Phase 2: Error Handling

### Goal
Replace `sys.exit()` with typed exceptions that can be handled upstream.

### Actions

1. Create `pyage/core/exceptions.py` with a simple hierarchy:
   - `PyAgeError`
   - `ConfigError`, `DataError`, `ModelError`, `CalibrationError`, etc.
2. Replace `sys.exit()` with `raise ...Error(...)` in:
   - convolution modules
   - LPM build
   - calibration methods

### Validation

```bash
python tests/run_tests.py regression
python -c "from pyage.lpm.lpm_build import lpm_build; lpm_build('invalid')"
```

---

## Phase 3: Logging and Monitoring

### Goal
Replace `print()` statements with structured logging.

### Actions

1. Add `pyage/core/logging.py`:
   - console + optional file logging
   - standardized format
2. Update modules to use `logger.info/warning/error`.

---

## Phase 4: Data / Code Separation

### Goal
Clearly separate core code, applications, and datasets.

### Proposed Layout

```
pyage/
├── pyage/               # Python package (core library)
├── applications/        # Site-specific apps (optional)
├── data/                # External datasets
├── data_core/           # Default datasets shipped with repo
├── tests/
├── docs/
└── pyproject.toml
```

### Migration Strategy

1. Create the new structure without moving files.
2. Add temporary compatibility imports.
3. Move modules gradually, then remove compatibility shims.

---

## Phase 5: Optimizations (Optional)

### 5.1 Cache tracer recharge chronicle

```python
from functools import lru_cache

class Tracer:
    @lru_cache(maxsize=32)
    def _load_recharge_cached(self, tracer_name: str):
        ...
```

### 5.2 Vectorized convolution for many dates

```python
def convolution_vectorized(self, lpm, dates: np.ndarray) -> np.ndarray:
    results = np.zeros(len(dates))
    t_grid = np.linspace(0, self.datemax - self.datemin, 200)
    for i, date in enumerate(dates):
        self.__date = date
        results[i] = self._convolution_with_grid(lpm, t_grid)
    return results
```

---

## Summary Table

| Phase | Duration | Priority | Impact |
| --- | --- | --- | --- |
| Phase 0: Tests | 1-2 days | Critical | Safety |
| Phase 1: Config YAML | 2-3 days | High | Maintainability |
| Phase 2: Exceptions | 1-2 days | High | Robustness |
| Phase 3: Logging | 1 day | Medium | Observability |
| Phase 4: Reorganization | 2-3 days | Medium | Architecture |
| Phase 5: Optimization | 2-3 days | Low | Performance |

### Validation Checklist

- [ ] Regression tests pass
- [ ] No functionality broken
- [ ] Code committed with clear message
- [ ] Docs updated if needed

### Validation Commands

```bash
python tests/run_tests.py regression
git add -A
git commit -m "Phase X.Y: short description"
```

---

## Appendix: Data File Migration

### Current vs Proposed LPM bounds format

**Current** (`.../bounds.txt`):
```
mu,0,100,year
shift,0,100,year
```

**Proposed** (`.../config.yaml`):
```yaml
parameters:
  mu:
    min: 0
    max: 100
    unit: year
  shift:
    min: 0
    max: 100
    unit: year
```

### Conversion Script

```python
# scripts/convert_lpm_config.py
"""Convert bounds.txt and MH config files into a single YAML."""
from pathlib import Path
import yaml

def convert_bounds_to_yaml(lpm_dir: Path):
    config = {"parameters": {}, "metropolis_hastings": {"step": {}, "prior": {}}}

    bounds_file = lpm_dir / "bounds.txt"
    if bounds_file.exists():
        for line in bounds_file.read_text().strip().split("\n"):
            name, vmin, vmax, unit = line.split(",")
            config["parameters"][name] = {
                "min": float(vmin),
                "max": float(vmax),
                "unit": unit
            }

    step_file = lpm_dir / "MHstep.txt"
    if step_file.exists():
        for line in step_file.read_text().strip().split("\n"):
            name, value = line.split(",")
            config["metropolis_hastings"]["step"][name] = float(value)

    prior_file = lpm_dir / "MHapriori.txt"
    if prior_file.exists():
        for line in prior_file.read_text().strip().split("\n"):
            name, ptype, p1, p2 = line.split(",")
            config["metropolis_hastings"]["prior"][name] = {
                "type": ptype,
                "param1": float(p1),
                "param2": float(p2)
            }

    output = lpm_dir / "config.yaml"
    with open(output, "w", encoding="utf-8") as handle:
        yaml.dump(config, handle, default_flow_style=False, sort_keys=False)

    print(f"Converted: {lpm_dir.name} -> {output}")


if __name__ == "__main__":
    for lpm_dir in Path("data_core/data_lpm").iterdir():
        if lpm_dir.is_dir():
            convert_bounds_to_yaml(lpm_dir)
```
