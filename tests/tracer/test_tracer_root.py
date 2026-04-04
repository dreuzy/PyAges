"""
tests/tracer/test_tracer_root.py (ou test_tracer_concentration.py)

Fichier de tests pytest pour la classe Tracer.

Ce fichier illustre trois "niveaux" de tests utiles en calcul scientifique :

1) Tests de cohérence / "smoke tests"
   - Le code s'initialise
   - Les propriétés sont définies
   - Les sorties sont des nombres finis (pas NaN, pas inf)

2) Tests de comportement attendu en cas d'usage non supporté
   - Vérifier qu'une exception est levée (ex: ValueError)

3) Test "golden" (valeur de référence / non-régression)
   - On compare une valeur calculée à une valeur de référence stockée dans un fichier JSON
   - Option pytest --update-golden : recalcule et met à jour les valeurs de référence

Prérequis :
- Un conftest.py à la racine du repo (C:\\codes\\pyage\\conftest.py) qui définit :
  - l'option --update-golden
  - les fixtures update_golden et golden_store
  - la fonction save_golden_store(store)
- Un fichier de références (golden) :
  tests/golden/tracer_values.json
"""

from pathlib import Path
import math

import pytest

# Import du code à tester
from pyage.tracer.tracer_root import Tracer

# Fonction utilitaire de sauvegarde des golden values
# NOTE: importer depuis conftest.py marche, mais à long terme il est souvent plus propre
#       de placer cette fonction dans tests/utils_golden.py et d'importer depuis là.
from conftest import save_golden_store


# ---------------------------------------------------------------------------
# Utilitaire : localiser les données de tests
# ---------------------------------------------------------------------------

def _data_tracer_dir() -> Path:
    """
    Renvoie le chemin vers le dossier contenant les données nécessaires aux tests.

    Hypothèse d'arborescence (exemple) :
      <repo_root>/
        conftest.py
        pyage/
          ...
        data_core/
          data_tracer/
        tests/
          tracer/
            test_tracer_root.py

    __file__ = chemin du fichier de test courant.
    parents[2] remonte de :
      - parents[0] : dossier du fichier (ex: tests/tracer)
      - parents[1] : tests
      - parents[2] : racine du repo

    On construit ensuite : <repo_root>/data_core/data_tracer
    """
    return Path(__file__).resolve().parents[2] / "data_core" / "data_tracer"


def _tracer_names(exclude=None) -> list[str]:
    """
    Liste les traceurs disponibles (sous-dossiers avec YAML) en excluant certains.
    """
    tracer_dir = _data_tracer_dir()
    exclude_set = set(exclude or [])
    names = []
    for item in tracer_dir.iterdir():
        if not item.is_dir():
            continue
        yaml_file = item / f"{item.name}.yaml"
        if yaml_file.exists() and item.name not in exclude_set:
            names.append(item.name)
    return sorted(names)


# ---------------------------------------------------------------------------
# Tests de cohérence (smoke tests)
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("tracer_name", _tracer_names(exclude=["NO3"]))
def test_tracer_smoke_all(tracer_name):
    """
    Smoke test minimal pour tous les traceurs (sauf NO3).
    """
    tracer_dir = _data_tracer_dir()
    tracer = Tracer(tracer_dir, name=tracer_name)

    assert tracer.name == tracer_name
    assert tracer.unit != ""
    assert tracer.datemin < tracer.datemax

    value = tracer.get_concentration(date=2000.0, time=10.0)
    assert math.isfinite(float(value))

    try:
        max_val = tracer.max_value()
        assert math.isfinite(max_val)
    except ValueError:
        pass


def test_tracer_chronicle_cfc11_basics():
    """
    Test "smoke" sur un traceur de type chronique (ex: cfc11).

    Objectif :
    - vérifier que l'objet Tracer s'initialise correctement
    - vérifier que quelques attributs essentiels sont cohérents
    - vérifier que les méthodes principales retournent des valeurs numériques finies

    Ce test NE garantit pas la validité scientifique fine :
    il valide surtout "ça marche" et "les sorties sont raisonnables".
    """
    tracer_dir = _data_tracer_dir()
    tracer = Tracer(tracer_dir, name="cfc11")

    # --- attributs de base ---
    assert tracer.name == "cfc11"

    # On s'attend à ce que l'unité soit renseignée (sinon données/propriétés incomplètes)
    assert tracer.unit != ""

    # La plage de dates doit être cohérente
    assert tracer.datemin < tracer.datemax

    # --- sorties numériques : doivent être finies ---
    # On force float(value) car get_concentration peut renvoyer un numpy scalar
    value = tracer.get_concentration(date=2010.0, time=20.0)
    assert math.isfinite(float(value))

    # Valeur moyenne (sur une année par exemple)
    mean_val = tracer.mean_value(2010.0)
    assert math.isfinite(mean_val)

    # Valeur max globale
    max_val = tracer.max_value()
    assert math.isfinite(max_val)

    # Hypothèse métier : la concentration ne devrait pas être négative
    # (à ajuster si, dans ton modèle, des valeurs négatives peuvent exister)
    assert max_val >= 0


