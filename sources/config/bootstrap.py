# -*- coding: utf-8 -*-
"""
Bootstrap helpers (path setup).
"""

import sys

from config.paths import ROOT_DIRECTORY_SRC


def setup_path():
    """Adds to sys.path the source directory and its subdirectories."""
    for dir_path in ROOT_DIRECTORY_SRC.iterdir():
        if dir_path.is_dir():
            sys.path.insert(0, str(dir_path))
