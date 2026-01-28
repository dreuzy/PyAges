# -*- coding: utf-8 -*-
"""
Created on Tue Mar 23 21:20:39 2021

@author: Jean-Raynald de Dreuzy

Global parameters and re-exports used across the codebase.
Includes model/data constants and forwards config helpers from config.*
to keep call sites stable.
"""

import os
from pathlib import Path

import numpy as np

from config.paths import (
    ROOT_DIRECTORY,
    ROOT_DIRECTORY_RESULTS,
    ROOT_DIRECTORY_SRC,
    DIRECTORY_TRACER_DATA,
    DIRECTORY_TEST,
    DIRECTORY_LPM_DATA,
    results_directory,
    name_dhms,
)

from config.runtime import display_options, simulation_time, arange_n

# -------------------------------------------------------
# Global parameters (model/data constants)
# -------------------------------------------------------

# Default resolution for convolutions
RESOLUTION_CONVOLUTION = 200

# Reference column names for concentration datasets
REFERENCE_COLUMNS = ["element", "concentration", "error", "unit", "date"]
CONCENTRATION = REFERENCE_COLUMNS.index("concentration")
ERROR = REFERENCE_COLUMNS.index("error")
