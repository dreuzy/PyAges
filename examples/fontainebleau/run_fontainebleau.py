# -*- coding: utf-8 -*-
"""
Launcher for the Fontainebleau workflow.
"""

import sys
from pathlib import Path
import subprocess
import runpy


def find_repo_root():
    """Return repo root by walking up until 'sources' exists."""
    root = Path.cwd()
    if not (root / "sources").exists():
        for parent in root.parents:
            if (parent / "sources").exists():
                root = parent
                break
    return root


def main():
    root = find_repo_root()
    script = root / "scripts" / "launcher.py"
    params = root / "examples" / "fontainebleau" / "exemple_fontainebleau.yaml"
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
