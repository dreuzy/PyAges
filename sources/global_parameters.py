# -*- coding: utf-8 -*-
"""
Created on Tue Mar 23 21:20:39 2021

@author: dreuzy
"""

from datetime import datetime
import matplotlib.pyplot as plt
import numpy as np
import os
import sys
import time
from pathlib import Path

# -------------------------------------------------------
# Root directories
# -------------------------------------------------------

# Root Directory of Results
ROOT_DIRECTORY_RESULTS = next(
    (p for p in [Path("D:/results/PyAge"), Path("C:/results/PyAge")] if p.exists()),
    None
)

# Root Directory of Application
ROOT_DIRECTORY_SRC = next(
    (p for p in [Path("D:/codes/pyage/sources"), Path("C:/codes/pyage/sources")] if p.exists()),
    None
)

if ROOT_DIRECTORY_RESULTS is None:
    raise FileNotFoundError("No ROOT_DIRECTORY_RESULTS found")
if ROOT_DIRECTORY_SRC is None:
    raise FileNotFoundError("No ROOT_DIRECTORY_SRC found")

# -------------------------------------------------------
# Sub-directories (conserving same variable names)
# -------------------------------------------------------

DIRECTORY_TRACER_DATA = ROOT_DIRECTORY_SRC / "tracer_data"
DIRECTORY_TEST = ROOT_DIRECTORY_SRC / "tests_data"
directory_lpm_data = ROOT_DIRECTORY_SRC / "LPM_data"

# -------------------------------------------------------
# Global parameters
# -------------------------------------------------------

RESOLUTION_CONVOLUTION = 200

REFERENCE_COLUMNS = ["element", "concentration", "error", "unit", "date"]
CONCENTRATION = REFERENCE_COLUMNS.index("concentration")
ERROR = REFERENCE_COLUMNS.index("error")

# -------------------------------------------------------
# Utility functions
# -------------------------------------------------------

def results_directory(directory, sub_directory):
    """Create sub-directory if necessary and return its path."""
    path = Path(directory) / sub_directory
    path.mkdir(parents=True, exist_ok=True)
    return path

def name_dhms():
    """Return a timestamp string (year_month_day-hour_minute_second)."""
    now = datetime.now()
    return now.strftime("%Y_%m_%d-%H_%M_%S")

def results_directory_dhms(sub_directory, directory=ROOT_DIRECTORY_RESULTS):
    """Create dated sub-directory under directory/sub_directory."""
    base = results_directory(directory, sub_directory)
    return results_directory(base, sub_directory)

# -------------------------------------------------------
# Classes
# -------------------------------------------------------


import warnings
from pathlib import Path
import matplotlib.pyplot as plt

class display_options:
    """Display options for the tests."""
    def __init__(self):
        self.text = False
        self.figure = False
        self.figure_close = True
        self.figure_save = False
        self.directory = None

    def save_and_close(self, fig, filename, method="", dpi=300, ax=None):
        """
        Sauvegarde et ferme une figure matplotlib, avec gestion robuste
        des warnings liés à tight_layout et legend(loc="best").
        """
        filepath = Path(self.directory) / method / filename
        filepath.parent.mkdir(parents=True, exist_ok=True)

        # Gestion de la légende si un axe est fourni
        if ax is not None:
            try:
                ax.legend(loc="best", fontsize=8)
            except Exception:
                # fallback si beaucoup de données
                ax.legend(loc="upper right", fontsize=8)

        # Application de tight_layout avec fallback
        try:
            with warnings.catch_warnings(record=True) as wlist:
                warnings.simplefilter("always")
                fig.tight_layout()
                for w in wlist:
                    if "Tight layout not applied" in str(w.message):
                        # fallback : ajustement manuel
                        fig.subplots_adjust(top=0.9, bottom=0.1, hspace=0.4)
        except Exception:
            fig.subplots_adjust(top=0.9, bottom=0.1, hspace=0.4)

        # Sauvegarde robuste
        try:
            fig.savefig(filepath, dpi=dpi)
            print(f"✅ Figure sauvegardée : {filepath}")
        except Exception as e:
            print(f"❌ Erreur lors de la sauvegarde : {e}")

        # Fermeture mémoire
        if self.figure_close:
            plt.close(fig)


    def figure_close_fx(self, filename):
        if self.figure_save and self.directory is not None:
            plt.savefig(Path(self.directory) / filename, dpi=300)
        if self.figure_close:
            plt.close("all")

def arange_n(pmin, pmax, n):
    """Regular sampling between pmin and pmax with n elements (including endpoints)."""
    return pmin + (pmax - pmin) * np.arange(0, n + 1) / n

class simulation_time:
    """Elapsed and remaining times of simulation."""
    def __init__(self, nsim=1):
        self.simul_total = nsim
        self.time_start = 0
        self.time_inter_start = 0
        self.time_inter_end = 0
        self.simul_current = 0
        self.init_yes = False

    def initialize(self, nb):
        if not self.init_yes:
            self.time_start = time.time()
            self.time_inter_start = time.time()
            self.simul_total = nb * self.simul_total
            self.init_yes = True

    def actualize(self, nb=1):
        self.time_inter_end = time.time()
        self.simul_current += nb
        print("time elapsed =", (self.time_inter_end - self.time_start) / 3600, "hours")
        print(
            "time remaining =",
            (self.time_inter_end - self.time_start)
            * (self.simul_total / self.simul_current - 1)
            / 3600,
            "hours",
        )

# -------------------------------------------------------
# Path setup
# -------------------------------------------------------

def setup_path():
    """Adds to sys.path the source directory and its subdirectories."""
    for dir_path in ROOT_DIRECTORY_SRC.iterdir():
        if dir_path.is_dir():
            sys.path.insert(0, str(dir_path))
