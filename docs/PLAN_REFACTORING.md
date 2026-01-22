# Plan de Refactoring PyAge

## Objectifs

1. **Maintenabilité** : Réduire le code dupliqué, clarifier l'architecture
2. **Extensibilité** : Faciliter l'ajout de nouveaux sites/puits/traceurs
3. **Robustesse** : Améliorer la gestion des erreurs et les tests
4. **Performance** : Optimisations ciblées sans casser l'existant

## État actuel (structure révisée)

- `sources/` contient désormais `convolution/` (singulier), `concentrations/`,
  `calibration/{methods,utils,workflows}` et `config/`.
- `core_data/` regroupe les données LPM et traceurs (données “core”).
- `sites/ploemeur/` reste le site principal.
- `examples/` contient les scénarios et données de démonstration (fontainebleau, ploemeur).

---

## Vue d'Ensemble des Phases

```
┌─────────────────────────────────────────────────────────────────────────┐
│  PHASE 0 : PRÉPARATION (1-2 jours)                                      │
│  Tests de caractérisation + golden references                           │
└─────────────────────────────────────────────────────────────────────────┘
                                    │
                                    ▼
┌─────────────────────────────────────────────────────────────────────────┐
│  PHASE 1 : CONFIGURATION EXTERNALISÉE (2-3 jours)                       │
│  wells_config.yaml + refactoring selector()                             │
└─────────────────────────────────────────────────────────────────────────┘
                                    │
                                    ▼
┌─────────────────────────────────────────────────────────────────────────┐
│  PHASE 2 : GESTION DES ERREURS (1-2 jours)                              │
│  Exceptions personnalisées + suppression sys.exit()                     │
└─────────────────────────────────────────────────────────────────────────┘
                                    │
                                    ▼
┌─────────────────────────────────────────────────────────────────────────┐
│  PHASE 3 : LOGGING ET MONITORING (1 jour)                               │
│  Système de logging structuré                                           │
└─────────────────────────────────────────────────────────────────────────┘
                                    │
                                    ▼
┌─────────────────────────────────────────────────────────────────────────┐
│  PHASE 4 : SÉPARATION DONNÉES/CODE (2-3 jours)                          │
│  Réorganisation des répertoires + configuration hiérarchique            │
└─────────────────────────────────────────────────────────────────────────┘
                                    │
                                    ▼
┌─────────────────────────────────────────────────────────────────────────┐
│  PHASE 5 : OPTIMISATIONS (optionnel, 2-3 jours)                         │
│  Vectorisation convolution + cache                                      │
└─────────────────────────────────────────────────────────────────────────┘
```

---

## Phase 0 : Préparation - Tests de Caractérisation

### Objectif
Capturer le comportement actuel avant toute modification pour garantir la non-régression.

### Actions

#### 0.1 Créer la structure de tests

```
tests/
├── __init__.py
├── conftest.py                 # Fixtures pytest partagées
├── golden_references/          # Sorties de référence (JSON)
│   ├── lpm/
│   ├── convolution/
│   └── selector/
├── characterization/           # Tests de capture
│   └── test_capture_golden.py
├── regression/                 # Tests de non-régression
│   └── test_regression.py
└── unit/                       # Tests unitaires (futurs)
```

#### 0.2 Créer le fichier de capture

**Fichier** : `tests/characterization/test_capture_golden.py`

