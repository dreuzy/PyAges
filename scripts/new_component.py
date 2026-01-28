# -*- coding: utf-8 -*-
"""
Template generator for new PyAge components (LPMs and Tracers).

Usage
-----
    python new_component.py lpm <name> [--params param1,param2,...]
    python new_component.py tracer <name> [--unit <unit>] [--decay] [--production]

Examples
--------
    # Create a new LPM with two parameters
    python new_component.py lpm weibull --params k,lambda

    # Create a new tracer with default settings
    python new_component.py tracer argon39

    # Create a tracer with radioactive decay
    python new_component.py tracer tritium --unit TU --decay

Author
------
PyAge Development Team
"""

import argparse
import sys
from pathlib import Path
from datetime import datetime


# =============================================================================
# Path Configuration
# =============================================================================

def get_project_root() -> Path:
    """Get the project root directory."""
    return Path(__file__).resolve().parent.parent


def get_lpm_models_dir() -> Path:
    """Get the LPM models directory."""
    return get_project_root() / "pyage" / "LPM" / "models"


def get_lpm_data_dir() -> Path:
    """Get the LPM data directory."""
    return get_project_root() / "data_core" / "data_LPM"


def get_tracer_data_dir() -> Path:
    """Get the tracer data directory."""
    return get_project_root() / "data_core" / "data_tracer"


# =============================================================================
# LPM Template Generation
# =============================================================================

PYTHON_RESERVED_WORDS = {
    'False', 'None', 'True', 'and', 'as', 'assert', 'async', 'await',
    'break', 'class', 'continue', 'def', 'del', 'elif', 'else', 'except',
    'finally', 'for', 'from', 'global', 'if', 'import', 'in', 'is',
    'lambda', 'nonlocal', 'not', 'or', 'pass', 'raise', 'return', 'try',
    'while', 'with', 'yield'
}


def safe_param_name(name: str) -> str:
    """Convert parameter name to safe Python identifier (adds _ suffix if reserved)."""
    if name in PYTHON_RESERVED_WORDS:
        return f"{name}_"  # e.g., lambda -> lambda_
    return name


LPM_PYTHON_TEMPLATE = '''# -*- coding: utf-8 -*-
"""
LPM {display_name} distribution model.

Purpose
-------
{description}

Reference
---------
[Add your reference here]

Author
------
[Your name]
"""

from scipy.stats import {scipy_dist}

from LPM.core.LPM_scipy import LPMScipy
from LPM.core.registry import register_lpm


@register_lpm("{registry_name}")
class {class_name}(LPMScipy):
    """Lumped Parameter Model - {display_name} distribution."""

    scipy_dist = {scipy_dist}

    def __init__(self, {init_params}, directory_lpm=None):
        """
        Constructor.

        Parameters
        ----------
{param_docs}
        directory_lpm : str, optional
            Directory for LPM parameter files.
        """
        parameter_values = {{{param_dict}}}
        parameter_units = {{{param_units}}}
        super().__init__("{registry_name}", parameter_values, parameter_units, directory_lpm)

    def _scipy_params(self):
        """
        Return scipy distribution parameters.

        Returns
        -------
        tuple
            (args, loc, scale) for scipy distribution.
            Adjust this method based on your scipy distribution's parameterization.
        """
        # TODO: Adjust this based on your scipy distribution
        # Common patterns:
        #   Exponential: return (), 0, self.p['mu']
        #   Gamma: return (self.p['k'],), 0, self.p['theta']
        #   Normal: return (), self.p['mu'], self.p['sigma']
        return ({scipy_args}), 0, {scipy_scale}
'''


LPM_YAML_TEMPLATE = '''# LPM parameters for model "{registry_name}"
#
# This file defines parameter bounds, initial values, and MCMC settings.
# Used by calibration routines (simplex, Metropolis-Hastings).
#
# Created: {date}
# Author: [Your name]

model: {registry_name}
version: 1

parameters:
{param_yaml}

notes: |
  Add any notes about this model here.
  - Parameter interpretation
  - Physical constraints
  - References
'''


LPM_PARAM_YAML_TEMPLATE = '''  - name: {name}
    label: {label}
    unit: {unit}
    description: "{description}"
    bounds: [{bound_min}, {bound_max}]
    init: {init}
    step: {step}
    prior:
      type: uniform
      min: {prior_min}
      max: {prior_max}
      unit: {unit}
'''


