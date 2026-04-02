# -*- coding: utf-8 -*-
"""Run the temporal MH launcher with a local YAML config."""

from pathlib import Path
import subprocess
import sys


def main():
    root = Path(__file__).resolve().parents[3]
    params = root / "examples" / "natural" / "ploemeur_temporal" / "ploemeur_temporal.yaml"
    script = root / "scripts" / "launcher_temporal.py"
    subprocess.run([sys.executable, str(script), "--params", str(params)], check=True)


if __name__ == "__main__":
    main()
