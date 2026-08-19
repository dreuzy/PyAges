# Getting Started with PyAge

PyAge is a Python library for groundwater age dating using lumped-parameter models (LPMs) and environmental tracers. This guide will help you install PyAge and run your first simulation.

## Prerequisites

- Python 3.9 or later
- Conda (recommended) or pip
- Git

## Installation

### 1. Clone the Repository

```bash
git clone https://gitlab.univ-rennes1.fr/aupepin/pyage.git
cd pyage
```

### 2. Create the Conda Environment

```bash
conda env create -f install/environment.yml
conda activate pyage
```

### 3. Install PyAge (CLI enabled)

```bash
python -m pip install -e .
```

Contributors should install the test, release, and documentation tools declared
by the project:

```bash
python -m pip install -c install/constraints.txt -e ".[dev,docs,examples]"
```

IDE and media-export packages are optional; see `install/README.md` for the
separate conda command.

### 4. Verify Installation

Run the system check to verify everything is working:

```bash
python -m scripts.run_system_check
```

You should see output listing all available LPMs and tracers, with no errors.
Advanced checks can override defaults with
`python -m scripts.run_system_check --params <config.yaml>`.

## Project Structure

```
pyage/
├── pyage/                 # Core library
│   ├── lpm/              # Lumped Parameter Models
│   ├── tracer/           # Tracer definitions
│   ├── convolution/      # Convolution algorithms
│   ├── calibration/      # Calibration methods
│   └── config/           # Configuration utilities
├── data_core/            # Model data
│   ├── data_lpm/         # LPM parameter files
│   └── data_tracer/      # Tracer chronologies
├── examples/             # Runnable examples
├── scripts/              # CLI entry points
└── docs/                 # Documentation
```

## Quick Start: Run Your First Simulation

### 1. Run the Ploemeur Example

The simplest way to start is with an existing example:

```bash
pyage run examples/natural/ploemeur/exemple_ploemeur.yaml
```

Or use the minimal templates (fast, no interactive plots):

```bash
pyage run examples/templates/quickstart_single.yaml
pyage run --transient examples/templates/quickstart_temporal.yaml
```

Or, if you installed the package, use the CLI:

```bash
pyage run examples/natural/ploemeur/exemple_ploemeur.yaml
```

You can override key fields from the CLI (without editing YAML):

```bash
pyage run --lpm exp_shifted --mh-nsteps 5000 \
  --data-name mydata.txt --data-dir examples/my_site/data \
  my_config.yaml
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
cp examples/natural/ploemeur/exemple_ploemeur.yaml my_config.yaml
```

Edit `my_config.yaml` to change:
- The LPM model (`lpm.model_name`)
- The number of MCMC steps (`calibration_metropolis_hastings.nstep`)
- Which analyses to run (`run.*` options)

Then run with your configuration:

```bash
pyage run my_config.yaml
```

## Understanding the Core Concepts

### Lumped Parameter Models (LPMs)

LPMs describe the distribution of groundwater transit times. Available models include:

| Model | Description | Parameters |
|-------|-------------|------------|
| `dirac` | Single age (piston flow) | `tau` (age) |
| `dirac_double` | Binary mixing | `mu1`, `mu2`, `rate` |
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

- Run `pyage run --help` for workflow options
- Run `pyage --help` for all CLI commands
- Check the `scripts/README.md` for script documentation
- Report issues at: https://gitlab.univ-rennes1.fr/aupepin/pyage