```python
"""
Tests de caractérisation : capture le comportement actuel.
Exécuter UNE FOIS avant le refactoring.
"""
import json
import sys
from pathlib import Path
import numpy as np
import pytest

# Ajouter le répertoire sources au path
sys.path.insert(0, str(Path(__file__).parent.parent.parent / "sources"))

GOLDEN_DIR = Path(__file__).parent.parent / "golden_references"


class TestCaptureLPM:
    """Capture les sorties LPM."""

    @pytest.fixture(autouse=True)
    def setup(self):
        GOLDEN_DIR.mkdir(parents=True, exist_ok=True)
        (GOLDEN_DIR / "lpm").mkdir(exist_ok=True)

    @pytest.mark.parametrize("lpm_type", [
        "exp", "exp_shifted", "gamma", "uniform", "ig", "ig_shifted",
        "dirac", "dirac_double", "dirac_double_1_set"
    ])
    def test_capture_lpm(self, lpm_type):
        """Capture PDF/CDF pour chaque LPM."""
        from LPM.LPM_generate import LPM_generate

        lpm = LPM_generate(lpm_type)
        t = np.linspace(0.1, 100, 50)

        results = {
            "lpm_type": lpm_type,
            "parameters": {k: float(v) for k, v in lpm.p.items()},
            "test_points": t.tolist(),
            "pdf_values": lpm.pdf(t).tolist(),
            "cdf_values": lpm.cdf(t).tolist(),
            "mean": float(lpm.mean()),
            "std": float(lpm.std())
        }

        output_file = GOLDEN_DIR / "lpm" / f"{lpm_type}.json"
        with open(output_file, "w") as f:
            json.dump(results, f, indent=2)

        print(f"✓ Captured {lpm_type}")


class TestCaptureConvolution:
    """Capture les résultats de convolution."""

    @pytest.fixture(autouse=True)
    def setup(self):
        (GOLDEN_DIR / "convolution").mkdir(exist_ok=True)

    @pytest.mark.parametrize("lpm_type,tracer,date", [
        ("exp_shifted", "cfc11", 2010),
        ("exp_shifted", "cfc12", 2010),
        ("ig_shifted", "cfc11", 2010),
        ("gamma", "cfc11", 2010),
        ("dirac_double_1_set", "cfc11", 2010),
    ])
    def test_capture_convolution(self, lpm_type, tracer, date):
        """Capture convolution pour chaque combinaison."""
        from convolution.convolution import Convolution
        from LPM.LPM_generate import LPM_generate
        import global_parameters as gp

        lpm = LPM_generate(lpm_type)
        conv = Convolution(
            dir_tracer=gp.DIRECTORY_TRACER_DATA,
            name=tracer,
            date=date
        )
        result = conv.convolution(lpm)

        results = {
            "lpm_type": lpm_type,
            "lpm_params": {k: float(v) for k, v in lpm.p.items()},
            "tracer": tracer,
            "date": date,
            "convolution_result": float(result)
        }

        filename = f"{lpm_type}_{tracer}_{date}.json"
        output_file = GOLDEN_DIR / "convolution" / filename
        with open(output_file, "w") as f:
            json.dump(results, f, indent=2)

        print(f"✓ Captured {lpm_type}+{tracer}@{date}")


class TestCaptureSelector:
    """Capture la configuration selector()."""

    @pytest.fixture(autouse=True)
    def setup(self):
        (GOLDEN_DIR / "selector").mkdir(exist_ok=True)

    def test_capture_selector(self):
        """Capture toutes les configurations de puits."""
        from appli_ploemeur import selector

        all_wells = [
            "F09", "F11", "F34", "F38", "F38b",
            "PE", "MF1", "MF4", "PZ2", "PSR1"
        ]

        results = {}
        for well in all_wells:
            wells, datess, errors, lpm_types = selector([well], error=0.03)
            if wells:
                results[well] = {
                    "dates": datess[0],
                    "error": errors[0],
                    "lpm_types": lpm_types[0]
                }

        output_file = GOLDEN_DIR / "selector" / "wells_config.json"
        with open(output_file, "w") as f:
            json.dump(results, f, indent=2)

        print(f"✓ Captured {len(results)} wells")


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
```

#### 0.3 Créer les tests de régression

**Fichier** : `tests/regression/test_regression.py`

