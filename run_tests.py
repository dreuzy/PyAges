"""
Script utilitaire pour lancer les tests pytest depuis la racine du projet.

Usage :
  python run_tests.py               -> mode normal (synthèse)
  python run_tests.py update        -> mise à jour des golden (--update-golden)
  python run_tests.py detail        -> affichage détaillé (-vv)
  python run_tests.py update detail -> combine update + détail
"""

import argparse
import subprocess
import sys


def main():
    parser = argparse.ArgumentParser(description="Run pytest for this project.")
    parser.add_argument(
        "mode",
        nargs="*",
        help="Optional modes: update, detail",
    )
    args = parser.parse_args()

    update = "update" in args.mode
    detail = "detail" in args.mode

    # Commande de base (synthèse)
    cmd = [sys.executable, "-m", "pytest", "-q", "tests"]

    if detail:
        cmd = [sys.executable, "-m", "pytest", "-vv", "tests"]

    if update:
        cmd = cmd[:2] + ["-s", "--update-golden"] + cmd[2:]

    print("Running:", " ".join(cmd))
    print("-" * 60)

    # Lance pytest et propage le code de retour
    result = subprocess.run(cmd)
    sys.exit(result.returncode)


if __name__ == "__main__":
    main()