def generate_lpm(name: str, params: list[str], scipy_dist: str = "norm") -> dict:
    """
    Generate LPM template files.

    Parameters
    ----------
    name : str
        LPM model name (e.g., 'weibull', 'lognormal')
    params : list[str]
        List of parameter names (e.g., ['k', 'lambda'])
    scipy_dist : str
        Scipy distribution name (default: 'norm')

    Returns
    -------
    dict
        Paths to generated files
    """
    # Normalize name
    registry_name = name.lower().replace("-", "_")
    class_name = f"LPM_{registry_name}"
    display_name = name.replace("_", " ").title()

    # Default parameters if none provided
    if not params:
        params = ["mu", "sigma"]

    # Generate safe Python identifiers for parameters
    safe_params = [safe_param_name(p) for p in params]

    # Generate Python file content
    init_params = ", ".join([f"{sp}=1.0" for sp in safe_params])
    param_dict = ", ".join([f"'{p}': {sp}" for p, sp in zip(params, safe_params)])
    param_units = ", ".join([f"'{p}': 'year'" for p in params])

    param_docs = "\n".join([
        f"        {sp} : float\n            Parameter {p} of the distribution."
        for p, sp in zip(params, safe_params)
    ])

    # Scipy params - user needs to customize
    if len(params) == 1:
        scipy_args = ""
        scipy_scale = f"self.p['{params[0]}']"
    else:
        scipy_args = ", ".join([f"self.p['{p}']" for p in params[:-1]])
        scipy_scale = f"self.p['{params[-1]}']"

    python_content = LPM_PYTHON_TEMPLATE.format(
        class_name=class_name,
        registry_name=registry_name,
        display_name=display_name,
        description=f"Wrap the SciPy {display_name} distribution as an LPM with metadata.",
        scipy_dist=scipy_dist,
        init_params=init_params,
        param_docs=param_docs,
        param_dict=param_dict,
        param_units=param_units,
        scipy_args=scipy_args,
        scipy_scale=scipy_scale,
    )

    # Generate YAML content
    param_yaml_parts = []
    for i, p in enumerate(params):
        param_yaml_parts.append(LPM_PARAM_YAML_TEMPLATE.format(
            name=p,
            label=f"param_{p}",
            unit="year",
            description=f"Parameter {p} of the {display_name} distribution",
            bound_min=0.1,
            bound_max=100.0,
            init=10.0 if i == 0 else 2.0,
            step=1.0,
            prior_min=0.0,
            prior_max=100.0,
        ))

    yaml_content = LPM_YAML_TEMPLATE.format(
        registry_name=registry_name,
        date=datetime.now().strftime("%Y-%m-%d"),
        param_yaml="\n".join(param_yaml_parts),
    )

    # Write files
    python_file = get_lpm_models_dir() / f"LPM_{registry_name}.py"
    yaml_dir = get_lpm_data_dir() / registry_name
    yaml_file = yaml_dir / "params.yaml"

    # Check if files already exist
    if python_file.exists():
        raise FileExistsError(f"LPM Python file already exists: {python_file}")
    if yaml_file.exists():
        raise FileExistsError(f"LPM YAML file already exists: {yaml_file}")

    # Create directories and files
    yaml_dir.mkdir(parents=True, exist_ok=True)

    python_file.write_text(python_content, encoding="utf-8")
    yaml_file.write_text(yaml_content, encoding="utf-8")

    # Check for reserved words and warn
    reserved_used = [p for p in params if p in PYTHON_RESERVED_WORDS]

    return {
        "python_file": python_file,
        "yaml_file": yaml_file,
        "registry_name": registry_name,
        "class_name": class_name,
        "reserved_words_warning": reserved_used if reserved_used else None,
    }


# =============================================================================
# Tracer Template Generation
# =============================================================================

TRACER_YAML_TEMPLATE = '''# {name_upper} Tracer Configuration
#
# This file configures the {name} tracer for groundwater age dating.
#
# Created: {date}
# Author: [Your name]

# =============================================================================
# Tracer Properties
# =============================================================================

# Unit of concentration measurement
# Common options: pptv, TU, pmC, Bq/L, atoms/L
unit: {unit}

# =============================================================================
# Recharge Configuration
# =============================================================================

# Enable recharge chronicle from external file
# If true, concentrations are loaded from recharge.csv in the same directory
recharge: {has_recharge}
{recharge_constant_line}
# =============================================================================
# Optional: Radioactive Decay
# =============================================================================
{decay_section}
# =============================================================================
# Optional: Geoproduction
# =============================================================================
{production_section}
# =============================================================================
# Valid Date Range (only needed if recharge: false)
# =============================================================================
{date_range_section}
'''


