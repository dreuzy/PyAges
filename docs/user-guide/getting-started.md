# Getting Started with PyAge

PyAge is a Python library for groundwater age dating using lumped-parameter models (LPMs) and environmental tracers. This guide will help you install PyAge and run your first simulation.

## Prerequisites

- Python 3.10 or later
- Conda (recommended) or pip
- Git

## Installation

### 1. Clone the Repository

```bash
git clone https://github.com/your-org/pyage.git
cd pyage
```

### 2. Create the Conda Environment

```bash
conda env create -f install/environment.yml
conda activate pyage
```

### 3. Verify Installation

Run the system check to verify everything is working:

```bash
python scripts/run_system_check.py
```

You should see output listing all available LPMs and tracers, with no errors.

## Project Structure

```
pyage/
├── pyage/                 # Core library
│   ├── LPM/              # Lumped Parameter Models
│   ├── tracer/           # Tracer definitions
│   ├── convolution/      # Convolution algorithms
│   ├── calibration/      # Calibration methods
│   └── config/           # Configuration utilities
├── data_core/            # Model data
│   ├── data_LPM/         # LPM parameter files
│   └── data_tracer/      # Tracer chronologies
├── examples/             # Runnable examples
├── scripts/              # CLI entry points
└── docs/                 # Documentation
```

## Quick Start: Run Your First Simulation

### 1. Run the Ploemeur Example

The simplest way to start is with an existing example:

```bash
python scripts/launcher.py --params examples/ploemeur/exemple_ploemeur.yaml
```

This runs a complete calibration workflow on the Ploemeur dataset using the `dirac_double` LPM model.

### 2. View the Results

Results are saved to:
```
~/results/PyAge/test_cases/ploemeur_F09_2010/
```

Key output files:
- `parameters_calibration.txt` - Calibrated parameter values
- `results_calibration.txt` - Calibration summary
- `concentration_times.png` - Concentration plot

### 3. Customize the Configuration

Copy an example YAML and modify it:

```bash
cp examples/ploemeur/exemple_ploemeur.yaml my_config.yaml
```

Edit `my_config.yaml` to change:
- The LPM model (`lpm.model_name`)
- The number of MCMC steps (`calibration_metropolis_hastings.nstep`)
- Which analyses to run (`run.*` options)

Then run with your configuration:

```bash
python scripts/launcher.py --params my_config.yaml
```

## Understanding the Core Concepts

### Lumped Parameter Models (LPMs)

LPMs describe the distribution of groundwater transit times. Available models include:

| Model | Description | Parameters |
|-------|-------------|------------|
| `dirac` | Single age (piston flow) | `tau` (age) |
| `dirac_double` | Binary mixing | `tau1`, `tau2`, `f` |
| `exp` | Exponential distribution | `mu` (mean age) |
| `exp_shifted` | Shifted exponential | `mu`, `shift` |
| `ig` | Inverse Gaussian | `mu`, `sigma` |
| `gamma` | Gamma distribution | `mu`, `sigma` |

### Tracers

Tracers are chemical species with known atmospheric histories used to date groundwater:

| Tracer | Unit | Description |
|--------|------|-------------|
| `cfc11` | pptv | CFC-11 (declining since 1990s) |
| `cfc12` | pptv | CFC-12 (similar to CFC-11) |
| `sf6` | pptv | SF6 (still increasing) |
| `3H` | TU | Tritium (radioactive, bomb peak) |
| `14C` | pmC | Carbon-14 (long timescales) |

### Convolution

The convolution operation combines a tracer's atmospheric history with an LPM's transit time distribution to predict the concentration measured in a groundwater sample.

```
C(t) = ∫ c_in(t - τ) × g(τ) × decay(τ) dτ
```

Where:
- `C(t)` = measured concentration at time t
- `c_in` = input (atmospheric) concentration
- `g(τ)` = LPM probability density function
- `decay(τ)` = radioactive decay factor

## Next Steps

- [Running Examples](running-examples.md) - Detailed examples walkthrough
- [Configuration Reference](configuration.md) - All YAML options explained
- [Adding a New LPM](adding-lpm.md) - Create your own distribution model
- [Adding a New Tracer](adding-tracer.md) - Add a new tracer chronology

## Getting Help

- Run `python scripts/launcher.py --help` for CLI options
- Check the `scripts/README.md` for script documentation
- Report issues at: https://github.com/your-org/pyage/issues