```python
"""
Tests de non-régression : vérifie que le comportement n'a pas changé.
Exécuter APRÈS chaque modification.
"""
import json
import sys
from pathlib import Path
import numpy as np
import pytest

sys.path.insert(0, str(Path(__file__).parent.parent.parent / "sources"))

GOLDEN_DIR = Path(__file__).parent.parent / "golden_references"
TOLERANCE = 1e-10


class TestRegressionLPM:
    """Vérifie que les LPM n'ont pas changé."""

    @pytest.mark.parametrize("lpm_type", [
        "exp", "exp_shifted", "gamma", "uniform", "ig", "ig_shifted",
        "dirac", "dirac_double", "dirac_double_1_set"
    ])
    def test_lpm_unchanged(self, lpm_type):
        """Compare PDF/CDF aux références."""
        from LPM.LPM_generate import LPM_generate

        golden_file = GOLDEN_DIR / "lpm" / f"{lpm_type}.json"
        if not golden_file.exists():
            pytest.skip(f"Golden reference not found: {golden_file}")

        with open(golden_file) as f:
            golden = json.load(f)

        # Recréer le LPM avec les mêmes paramètres
        lpm = LPM_generate(lpm_type)
        for param, value in golden["parameters"].items():
            lpm.p[param] = value

        t = np.array(golden["test_points"])

        # Comparer PDF
        np.testing.assert_allclose(
            lpm.pdf(t),
            np.array(golden["pdf_values"]),
            rtol=TOLERANCE,
            err_msg=f"PDF changed for {lpm_type}"
        )

        # Comparer CDF
        np.testing.assert_allclose(
            lpm.cdf(t),
            np.array(golden["cdf_values"]),
            rtol=TOLERANCE,
            err_msg=f"CDF changed for {lpm_type}"
        )

        # Comparer moments
        assert abs(lpm.mean() - golden["mean"]) < TOLERANCE
        assert abs(lpm.std() - golden["std"]) < TOLERANCE


class TestRegressionConvolution:
    """Vérifie que les convolutions n'ont pas changé."""

    @pytest.mark.parametrize("lpm_type,tracer,date", [
        ("exp_shifted", "cfc11", 2010),
        ("exp_shifted", "cfc12", 2010),
        ("ig_shifted", "cfc11", 2010),
        ("gamma", "cfc11", 2010),
        ("dirac_double_1_set", "cfc11", 2010),
    ])
    def test_convolution_unchanged(self, lpm_type, tracer, date):
        """Compare convolution aux références."""
        from convolution.convolution import Convolution
        from LPM.LPM_generate import LPM_generate
        import global_parameters as gp

        filename = f"{lpm_type}_{tracer}_{date}.json"
        golden_file = GOLDEN_DIR / "convolution" / filename
        if not golden_file.exists():
            pytest.skip(f"Golden reference not found: {golden_file}")

        with open(golden_file) as f:
            golden = json.load(f)

        lpm = LPM_generate(lpm_type)
        for param, value in golden["lpm_params"].items():
            lpm.p[param] = value

        conv = Convolution(
            dir_tracer=gp.DIRECTORY_TRACER_DATA,
            name=tracer,
            date=date
        )
        result = conv.convolution(lpm)

        assert abs(result - golden["convolution_result"]) < TOLERANCE, \
            f"Convolution changed: {result} vs {golden['convolution_result']}"


class TestRegressionSelector:
    """Vérifie que selector() n'a pas changé."""

    def test_selector_unchanged(self):
        """Compare configuration puits aux références."""
        from appli_ploemeur import selector

        golden_file = GOLDEN_DIR / "selector" / "wells_config.json"
        if not golden_file.exists():
            pytest.skip(f"Golden reference not found: {golden_file}")

        with open(golden_file) as f:
            golden = json.load(f)

        for well, expected in golden.items():
            wells, datess, errors, lpm_types = selector([well], error=0.03)

            assert len(wells) == 1, f"Well {well} not found"
            assert datess[0] == expected["dates"], \
                f"Dates changed for {well}: {datess[0]} vs {expected['dates']}"
            assert set(lpm_types[0]) == set(expected["lpm_types"]), \
                f"LPM types changed for {well}"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
```

#### 0.4 Script d'exécution

**Fichier** : `tests/run_tests.py`

```python
#!/usr/bin/env python
"""
Script principal pour les tests.

Usage:
    python run_tests.py capture     # Capturer les golden references
    python run_tests.py regression  # Vérifier la non-régression
    python run_tests.py all         # Tout exécuter
"""
import subprocess
import sys
from pathlib import Path

TESTS_DIR = Path(__file__).parent


def run_capture():
    """Capture les golden references."""
    print("=" * 60)
    print("CAPTURING GOLDEN REFERENCES")
    print("=" * 60)
    return subprocess.run([
        sys.executable, "-m", "pytest",
        str(TESTS_DIR / "characterization"),
        "-v", "--tb=short"
    ]).returncode


def run_regression():
    """Exécute les tests de régression."""
    print("=" * 60)
    print("RUNNING REGRESSION TESTS")
    print("=" * 60)
    return subprocess.run([
        sys.executable, "-m", "pytest",
        str(TESTS_DIR / "regression"),
        "-v", "--tb=short"
    ]).returncode


def main():
    if len(sys.argv) < 2:
        print(__doc__)
        sys.exit(1)

    command = sys.argv[1]

    if command == "capture":
        sys.exit(run_capture())
    elif command == "regression":
        sys.exit(run_regression())
    elif command == "all":
        run_capture()
        sys.exit(run_regression())
    else:
        print(f"Unknown command: {command}")
        sys.exit(1)


if __name__ == "__main__":
    main()
```

