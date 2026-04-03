# -*- coding: utf-8 -*-
"""Launcher for the temporal Ploemeur example."""

import runpy
import subprocess
import sys
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[3]


def main():
    root = REPO_ROOT
    script = root / "scripts" / "launcher_temporal.py"
    params = root / "examples" / "natural" / "ploemeur_temporal" / "ploemeur_temporal.yaml"
    try:
        from IPython import get_ipython

        ipy = get_ipython()
    except Exception:
        ipy = None
    if ipy is not None:
        sys.path.insert(0, str(root))
        sys.argv = [str(script), "--params", str(params)]
        runpy.run_path(str(script), run_name="__main__")
    else:
        subprocess.run(
            [sys.executable, str(script), "--params", str(params)],
            check=True,
        )


if __name__ == "__main__":
    main()
