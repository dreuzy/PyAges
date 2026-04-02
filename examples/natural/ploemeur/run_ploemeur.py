# -*- coding: utf-8 -*-
"""
Launcher for the workflow.
"""

import sys
from pathlib import Path
import subprocess
import runpy

# Repository root is three levels up from this file (examples/natural/ploemeur/)
REPO_ROOT = Path(__file__).resolve().parents[3]


def main():
    root = REPO_ROOT
    script = root / "scripts" / "launcher.py"
    params = root / "examples" / "natural" / "ploemeur" / "exemple_ploemeur.yaml"
    try:
        from IPython import get_ipython
        ipy = get_ipython()
    except Exception:
        ipy = None
    if ipy is not None:
        sys.path.insert(0, str(root / "scripts"))
        sys.argv = [str(script), str(params), "--inline"]
        runpy.run_path(str(script), run_name="__main__")
    else:
        subprocess.run(
            [sys.executable, str(script), str(params)],
            check=True,
        )


if __name__ == "__main__":
    main()