### Validation Phase 0

```bash
# 1. Installer pytest si nécessaire
pip install pytest

# 2. Capturer les références (AVANT tout changement)
cd c:\codes\pyage
python tests/run_tests.py capture

# 3. Vérifier que les tests passent
python tests/run_tests.py regression
```

---

## Phase 1 : Configuration Externalisée

### Objectif
Remplacer les 150 lignes de `selector()` par une configuration YAML.

### Actions

#### 1.1 Créer le fichier de configuration des puits

**Fichier** : `sources/sites/ploemeur/data/wells_config.yaml`

```yaml
# Configuration des puits pour le site de Ploemeur
# Ce fichier remplace la fonction selector() hardcodée

# Valeurs par défaut appliquées à tous les puits
defaults:
  lpm_types:
    - exp_shifted
    - ig_shifted
    - ig
    - dirac_double_1_set
    - gamma
    - uniform
    - exp
  tracers:
    - cfc11
    - cfc12
    - cfc113
  breakups:
    - 2012

# Configuration spécifique par puits
wells:
  F09:
    dates: "2005_2024"
    description: "Puits F09 - données 2005 à 2024"

  F11:
    dates: "2004_2024"
    description: "Puits F11 - données 2004 à 2024"

  F34:
    dates: "2004_2015"
    breakups: []  # Pas de breakup pour ce puits
    description: "Puits F34 - série courte"

  F38:
    dates: "2006_2020"
    description: "Puits F38"

  F38b:
    dates: "2006_2011"
    breakups: []
    description: "Puits F38b - série courte"

  PE:
    dates: "2005_2020"
    description: "Puits PE (pompage)"

  MF1:
    dates: "2004_2020"
    description: "Puits MF1"

  MF4:
    dates: "2006_2017"
    breakups: []
    description: "Puits MF4 - série courte"

  PZ2:
    dates: "2009_2024"
    breakups: []
    description: "Piézomètre PZ2"

  PSR1:
    dates: "2009_2024"
    breakups: []
    description: "Piézomètre PSR1"
```

#### 1.2 Créer le module de chargement de configuration

**Fichier** : `sources/core/__init__.py`

```python
"""Core module for PyAge."""
```

**Fichier** : `sources/core/config.py`

```python
"""
Configuration management for PyAge.

Handles loading and merging of YAML configuration files
with support for hierarchical defaults.
"""
from pathlib import Path
from typing import Any, Optional
import yaml


class ConfigError(Exception):
    """Exception raised for configuration errors."""
    pass


class WellsConfig:
    """
    Gestionnaire de configuration des puits.

    Charge la configuration depuis un fichier YAML et applique
    les valeurs par défaut automatiquement.

    Attributes
    ----------
    defaults : dict
        Valeurs par défaut appliquées à tous les puits
    wells : dict
        Configuration spécifique de chaque puits

    Example
    -------
    >>> config = WellsConfig(Path("sites/ploemeur/data/wells_config.yaml"))
    >>> config.list_wells()
    ['F09', 'F11', 'F34', ...]
    >>> config.get_well("F09")
    {'dates': '2005_2024', 'lpm_types': [...], 'breakups': [2012]}
    """

    def __init__(self, config_path: Path):
        """
        Charge la configuration depuis un fichier YAML.

        Parameters
        ----------
        config_path : Path
            Chemin vers le fichier wells_config.yaml

        Raises
        ------
        ConfigError
            Si le fichier n'existe pas ou est invalide
        """
        if not config_path.exists():
            raise ConfigError(f"Configuration file not found: {config_path}")

        try:
            with open(config_path, encoding='utf-8') as f:
                data = yaml.safe_load(f)
        except yaml.YAMLError as e:
            raise ConfigError(f"Invalid YAML in {config_path}: {e}")

        self.defaults = data.get("defaults", {})
        self._wells = data.get("wells", {})

        if not self._wells:
            raise ConfigError(f"No wells defined in {config_path}")

    def list_wells(self) -> list[str]:
        """Retourne la liste des puits disponibles."""
        return list(self._wells.keys())

    def get_well(self, name: str) -> dict:
        """
        Retourne la configuration d'un puits avec les defaults appliqués.

        Parameters
        ----------
        name : str
            Nom du puits (ex: "F09")

        Returns
        -------
        dict
            Configuration complète du puits

        Raises
        ------
        ConfigError
            Si le puits n'existe pas
        """
        if name not in self._wells:
            available = ", ".join(self._wells.keys())
            raise ConfigError(
                f"Well '{name}' not found. Available: {available}"
            )

        # Copier les defaults et surcharger avec la config du puits
        config = self.defaults.copy()
        well_config = self._wells[name]

        for key, value in well_config.items():
            config[key] = value

        return config

    def select(
        self,
        well_names: list[str],
        error: float = 0.03
    ) -> tuple[list, list, list, list]:
        """
        Sélectionne les puits et retourne les listes de configuration.

        Compatible avec l'ancienne API de selector().

        Parameters
        ----------
        well_names : list[str]
            Liste des noms de puits à sélectionner
        error : float
            Erreur relative à appliquer (défaut: 0.03)

        Returns
        -------
        tuple
            (wells, datess, errors, lpm_types) - 4 listes parallèles
        """
        wells = []
        datess = []
        errors = []
        lpm_types = []

        for name in well_names:
            if name not in self._wells:
                continue

            config = self.get_well(name)
            wells.append(name)
            datess.append(config["dates"])
            errors.append(error)
            lpm_types.append(config.get("lpm_types", self.defaults.get("lpm_types", [])))

        return wells, datess, errors, lpm_types


# Instance globale (lazy loading)
_wells_config: Optional[WellsConfig] = None


def get_wells_config() -> WellsConfig:
    """
    Retourne l'instance globale de WellsConfig.

    Utilise un lazy loading pour ne charger qu'une fois.
    """
    global _wells_config
    if _wells_config is None:
        config_path = Path(__file__).parent.parent / "sites" / "ploemeur" / "data" / "wells_config.yaml"
        _wells_config = WellsConfig(config_path)
    return _wells_config
```

