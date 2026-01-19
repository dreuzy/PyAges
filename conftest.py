import json
import sys
from pathlib import Path

import pytest

# ---------------------------------------------------------------------------
# 1) Localisation du projet + ajout de "sources/" au PYTHONPATH des tests
# ---------------------------------------------------------------------------

# REPO_ROOT = dossier où se trouve ce fichier conftest.py (généralement la racine du repo)
REPO_ROOT = Path(__file__).resolve().parent

# Dossier contenant le code du projet (à adapter si ton projet utilise "src/" au lieu de "sources/")
SRC_DIR = REPO_ROOT / "sources"

# sys.path = liste des dossiers dans lesquels Python cherche les modules à importer.
# Ici on ajoute "sources/" au début pour que les imports du projet fonctionnent dans les tests,
# même si le projet n'est pas installé comme un package (pip install -e .).
if SRC_DIR.exists() and str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))


# ---------------------------------------------------------------------------
# 2) Emplacement du fichier "golden" (valeurs de référence)
# ---------------------------------------------------------------------------

# Le fichier JSON où l'on stocke les valeurs de référence (golden values).
# Exemple de contenu:
# {
#   "cfc11:date=2001.0,time=25.0": 0.002347891234
# }
GOLDEN_PATH = REPO_ROOT / "tests" / "golden" / "tracer_values.json"


# ---------------------------------------------------------------------------
# 3) Ajout d'une option de ligne de commande à pytest
# ---------------------------------------------------------------------------

def pytest_addoption(parser):
    """
    Hook pytest: permet d'ajouter des options à la commande `pytest ...`.

    Ici on ajoute:
      --update-golden

    Usage:
      pytest --update-golden
    """
    parser.addoption(
        "--update-golden",
        action="store_true",     # option booléenne: présente => True, absente => False
        default=False,
        help="Update golden reference values instead of asserting.",
    )


# ---------------------------------------------------------------------------
# 4) Fixtures: accès aux options et aux données golden dans les tests
# ---------------------------------------------------------------------------

@pytest.fixture
def update_golden(request) -> bool:
    """
    Fixture pytest qui expose le booléen update_golden aux tests.

    Dans un test:
      def test_x(update_golden):
          if update_golden:
              ... # mode mise à jour
          else:
              ... # mode comparaison
    """
    return bool(request.config.getoption("--update-golden"))


@pytest.fixture
def golden_store() -> dict:
    """
    Fixture pytest qui charge (au début d'un test) le fichier JSON des valeurs golden.

    - Crée le dossier tests/golden/ s'il n'existe pas
    - Si le fichier JSON n'existe pas, renvoie {}
    - Si le JSON est invalide (fichier corrompu ou édité à la main avec une erreur),
      on lève une erreur "UsageError" pytest (message clair et arrêt).
    """
    # S'assure que le dossier existe (même s'il est vide)
    GOLDEN_PATH.parent.mkdir(parents=True, exist_ok=True)

    # Aucun fichier => aucune référence => dictionnaire vide
    if not GOLDEN_PATH.exists():
        return {}

    # Si le fichier existe, on tente de le parser en JSON
    try:
        return json.loads(GOLDEN_PATH.read_text(encoding="utf-8"))
    except json.JSONDecodeError as e:
        # UsageError est une erreur "de configuration/usage" plus parlante qu'un traceback brut
        raise pytest.UsageError(
            f"Golden file is not valid JSON: {GOLDEN_PATH}\n{e}"
        )


# ---------------------------------------------------------------------------
# 5) Fonction utilitaire: sauvegarder les valeurs golden de manière sûre
# ---------------------------------------------------------------------------

def save_golden_store(store: dict) -> None:
    """
    Écrit le dictionnaire `store` dans le fichier GOLDEN_PATH.

    On écrit de façon "atomique":
      1) on écrit d'abord dans un fichier temporaire *.tmp
      2) puis on remplace le fichier final

    Avantage: si le processus est interrompu pendant l'écriture, tu évites d'avoir
    un tracer_values.json partiellement écrit/corrompu.
    """
    # S'assure que le dossier existe au moment de la sauvegarde
    GOLDEN_PATH.parent.mkdir(parents=True, exist_ok=True)

    # Chemin temporaire
    tmp_path = GOLDEN_PATH.with_suffix(GOLDEN_PATH.suffix + ".tmp")

    # On sérialise en JSON "lisible" (indentation) avec clés triées (sort_keys=True)
    tmp_path.write_text(
        json.dumps(store, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )

    # Remplace le fichier final par le fichier tmp (opération atomique sur la plupart des OS)
    tmp_path.replace(GOLDEN_PATH)