def test_tracer_constant_recharge_so4():
    """
    Test "smoke" + test d'exception sur un traceur de type "recharge constante" (SO4).

    Objectif :
    - get_concentration doit fonctionner et renvoyer une valeur finie
    - max_value n'est peut-être pas défini pour ce type -> on vérifie qu'il lève ValueError
    """
    tracer_dir = _data_tracer_dir()
    tracer = Tracer(tracer_dir, name="SO4")

    value = tracer.get_concentration(date=2000.0, time=10.0)
    assert math.isfinite(float(value))

    # Ici, on teste un comportement "d'erreur attendue" :
    # max_value() n'a pas de sens pour ce traceur, donc on veut une exception.
    with pytest.raises(ValueError):
        tracer.max_value()


def test_tracer_allows_metadata_block(tmp_path):
    tracer_dir = tmp_path / "data_tracer"
    tracer_name = "meta_tracer"
    tracer_path = tracer_dir / tracer_name
    tracer_path.mkdir(parents=True)
    (tracer_path / f"{tracer_name}.yaml").write_text(
        "\n".join(
            [
                "unit: TU",
                "recharge_constant: 1.0",
                "decay_time: 12.32",
                "datemin: 1950.0",
                "datemax: 2021.0",
                "metadata:",
                "  reference: local test",
                "  notes: keep for example workflows",
                "",
            ]
        ),
        encoding="utf-8",
    )

    tracer = Tracer(tracer_dir, name=tracer_name)

    assert tracer.unit == "TU"
    assert tracer.datemin == 1950.0
    assert tracer.datemax == 2021.0


# ---------------------------------------------------------------------------
# Test Golden (valeur de référence / non-régression)
# ---------------------------------------------------------------------------

def _golden_key(tracer_name: str, date: float, time: float) -> str:
    """
    Construit une clé stable pour indexer une valeur de référence dans le JSON.

    Exemple :
      "cfc11:date=2001.0,time=25.0"

    Le but est d'éviter toute ambiguïté et d'avoir une clé "copiable" et stable.
    """
    return f"{tracer_name}:date={date},time={time}"


@pytest.mark.parametrize("tracer_name", _tracer_names(exclude=["NO3"]))
def test_tracer_get_concentration_golden(tracer_name, update_golden, golden_store):
    """
    Test golden pour get_concentration sur un point précis (date, time).

    Deux modes :

    - Mode normal (sans option) :
        On compare la valeur calculée à la valeur de référence stockée dans
        tests/golden/tracer_values.json, sous une clé stable.

    - Mode mise à jour (avec --update-golden) :
        On recalcule la valeur et on l'écrit dans le JSON,
        puis on "skip" le test (on ne compare pas).

    Pourquoi "skip" en mode update ?
      - On veut rendre explicite l'intention : "je mets à jour la référence".
      - On évite de mélanger mise à jour et validation dans la même exécution.
    """
    tracer_dir = _data_tracer_dir()
    tracer = Tracer(tracer_dir, name=tracer_name)

    # Paramètres du point de test : doit être stable et reproductible
    date = 0.5 * (tracer.datemin + tracer.datemax)
    time = min(10.0, max(0.0, date - tracer.datemin))

    # Valeur calculée
    value = float(tracer.get_concentration(date=date, time=time))

    # Clé de stockage/retrieval dans le golden store
    key = _golden_key(tracer_name, date, time)

    # Affiche une valeur "copiable" si tu veux l'observer dans la console
    # (utile pour debug / validation manuelle)
    print(f"[golden] {key} = {value:.12e}")

    if update_golden:
        # --- Mode mise à jour ---
        golden_store[key] = value
        save_golden_store(golden_store)

        # On ne "valide" pas ici : on signale seulement que la référence a été mise à jour.
        pytest.skip(f"Golden updated: {key} = {value:.12e}")
    else:
        # --- Mode comparaison ---
        # Si la référence n'existe pas encore, on force l'utilisateur à la générer
        # plutôt que de laisser le test passer sans vérifier quoi que ce soit.
        if key not in golden_store:
            pytest.fail(
                f"Golden value missing for {key}. "
                f"Run: pytest -s --update-golden"
            )

        expected = float(golden_store[key])

        # Comparaison tolérante pour flottants.
        # rel = tolérance relative, abs = tolérance absolue.
        print(f"[golden] comparing {key}: computed={value:.12e} expected={expected:.12e}")
        assert value == pytest.approx(expected, rel=1e-6, abs=1e-6)