#### 1.3 Modifier selector() pour utiliser la configuration

**Fichier** : `sites/ploemeur/scripts/appli_ploemeur.py` (modification)

```python
# Ajouter en haut du fichier
from core.config import get_wells_config, ConfigError

# Remplacer la fonction selector() (lignes 527-674) par :

def selector(well_select: list, error: float = 0.03):
    """
    Sélection des puits, dates, erreurs et modèles LPM.

    Charge la configuration depuis wells_config.yaml.

    Parameters
    ----------
    well_select : list
        Liste des noms de puits à sélectionner
    error : float
        Erreur relative (défaut: 0.03)

    Returns
    -------
    tuple
        (wells, datess, errors, lpm_types)
    """
    try:
        config = get_wells_config()
        return config.select(well_select, error)
    except ConfigError as e:
        print(f"Configuration error: {e}")
        # Fallback vers l'ancienne méthode si nécessaire
        return _selector_legacy(well_select, error)


def _selector_legacy(well_select, error=0.03):
    """
    Ancienne implémentation de selector() - DEPRECATED.

    Conservée pour compatibilité en cas de problème avec le YAML.
    """
    # [Garder l'ancien code ici comme fallback]
    wells = []
    datess = []
    errors = []
    lpm_types = []

    # ... ancien code ...

    return wells, datess, errors, lpm_types
```

### Validation Phase 1

```bash
# 1. Exécuter les tests de régression
python tests/run_tests.py regression

# 2. Test manuel
python -c "
from core.config import get_wells_config
config = get_wells_config()
print('Wells:', config.list_wells())
print('F09:', config.get_well('F09'))
"

# 3. Si OK, supprimer _selector_legacy après quelques jours
```

---

## Phase 2 : Gestion des Erreurs

### Objectif
Remplacer les `sys.exit()` par des exceptions propres et traçables.

### Actions

#### 2.1 Créer le module d'exceptions

**Fichier** : `sources/core/exceptions.py`

```python
"""
Custom exceptions for PyAge.

Hierarchy:
    PyAgeError (base)
    ├── ConfigError
    ├── DataError
    │   ├── ConcentrationError
    │   └── TracerError
    ├── ModelError
    │   ├── LPMError
    │   └── ConvolutionError
    └── CalibrationError
"""


class PyAgeError(Exception):
    """Base exception for all PyAge errors."""

    def __init__(self, message: str, details: dict = None):
        self.message = message
        self.details = details or {}
        super().__init__(self.message)

    def __str__(self):
        if self.details:
            detail_str = ", ".join(f"{k}={v}" for k, v in self.details.items())
            return f"{self.message} ({detail_str})"
        return self.message


class ConfigError(PyAgeError):
    """Error in configuration files."""
    pass


class DataError(PyAgeError):
    """Error related to data loading or validation."""
    pass


class ConcentrationError(DataError):
    """Error in concentration data."""
    pass


class TracerError(DataError):
    """Error in tracer configuration or data."""
    pass


class ModelError(PyAgeError):
    """Error related to models (LPM, etc.)."""
    pass


class LPMError(ModelError):
    """Error in LPM model."""
    pass


class ConvolutionError(ModelError):
    """Error during convolution computation."""
    pass


class CalibrationError(PyAgeError):
    """Error during calibration process."""
    pass


class ParameterError(CalibrationError):
    """Error related to parameter values or bounds."""
    pass
```