TRACER_CSV_TEMPLATE = '''# ============================================================================
# {name_upper} Atmospheric Recharge Chronicle
# ============================================================================
#
# Tracer: {name}
# Unit: {unit}
#
# Data Source: [Add your data source]
# Reference: [Add reference URL or citation]
#
# Temporal Coverage: {date_start} - {date_end}
# Number of Records: {n_records}
#
# Notes:
# - [Add any relevant notes about the data]
#
# Column Descriptions:
#   date: Decimal year (e.g., 2020.5 = July 1, 2020)
#   concentration: Atmospheric concentration in {unit}
#
# Last Updated: {date}
# ============================================================================
date,concentration
{sample_data}
'''


def generate_tracer(
    name: str,
    unit: str = "pptv",
    has_decay: bool = False,
    has_production: bool = False,
    has_recharge: bool = True,
) -> dict:
    """
    Generate tracer template files.

    Parameters
    ----------
    name : str
        Tracer name (e.g., 'argon39', 'krypton85')
    unit : str
        Concentration unit (default: 'pptv')
    has_decay : bool
        Include radioactive decay section
    has_production : bool
        Include geoproduction section
    has_recharge : bool
        Use recharge chronicle (vs constant)

    Returns
    -------
    dict
        Paths to generated files
    """
    # Normalize name
    tracer_name = name.lower().replace("-", "_")
    name_upper = name.upper().replace("_", "-")

    # Build optional sections
    if has_decay:
        decay_section = '''
# Decay characteristic time in years (half-life / ln(2))
# Example: Tritium has half-life 12.32 years -> decay_time = 17.77
decay_time: 10.0  # TODO: Set the correct decay time
'''
    else:
        decay_section = '''# Uncomment to enable radioactive decay
# decay_time: 10.0
'''

    if has_production:
        production_section = '''
# In-situ production rate (concentration units per year)
production_rate: 0.0  # TODO: Set the correct production rate
'''
    else:
        production_section = '''# Uncomment to enable geoproduction
# production_rate: 0.0
'''

    if has_recharge:
        recharge_constant_line = "# recharge_constant: 0.0  # Only used if recharge: false\n"
        date_range_section = "# Date range is automatically determined from recharge.csv"
    else:
        recharge_constant_line = "recharge_constant: 100.0  # Constant recharge concentration\n"
        date_range_section = '''datemin: 1940.0
datemax: 2025.0'''

    yaml_content = TRACER_YAML_TEMPLATE.format(
        name=tracer_name,
        name_upper=name_upper,
        date=datetime.now().strftime("%Y-%m-%d"),
        unit=unit,
        has_recharge=str(has_recharge).lower(),
        recharge_constant_line=recharge_constant_line,
        decay_section=decay_section,
        production_section=production_section,
        date_range_section=date_range_section,
    )

    # Generate sample CSV data
    sample_dates = [1940.0, 1950.0, 1960.0, 1970.0, 1980.0, 1990.0, 2000.0, 2010.0, 2020.0]
    sample_conc = [0.0, 10.0, 50.0, 100.0, 150.0, 180.0, 200.0, 210.0, 215.0]
    sample_data = "\n".join([f"{d},{c}" for d, c in zip(sample_dates, sample_conc)])

    csv_content = TRACER_CSV_TEMPLATE.format(
        name=tracer_name,
        name_upper=name_upper,
        unit=unit,
        date_start=sample_dates[0],
        date_end=sample_dates[-1],
        n_records=len(sample_dates),
        date=datetime.now().strftime("%Y-%m-%d"),
        sample_data=sample_data,
    )

    # Create directory and files
    tracer_dir = get_tracer_data_dir() / tracer_name
    yaml_file = tracer_dir / f"{tracer_name}.yaml"
    csv_file = tracer_dir / "recharge.csv"

    # Check if files already exist
    if yaml_file.exists():
        raise FileExistsError(f"Tracer YAML file already exists: {yaml_file}")
    if csv_file.exists() and has_recharge:
        raise FileExistsError(f"Tracer CSV file already exists: {csv_file}")

    # Write files
    tracer_dir.mkdir(parents=True, exist_ok=True)

    yaml_file.write_text(yaml_content, encoding="utf-8")
    if has_recharge:
        csv_file.write_text(csv_content, encoding="utf-8")

    result = {
        "yaml_file": yaml_file,
        "tracer_name": tracer_name,
    }
    if has_recharge:
        result["csv_file"] = csv_file

    return result


# =============================================================================
# CLI Interface
# =============================================================================

