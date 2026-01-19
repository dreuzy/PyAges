"""
Script utilitaire pour lancer les tests pytest depuis la racine du projet.

Usage :
  python run_tests.py           -> mode normal (comparaison des golden)
  python run_tests.py update    -> mise à jour des golden (--update-golden)
"""

import subprocess
import sys


def main():
    # Commande de base
    cmd = ["pytest", "-v", "tests"]

    # Si l'utilisateur passe "update" en argument
    if len(sys.argv) > 1 and sys.argv[1] == "update":
        cmd = ["pytest", "-v", "-s", "--update-golden", "tests"]

    print("Running:", " ".join(cmd))
    print("-" * 60)

    # Lance pytest et propage le code de retour
    result = subprocess.run(cmd)
    sys.exit(result.returncode)


if __name__ == "__main__":
    main()