#### 2.2 Remplacer sys.exit() dans les fichiers concernés

**Liste des fichiers à modifier** :

| Fichier | Ligne | Remplacement |
|---------|-------|--------------|
| `convolution.py` | 198 | `ConvolutionError` |
| `calibration_exploration.py` | 161, 176, 212 | `CalibrationError` |
| `calibration_exploration.py` | 542, 548 | `CalibrationError` |
| `calibration_Metropolis_Hastings.py` | 383 | `CalibrationError` |
| `LPM_generate.py` | 69 | `LPMError` |

**Exemple de modification** (`convolution.py:196-199`) :

```python
# AVANT
if self.__prepare != prepare:
    print("Problem in the preparation and performance of convolution")
    sys.exit()

# APRÈS
from core.exceptions import ConvolutionError

if self.__prepare != prepare:
    raise ConvolutionError(
        "Inconsistent preparation state for convolution",
        details={
            "tracer": self.name,
            "date": self.__date,
            "prepared": self.__prepare,
            "expected": prepare
        }
    )
```

**Exemple pour LPM_generate.py:67-69** :

```python
# AVANT
else:
    print('lpm type', lpm_type, 'not defined')
    sys.exit()

# APRÈS
from core.exceptions import LPMError

else:
    raise LPMError(
        f"Unknown LPM type: '{lpm_type}'",
        details={
            "available_types": [
                "exp", "exp_shifted", "gamma", "ig", "ig_shifted",
                "uniform", "dirac", "dirac_double", "dirac_double_1_set",
                "mix_exp_shifted"
            ]
        }
    )
```

### Validation Phase 2

```bash
# Tests de régression
python tests/run_tests.py regression

# Test des exceptions
python -c "
from core.exceptions import LPMError
from LPM.LPM_generate import LPM_generate
try:
    LPM_generate('invalid_type')
except LPMError as e:
    print(f'OK: {e}')
"
```

---

## Phase 3 : Logging et Monitoring

### Objectif
Remplacer les `print()` par un système de logging structuré.

### Actions

#### 3.1 Créer le module de logging

**Fichier** : `sources/core/logging.py`

```python
"""
Logging configuration for PyAge.

Usage:
    from core.logging import get_logger
    logger = get_logger(__name__)
    logger.info("Starting calibration")
    logger.warning("High objective function value")
    logger.error("Calibration failed", exc_info=True)
"""
import logging
import sys
from pathlib import Path
from datetime import datetime
from typing import Optional


def get_logger(
    name: str,
    level: int = logging.INFO,
    log_file: Optional[Path] = None
) -> logging.Logger:
    """
    Configure and return a logger for a module.

    Parameters
    ----------
    name : str
        Logger name (typically __name__)
    level : int
        Logging level (default: INFO)
    log_file : Path, optional
        Path to log file. If None, logs only to console.

    Returns
    -------
    logging.Logger
        Configured logger instance
    """
    logger = logging.getLogger(name)

    # Éviter les doublons si déjà configuré
    if logger.handlers:
        return logger

    logger.setLevel(level)

    # Format
    formatter = logging.Formatter(
        '%(asctime)s | %(levelname)-8s | %(name)s | %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S'
    )

    # Console handler
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setFormatter(formatter)
    logger.addHandler(console_handler)

    # File handler (optionnel)
    if log_file:
        log_file.parent.mkdir(parents=True, exist_ok=True)
        file_handler = logging.FileHandler(log_file, encoding='utf-8')
        file_handler.setFormatter(formatter)
        logger.addHandler(file_handler)

    return logger


def setup_simulation_logging(output_dir: Path) -> logging.Logger:
    """
    Configure logging for a simulation run.

    Creates a timestamped log file in the output directory.

    Parameters
    ----------
    output_dir : Path
        Directory where log file will be created

    Returns
    -------
    logging.Logger
        Root logger for the simulation
    """
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    log_file = output_dir / f"simulation_{timestamp}.log"

    return get_logger("pyage", level=logging.INFO, log_file=log_file)


# Logger par défaut pour les imports rapides
default_logger = get_logger("pyage")
```

