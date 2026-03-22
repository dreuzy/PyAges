# -*- coding: utf-8 -*-
"""
Launcher for the workflow.
"""

import sys
from pathlib import Path
import subprocess
import runpy

# Repository root is two levels up from this file (examples/albuquerque/)
REPO_ROOT = Path(__file__).resolve().parents[2]


def main():
    root = REPO_ROOT
    script = root / "scripts" / "launcher.py"
    params = root / "examples" / "albuquerque" / "exemple_albuquerque.yaml"
    try:
        from IPython import get_ipython
        ipy = get_ipython()
    except Exception:
        ipy = None
    if ipy is not None:
        sys.path.insert(0, str(root / "scripts"))
        sys.argv = [str(script), str(params), "--inline", "--set-results-dir"]
        runpy.run_path(str(script), run_name="__main__")
    else:
        subprocess.run(
            [sys.executable, str(script), str(params), "--set-results-dir"],
            check=True,
        )


if __name__ == "__main__":
    main()