def print_success_lpm(result: dict) -> None:
    """Print success message for LPM creation."""
    warning = ""
    if result.get("reserved_words_warning"):
        words = ", ".join(result["reserved_words_warning"])
        warning = f"""
Note: Parameter names [{words}] are Python reserved words.
      They have been renamed with a trailing underscore in the code
      (e.g., 'lambda' -> 'lambda_' in function arguments).
      The YAML file uses the original names.
"""
    print(f"""
{'='*60}
  LPM '{result['registry_name']}' created successfully!
{'='*60}

Files created:
  - Python: {result['python_file']}
  - YAML:   {result['yaml_file']}
{warning}
Next steps:
  1. Edit the Python file to configure:
     - scipy_dist: Choose the correct scipy.stats distribution
     - _scipy_params(): Map your parameters to scipy's (args, loc, scale)

  2. Edit the YAML file to set:
     - Parameter bounds (physically meaningful ranges)
     - Initial values for calibration
     - MCMC step sizes

  3. Test your LPM:
     >>> from LPM.lpm_build import lpm_build
     >>> lpm = lpm_build("{result['registry_name']}")
     >>> print(lpm.pdf(10.0))

  4. Run system check:
     python scripts/run_system_check.py
""")


def print_success_tracer(result: dict) -> None:
    """Print success message for tracer creation."""
    csv_info = f"\n  - CSV:  {result['csv_file']}" if "csv_file" in result else ""
    print(f"""
{'='*60}
  Tracer '{result['tracer_name']}' created successfully!
{'='*60}

Files created:
  - YAML: {result['yaml_file']}{csv_info}

Next steps:
  1. Edit the YAML file to configure:
     - unit: Concentration unit
     - decay_time: If radioactive tracer
     - production_rate: If in-situ production

  2. Replace recharge.csv with your actual data:
     - Column 1: decimal year (e.g., 2020.5)
     - Column 2: concentration in your chosen unit

  3. Test your tracer:
     >>> from tracer.tracer_root import Tracer, find_tracer_dir
     >>> tracer = Tracer(find_tracer_dir(), name="{result['tracer_name']}")
     >>> print(tracer.get_concentration(date=2010.0, time=20.0))

  4. Run system check:
     python scripts/run_system_check.py
""")


def main():
    """Main CLI entry point."""
    parser = argparse.ArgumentParser(
        description="Generate templates for new PyAge components",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  %(prog)s lpm weibull --params k,lambda --scipy weibull_min
  %(prog)s lpm lognormal --params mu,sigma --scipy lognorm
  %(prog)s tracer argon39 --unit "atoms/L"
  %(prog)s tracer tritium --unit TU --decay
        """
    )

    subparsers = parser.add_subparsers(dest="component", help="Component type")

    # LPM subcommand
    lpm_parser = subparsers.add_parser("lpm", help="Create a new LPM model")
    lpm_parser.add_argument("name", help="LPM model name (e.g., 'weibull')")
    lpm_parser.add_argument(
        "--params", "-p",
        default="mu,sigma",
        help="Comma-separated parameter names (default: mu,sigma)"
    )
    lpm_parser.add_argument(
        "--scipy", "-s",
        default="norm",
        help="Scipy distribution name (default: norm)"
    )

    # Tracer subcommand
    tracer_parser = subparsers.add_parser("tracer", help="Create a new tracer")
    tracer_parser.add_argument("name", help="Tracer name (e.g., 'argon39')")
    tracer_parser.add_argument(
        "--unit", "-u",
        default="pptv",
        help="Concentration unit (default: pptv)"
    )
    tracer_parser.add_argument(
        "--decay", "-d",
        action="store_true",
        help="Enable radioactive decay"
    )
    tracer_parser.add_argument(
        "--production", "-g",
        action="store_true",
        help="Enable geoproduction"
    )
    tracer_parser.add_argument(
        "--no-recharge",
        action="store_true",
        help="Use constant recharge instead of chronicle"
    )

    args = parser.parse_args()

    if args.component is None:
        parser.print_help()
        sys.exit(1)

    try:
        if args.component == "lpm":
            params = [p.strip() for p in args.params.split(",")]
            result = generate_lpm(args.name, params, args.scipy)
            print_success_lpm(result)

        elif args.component == "tracer":
            result = generate_tracer(
                args.name,
                unit=args.unit,
                has_decay=args.decay,
                has_production=args.production,
                has_recharge=not args.no_recharge,
            )
            print_success_tracer(result)

    except FileExistsError as e:
        print(f"\nError: {e}")
        print("Use a different name or delete the existing files first.")
        sys.exit(1)
    except Exception as e:
        print(f"\nError: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