#### 3.2 Exemple de migration des print()

**Dans `calibration_Metropolis_Hastings.py`** :

```python
# En haut du fichier
from core.logging import get_logger
logger = get_logger(__name__)

# Remplacer les print()

# AVANT
print(f"MH: step {i}/{nstep}, acceptance rate: {nsuccess/i:.2%}")

# APRÈS
logger.info(f"MH progress: {i}/{nstep} ({100*i/nstep:.1f}%), acceptance: {nsuccess/i:.2%}")

# AVANT
print("Error: concentration errors not defined")

# APRÈS
logger.error("Concentration errors are zero", extra={
    "tracer": tracer_name,
    "lpm": lpm.name
})
```

### Validation Phase 3

```bash
# Tests de régression
python tests/run_tests.py regression

# Vérifier les logs
python -c "
from core.logging import get_logger
logger = get_logger('test')
logger.info('Test message')
logger.warning('Warning message')
"
```

---

## Phase 4 : Séparation Données/Code

### Objectif
Réorganiser les répertoires pour séparer clairement données, code et applications.

### Actions

#### 4.1 Nouvelle structure proposée

```
pyage/
├── pyage/                      # Package Python (renommé depuis sources/)
│   ├── __init__.py
│   ├── core/
│   │   ├── __init__.py
│   │   ├── config.py
│   │   ├── exceptions.py
│   │   └── logging.py
│   ├── lpm/
│   ├── tracer/
│   ├── convolution/
│   └── calibration/
│
├── applications/               # Applications (séparées du package)
│   └── ploemeur/
│       ├── __init__.py
│       ├── config.yaml         # Configuration de simulation
│       ├── wells.yaml          # Configuration des puits
│       └── run.py              # Point d'entrée
│
├── data/                       # Données (hors du package Python)
│   ├── tracers/                # Chroniques traceurs (globales)
│   │   ├── cfc11/
│   │   │   ├── cfc11.yaml
│   │   │   └── recharge.csv
│   │   └── ...
│   │
│   └── sites/
│       └── ploemeur/
│           ├── concentrations/ # Mesures par puits
│           │   ├── F09.txt
│           │   └── ...
│           └── lpm_params/     # Paramètres LPM spécifiques
│               └── exp_shifted/
│                   ├── bounds.yaml
│                   └── mh_config.yaml
│
├── tests/
├── docs/
└── pyproject.toml
```

#### 4.2 Migration progressive

**Étape 1** : Créer la structure sans déplacer les fichiers
```bash
mkdir -p pyage/core
mkdir -p applications/ploemeur
mkdir -p data/tracers
mkdir -p data/sites/ploemeur/concentrations
mkdir -p data/sites/ploemeur/lpm_params
```

**Étape 2** : Ajouter des imports de compatibilité

```python
# sources/__init__.py (temporaire)
"""
Compatibility layer during migration.
Import from pyage package instead.
"""
import warnings
warnings.warn(
    "Importing from 'sources' is deprecated. Use 'pyage' instead.",
    DeprecationWarning,
    stacklevel=2
)

from pyage import *
```

**Étape 3** : Migrer les fichiers progressivement avec des symlinks temporaires

#### 4.3 Configuration hiérarchique

**Fichier** : `data/sites/ploemeur/lpm_params/exp_shifted/config.yaml`

```yaml
# Configuration LPM exp_shifted pour le site Ploemeur
# Surcharge les valeurs par défaut de data/lpm_defaults/exp_shifted.yaml

parameters:
  mu:
    min: 0
    max: 80    # Réduit par rapport au défaut (100)
    unit: year
    description: "Mean residence time"

  shift:
    min: 0
    max: 50    # Réduit par rapport au défaut (100)
    unit: year
    description: "Minimum transit time"

metropolis_hastings:
  step:
    mu: 1.5    # Ajusté pour ce site
    shift: 0.8

  prior:
    mu:
      type: uniform
      min: 0
      max: 80
    shift:
      type: uniform
      min: 0
      max: 50
```

---

## Phase 5 : Optimisations (Optionnel)

### Objectif
Améliorer les performances sans casser l'existant.

### Actions potentielles

