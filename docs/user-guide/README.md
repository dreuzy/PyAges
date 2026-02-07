# PyAge User Guide

Welcome to the PyAge user documentation. This guide helps you use PyAge for groundwater age dating using lumped-parameter models (LPMs) and environmental tracers.

## Contents

### Getting Started

- **[Getting Started](getting-started.md)**
  Installation, first steps, and core concepts overview.

### Using PyAge

- **[Running Examples](running-examples.md)**
  Detailed walkthrough of the included examples (Ploemeur, Fontainebleau, temporal analysis).

- **[Configuration Reference](configuration.md)**
  Complete reference for all YAML configuration options.

- **[CLI Flags Reference](cli-flags.md)**
  Summary of the optional CLI flags for each command.

### Extending PyAge

- **[Adding a New LPM](adding-lpm.md)**
  How to create a new Lumped Parameter Model (transit time distribution).

- **[Adding a New Tracer](adding-tracer.md)**
  How to add a new environmental tracer with its atmospheric history.

---

## Quick Reference

### Run an Example

```bash
conda activate pyage
python scripts/launcher.py --params examples/ploemeur/exemple_ploemeur.yaml
pyage run examples/ploemeur/exemple_ploemeur.yaml
```

### Create New Components

```bash
# New LPM
python scripts/new_component.py lpm <name> --params <p1,p2> --scipy <dist>

# New Tracer
python scripts/new_component.py tracer <name> --unit <unit> [--decay]
```

### Check Installation

```bash
python scripts/run_system_check.py
python scripts/run_system_check.py --params configs/system_check.yaml
pyage check
```

---

## Available LPM Models

| Model | Class | Parameters | Description |
|-------|-------|------------|-------------|
| `dirac` | `DiracLpm` | `tau` | Single age (piston flow) |
| `dirac_double` | `DiracDoubleLpm` | `mu1`, `mu2`, `rate` | Binary mixing |
| `exp` | `ExponentialLpm` | `mu` | Exponential distribution |
| `exp_shifted` | `ExponentialShiftedLpm` | `mu`, `shift` | Shifted exponential |
| `ig` | `InverseGaussianLpm` | `mu`, `sigma` | Inverse Gaussian |
| `ig_shifted` | `InverseGaussianShiftedLpm` | `mu`, `sigma`, `shift` | Shifted inverse Gaussian |
| `gamma` | `GammaLpm` | `mu`, `sigma` | Gamma distribution |
| `uniform` | `UniformLpm` | `a`, `b` | Uniform distribution |
| `weibull` | `WeibullLpm` | `k`, `lambda` | Weibull distribution |

## Available Tracers

| Tracer | Unit | Decay | Description |
|--------|------|-------|-------------|
| `cfc11` | pptv | No | CFC-11 (declining since 1990s) |
| `cfc12` | pptv | No | CFC-12 (declining) |
| `cfc113` | pptv | No | CFC-113 (declining) |
| `sf6` | pptv | No | SF6 (still increasing) |
| `3H` | TU | Yes | Tritium (bomb peak) |
| `14C` | pmC | Yes | Carbon-14 (long timescales) |
| `39Ar` | atoms/L | Yes | Argon-39 |
| `kr85` | Bq/L | Yes | Krypton-85 |

---

## Project Structure

```
pyage/
├── pyage/                    # Core library
│   ├── lpm/                  # Lumped Parameter Models
│   │   ├── core/            # Base classes, registry
│   │   └── models/          # Model implementations
│   ├── tracer/              # Tracer handling
│   ├── convolution/         # Convolution algorithms
│   ├── calibration/         # MCMC, simplex methods
│   └── config/              # Configuration utilities
│
├── data_core/               # Model data
│   ├── data_lpm/           # LPM parameter files
│   └── data_tracer/        # Tracer chronologies
│
├── examples/                # Runnable examples
├── scripts/                 # CLI entry points
└── docs/                    # Documentation
```

---

## Support

- **Scripts help**: `python scripts/<script>.py --help`
- **System check**: `python scripts/run_system_check.py`
- **Issues**: Report on GitHub/GitLab