#### 5.1 Cache des chroniques de recharge

```python
# tracer/tracer_root.py
from functools import lru_cache

class Tracer:
    @lru_cache(maxsize=32)
    def _load_recharge_cached(self, tracer_name: str) -> pd.DataFrame:
        """Cache les chroniques de recharge."""
        return pd.read_csv(self._recharge_file, comment='#')
```

#### 5.2 Vectorisation partielle de la convolution

```python
# convolution/convolution.py
def convolution_vectorized(self, lpm, dates: np.ndarray) -> np.ndarray:
    """
    Convolution vectorisée pour plusieurs dates.

    Plus efficace que d'appeler convolution() en boucle.
    """
    results = np.zeros(len(dates))

    # Pré-calculer la grille de temps une seule fois
    t_grid = np.linspace(0, self.datemax - self.datemin, 200)

    for i, date in enumerate(dates):
        self.__date = date
        # Réutiliser la grille
        results[i] = self._convolution_with_grid(lpm, t_grid)

    return results
```

---

## Résumé du Plan

| Phase | Durée | Priorité | Impact |
|-------|-------|----------|--------|
| **Phase 0** : Tests | 1-2 jours | Critique | Sécurité |
| **Phase 1** : Config YAML | 2-3 jours | Haute | Maintenabilité |
| **Phase 2** : Exceptions | 1-2 jours | Haute | Robustesse |
| **Phase 3** : Logging | 1 jour | Moyenne | Débogage |
| **Phase 4** : Réorganisation | 2-3 jours | Moyenne | Architecture |
| **Phase 5** : Optimisation | 2-3 jours | Basse | Performance |

### Checklist de Validation

Pour chaque phase :

- [ ] Tests de régression passent
- [ ] Aucune fonctionnalité cassée
- [ ] Code commité avec message clair
- [ ] Documentation mise à jour si nécessaire

### Commandes de Validation

```bash
# Après CHAQUE modification
python tests/run_tests.py regression

# Commit fréquent
git add -A
git commit -m "Phase X.Y: Description courte"
```

---

## Annexe : Migration des Fichiers de Données

### Format actuel vs proposé pour bounds.txt

**Actuel** (`sites/ploemeur/data/LPM_data/exp_shifted/bounds.txt`) :
```
mu,0,100,year
shift,0,100,year
```

**Proposé** (`data/lpm_defaults/exp_shifted.yaml`) :
```yaml
parameters:
  mu:
    min: 0
    max: 100
    unit: year
  shift:
    min: 0
    max: 100
    unit: year
```

### Script de conversion

```python
# scripts/convert_lpm_config.py
"""Convertit les fichiers bounds.txt en YAML."""
from pathlib import Path
import yaml

def convert_bounds_to_yaml(lpm_dir: Path):
    """Convertit bounds.txt, MHstep.txt, MHapriori.txt en un seul YAML."""
    config = {"parameters": {}, "metropolis_hastings": {"step": {}, "prior": {}}}

    # bounds.txt
    bounds_file = lpm_dir / "bounds.txt"
    if bounds_file.exists():
        for line in bounds_file.read_text().strip().split('\n'):
            parts = line.split(',')
            param = parts[0]
            config["parameters"][param] = {
                "min": float(parts[1]),
                "max": float(parts[2]),
                "unit": parts[3]
            }

    # MHstep.txt
    step_file = lpm_dir / "MHstep.txt"
    if step_file.exists():
        for line in step_file.read_text().strip().split('\n'):
            parts = line.split(',')
            config["metropolis_hastings"]["step"][parts[0]] = float(parts[1])

    # MHapriori.txt
    prior_file = lpm_dir / "MHapriori.txt"
    if prior_file.exists():
        for line in prior_file.read_text().strip().split('\n'):
            parts = line.split(',')
            config["metropolis_hastings"]["prior"][parts[0]] = {
                "type": parts[1],
                "param1": float(parts[2]),
                "param2": float(parts[3])
            }

    # Écrire le YAML
    output = lpm_dir / "config.yaml"
    with open(output, 'w') as f:
        yaml.dump(config, f, default_flow_style=False, sort_keys=False)

    print(f"Converted: {lpm_dir.name} -> {output}")


if __name__ == "__main__":
    lpm_data = Path("core_data/LPM_data")
    for lpm_dir in lpm_data.iterdir():
        if lpm_dir.is_dir():
            convert_bounds_to_yaml(lpm_dir)
```
