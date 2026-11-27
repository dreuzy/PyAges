# Charger des modèles LPM externes : proposition expliquée pas à pas

## Statut de ce document

Ce document décrit une **évolution possible** de PyAges. Le mécanisme présenté
ici n'est pas encore implémenté.

L'objectif n'est pas d'ajouter maintenant une nouvelle distribution. Il est de
comprendre comment PyAges pourrait, à l'avenir, utiliser des modèles LPM placés
entièrement à l'extérieur de son code source.

## 1. Le besoin, en une phrase

On souhaite pouvoir écrire ceci :

```python
from pyages.lpm import build_lpm

lpm = build_lpm("lognormal")
```

alors que le modèle `lognormal` n'est pas présent dans le dépôt PyAges.

Le modèle pourrait appartenir à une autre équipe, être conservé dans un autre
dépôt et être installé séparément. PyAges ne devrait pas avoir à être modifié à
chaque nouveau modèle.

## 2. Ce que signifie « entièrement externe »

Il faut distinguer le **code de PyAges** du **code du modèle mathématique**.

- Le code de PyAges ne serait pas modifié.
- Le nouveau modèle aurait tout de même son propre petit fichier Python.
- Ses paramètres seraient décrits dans son propre fichier `params.yaml`.
- Ces fichiers seraient rangés dans un paquet externe installable.
- Après installation, PyAges saurait automatiquement que ce modèle existe.

« Sans toucher au code » signifie donc ici **sans toucher au code de PyAges**.
Une distribution entièrement nouvelle a nécessairement besoin de quelques
formules quelque part : densité, fonction de répartition, moments et primitive
utilisée par la convolution.

Un simple fichier YAML peut décrire des noms, des bornes ou des valeurs
initiales. Il ne peut pas raisonnablement décrire toutes les mathématiques
d'une distribution arbitraire.

## 3. Quelques mots de vocabulaire

| Mot | Explication simple |
| --- | --- |
| Modèle LPM | Distribution des temps de transit utilisée par PyAges. |
| Registre | Annuaire qui associe un nom comme `exp` à son implémentation Python. |
| Paquet Python | Dossier de code que l'on peut installer avec `pip`. |
| Plugin | Petit paquet externe qu'un logiciel sait reconnaître et charger. |
| Point d'entrée | Ligne de la fiche d'installation d'un plugin qui annonce : « je fournis tel modèle ». Le terme anglais est *entry point*. |
| Fabrique | Fonction qui construit un objet. Dans PyAges, il s'agit notamment de `build_lpm()`. |
| Schéma de paramètres | Description validée des paramètres : noms, bornes, valeurs initiales, pas et lois a priori. |

Il n'est pas nécessaire de maîtriser ces termes pour utiliser un plugin. Ils
servent surtout à expliquer ce que fait PyAges en arrière-plan.

## 4. Comment cela fonctionne aujourd'hui

Lorsqu'on écrit :

```python
lpm = build_lpm("exp")
```

PyAges effectue approximativement les opérations suivantes :

```text
1. Chercher le nom "exp" dans son registre.
2. Trouver la classe ExponentialLpm.
3. Chercher data_core/data_lpm/exp/params.yaml.
4. Vérifier les paramètres et leurs bornes.
5. Construire le modèle.
```

Le registre actuel découvre uniquement les modules rangés dans :

```text
pyages/lpm/models/
```

Les paramètres par défaut sont cherchés uniquement sous :

```text
data_core/data_lpm/<nom_du_modèle>/params.yaml
```

C'est pourquoi un nouveau modèle doit actuellement être ajouté au dépôt
PyAges. La classe Python et le fichier YAML sont tous les deux supposés faire
partie du projet principal.

## 5. L'idée générale proposée

Un modèle externe serait livré comme un petit ensemble autonome contenant :

```text
le code mathématique du modèle
        +
son fichier params.yaml
        +
une courte déclaration indiquant son nom à PyAges
```

On peut comparer cela à un livre et à une bibliothèque :

- le paquet externe est le livre ;
- la déclaration du plugin est la fiche du catalogue ;
- le registre PyAges est le catalogue de la bibliothèque ;
- `build_lpm("lognormal")` demande le livre portant ce nom.

PyAges n'a pas besoin de connaître à l'avance tous les livres qui pourront être
publiés.

## 6. Ce que verrait l'utilisateur du modèle

L'utilisation devrait rester très courte.

### Étape 1 — Installer le modèle

```bash
pip install pyages-lpm-lognormal
```

Le nom `pyages-lpm-lognormal` n'est qu'un exemple de nom de paquet.

### Étape 2 — Vérifier que PyAges le voit

```python
from pyages.lpm import list_available_lpms

print(list_available_lpms())
```

La liste contiendrait par exemple :

```text
..., "ig", "lognormal", "uniform", ...
```

### Étape 3 — Construire le modèle

```python
from pyages.lpm import build_lpm

lpm = build_lpm("lognormal")
```

Il ne serait pas nécessaire d'importer explicitement le paquet externe ni de
copier un fichier dans PyAges.

## 7. À quoi ressemblerait le paquet externe

Voici une organisation possible :

```text
pyages-lpm-lognormal/
├── pyproject.toml
└── src/
    └── groundwater_lpms/
        ├── __init__.py
        ├── lognormal.py
        └── data_lpm/
            └── lognormal/
                └── params.yaml
```

Chaque élément a une responsabilité simple :

- `lognormal.py` contient les formules du modèle ;
- `params.yaml` contient ses réglages de calibration ;
- `pyproject.toml` indique comment installer le paquet et annonce le modèle à
  PyAges.

## 8. Comment le paquet annoncerait son modèle

Le fichier `pyproject.toml` du paquet externe pourrait contenir :

```toml
[project.entry-points."pyages.lpms"]
lognormal = "groundwater_lpms.lognormal:definition"
```

Cette notation peut sembler technique, mais sa lecture est assez directe :

```text
lognormal
    est fourni par
groundwater_lpms/lognormal.py
    dans l'objet appelé
definition
```

Le « point d'entrée » est simplement cette annonce. Lors de l'installation,
Python conserve l'annonce dans les informations du paquet. PyAges peut ensuite
lire la liste des annonces sans parcourir au hasard tous les dossiers de
l'ordinateur.

### Ce qu'un point d'entrée est exactement

Un point d'entrée n'est ni une nouvelle sorte de fonction, ni un programme qui
tourne en permanence. C'est une **ligne d'information enregistrée lors de
l'installation d'un paquet**.

Cette ligne contient trois éléments :

```text
pyages.lpms                          lognormal
───────────                          ─────────
groupe                               nom public

groundwater_lpms.lognormal:definition
────────────────────────────────────────────
adresse de l'objet Python à charger
```

Le **groupe** joue le rôle d'un rayon de catalogue. PyAges regarderait seulement
le rayon `pyages.lpms`. Il ne confondrait donc pas un modèle LPM avec une
commande de terminal ou avec un plugin destiné à un autre logiciel.

Le **nom public** est ce que l'utilisateur passe à `build_lpm()`.

L'**adresse** se lit comme un import Python :

```python
from groundwater_lpms.lognormal import definition
```

La notation avec les deux-points est simplement une forme compacte de cet
import :

```text
groundwater_lpms.lognormal : definition
          module              objet
```

L'installation ne charge pas le modèle et ne lance pas ses calculs. Elle se
contente d'enregistrer cette adresse. PyAges déciderait plus tard de charger
l'objet, seulement lorsqu'il en a besoin.

### À quoi ressemblerait la lecture côté PyAges

Python fournit déjà l'outil de lecture dans sa bibliothèque standard. Le cœur
du mécanisme tient approximativement dans ces lignes :

```python
from importlib.metadata import entry_points

annonces = entry_points(group="pyages.lpms")
for annonce in annonces:
    print(annonce.name, annonce.value)

definition = annonces[0].load()
```

Dans cet exemple :

- `annonce.name` vaut par exemple `lognormal` ;
- `annonce.value` vaut
  `groundwater_lpms.lognormal:definition` ;
- `annonce.load()` effectue l'import et renvoie l'objet `definition`.

Le vrai code PyAges devrait naturellement gérer les doublons et les erreurs,
mais la découverte elle-même n'est pas plus mystérieuse que cela. Elle ne
nécessite aucune dépendance supplémentaire : `importlib.metadata` fait partie
de Python.

### Est-ce un mécanisme classique ?

Oui. Les points d'entrée sont une spécification standard de l'empaquetage
Python. La documentation officielle les décrit comme un moyen pour un paquet
installé d'annoncer des composants que d'autres programmes peuvent découvrir.
Voir la [spécification Python Packaging Authority][pypa-entry-points].

Ils sont notamment utilisés par des bibliothèques très répandues :

| Logiciel | Utilisation du point d'entrée |
| --- | --- |
| `pytest` | Il découvre les plugins installés dans le groupe `pytest11`. C'est ainsi qu'un paquet de plugin peut être chargé sans modifier pytest. |
| Pygments | Il découvre de nouveaux analyseurs syntaxiques, styles, filtres et formatters fournis par des paquets externes. |
| `pip` et de nombreuses commandes Python | Le même mécanisme, avec le groupe spécial `console_scripts`, permet de créer une commande de terminal lors de l'installation. |

Les documentations officielles donnent directement ces exemples :

- [plugins pytest et groupe `pytest11`][pytest-plugins] ;
- [plugins externes de Pygments][pygments-plugins] ;
- [points d'entrée et commandes dans setuptools][setuptools-entry-points].

L'usage proposé pour PyAges serait donc conventionnel : seul le nom du groupe,
`pyages.lpms`, serait propre au projet.

[pypa-entry-points]: https://packaging.python.org/en/latest/specifications/entry-points/
[pytest-plugins]: https://docs.pytest.org/en/stable/how-to/writing_plugins.html#making-your-plugin-installable-by-others
[pygments-plugins]: https://pygments.org/docs/plugins/
[setuptools-entry-points]: https://setuptools.pypa.io/en/latest/userguide/entry_point.html

## 9. Ce que contiendrait `definition`

Le registre actuel conserve seulement une classe Python. Pour un modèle
externe, cela ne suffit pas : il faut également savoir où trouver ses
paramètres.

On pourrait donc introduire une petite fiche appelée ici `LpmDefinition` :

```python
definition = LpmDefinition(
    factory=LognormalLpm,
    parameters="groundwater_lpms:data_lpm/lognormal/params.yaml",
    api_version=1,
)
```

Cette fiche répondrait à trois questions :

1. Quelle classe faut-il construire ?
2. Où se trouve le fichier de paramètres par défaut ?
3. Quelle version du mécanisme de plugin est utilisée ?

Le mot `factory` désigne ici la classe ou la fonction capable de construire le
modèle. L'auteur du plugin n'aurait pas à écrire lui-même une véritable
« fabrique » compliquée.

Les noms présentés dans ce bloc sont une proposition d'interface. Ils
n'existent pas encore dans PyAges.

### Exemple complet du code externe

L'exemple suivant montre les fichiers qu'écrirait l'auteur d'une distribution
log-normale. Il est volontairement concret, mais l'import
`pyages.lpm.extensions` est encore **hypothétique** : il représente la petite
API qu'il faudrait ajouter à PyAges.

#### Fichier `pyproject.toml`

```toml
[build-system]
requires = ["setuptools>=77"]
build-backend = "setuptools.build_meta"

[project]
name = "pyages-lpm-lognormal"
version = "0.1.0"
requires-python = ">=3.12"
dependencies = ["pyages", "numpy", "scipy"]

[project.entry-points."pyages.lpms"]
lognormal = "pyages_lpm_lognormal.model:definition"

[tool.setuptools.package-data]
pyages_lpm_lognormal = ["data_lpm/*/params.yaml"]
```

Ce fichier dit quatre choses :

1. le paquet s'appelle `pyages-lpm-lognormal` ;
2. il dépend de PyAges, NumPy et SciPy ;
3. il annonce un LPM appelé `lognormal` ;
4. son fichier YAML doit être inclus lors de l'installation.

#### Fichier `src/pyages_lpm_lognormal/model.py`

```python
from pathlib import Path

import numpy as np
import numpy.typing as npt
from scipy.special import ndtr
from scipy.stats import lognorm

from pyages.lpm.core.lpm_scipy import LpmScipy
from pyages.lpm.extensions import LpmDefinition  # API proposée


class LognormalLpm(LpmScipy):
    """Distribution log-normale des temps de transit."""

    scipy_dist = lognorm

    def __init__(self, mu=10.0, sigma=5.0, directory_lpm=None):
        values = {"mu": mu, "sigma": sigma}
        units = {"mu": "year", "sigma": "year"}
        super().__init__("lognormal", values, units, directory_lpm)

    def _log_parameters(self):
        """Convertir moyenne et écart-type vers les paramètres log-normaux."""
        mean = float(self.p["mu"])
        std = float(self.p["sigma"])
        sigma_log = np.sqrt(np.log1p((std / mean) ** 2))
        mu_log = np.log(mean) - 0.5 * sigma_log**2
        return mu_log, sigma_log

    def _scipy_params(self):
        mu_log, sigma_log = self._log_parameters()
        return (sigma_log,), 0.0, np.exp(mu_log)

    def cdf_and_partial_first_moment(self, t: npt.ArrayLike):
        """Retourner F(t) et E[T 1(T <= t)] pour la convolution."""
        values = np.asarray(t, dtype=float)
        cdf = np.asarray(self.cdf(values), dtype=float)
        moment = np.zeros_like(values)

        positive = values > 0.0
        if np.any(positive):
            mu_log, sigma_log = self._log_parameters()
            z = (
                np.log(values[positive]) - mu_log - sigma_log**2
            ) / sigma_log
            moment[positive] = self.p["mu"] * ndtr(z)

        if values.ndim == 0:
            return float(cdf), float(moment)
        return cdf, moment


definition = LpmDefinition(
    model_class=LognormalLpm,
    parameter_directory=Path(__file__).parent / "data_lpm",
    api_version=1,
)
```

La plus grande partie de ce fichier ne concerne pas les plugins. Elle décrit
la distribution elle-même. Par rapport à un modèle intégré directement dans
PyAges, la partie spécifique au plugin se limite essentiellement à :

```python
definition = LpmDefinition(
    model_class=LognormalLpm,
    parameter_directory=Path(__file__).parent / "data_lpm",
    api_version=1,
)
```

et à la ligne correspondante dans `pyproject.toml`.

#### Fichier `src/pyages_lpm_lognormal/data_lpm/lognormal/params.yaml`

```yaml
model: lognormal
version: 1

parameters:
  - name: mu
    label: mean_age
    unit: year
    description: "Mean transit time."
    bounds: [0.1, 100.0]
    init: 10.0
    step: 1.0
    prior:
      type: uniform
      min: 0.1
      max: 100.0
      unit: year

  - name: sigma
    label: std_age
    unit: year
    description: "Standard deviation of transit time."
    bounds: [0.1, 50.0]
    init: 5.0
    step: 1.0
    prior:
      type: uniform
      min: 0.1
      max: 50.0
      unit: year
```

Ce fichier a exactement le même rôle et presque la même forme que les fichiers
`params.yaml` déjà présents dans `data_core/data_lpm`.

#### Fichier `src/pyages_lpm_lognormal/__init__.py`

Il peut être vide :

```python
"""Modèle log-normal externe pour PyAges."""
```

L'utilisateur installerait ensuite ce dossier en mode développement :

```bash
python -m pip install -e .
```

Après implémentation du mécanisme dans PyAges, le test d'utilisation serait :

```python
from pyages.lpm import build_lpm, list_available_lpms

assert "lognormal" in list_available_lpms()
lpm = build_lpm("lognormal")
print(lpm.mean())
```

### Gabarit complet sans distribution SciPy

Un dossier directement copiable est fourni dans
[`examples/templates/external_lpm_plugin`](../../examples/templates/external_lpm_plugin/README.md).

Il contient un second exemple, `bounded_power`, qui hérite directement de
`LpmBase` et implémente lui-même toutes les fonctions mathématiques :

- `pdf()` ;
- `cdf()` ;
- `cdf_inv()` ;
- `mean()` ;
- `std()` ;
- `cdf_and_partial_first_moment()`.

Ce gabarit comprend également le `pyproject.toml`, le `params.yaml`, la
déclaration du plugin et les tests scientifiques. Il est conçu pour être copié,
renommé puis complété. Sa découverte automatique restera hypothétique tant que
`LpmDefinition` ne sera pas implémentée dans PyAges.

## 10. Ce que ferait PyAges en arrière-plan

Avec ce mécanisme, l'appel :

```python
lpm = build_lpm("lognormal")
```

déclencherait les étapes suivantes :

```text
1. Chercher d'abord le modèle parmi les modèles intégrés à PyAges.
2. Chercher ensuite une annonce externe portant le nom "lognormal".
3. Charger uniquement le paquet qui fournit ce nom.
4. Lire sa fiche LpmDefinition.
5. Charger et valider son params.yaml.
6. Construire LognormalLpm.
7. Vérifier que le modèle respecte le contrat LPM.
8. Retourner le modèle à l'utilisateur.
```

Le chargement à l'étape 3 doit rester **paresseux** : PyAges ne charge pas tous
les plugins installés, seulement celui qui est demandé. Un plugin inutilisé et
défectueux ne doit pas empêcher l'utilisation de `exp` ou de `ig`.

## 11. Où placer les paramètres

Aujourd'hui, plusieurs parties de PyAges reviennent lire le `params.yaml` à
partir d'un chemin de répertoire. Cette organisation est pratique pour les
modèles internes, mais moins adaptée aux plugins.

Une solution plus propre serait de charger une seule fois le schéma de
paramètres, puis de l'attacher au modèle :

```python
lpm.parameter_schema
```

La calibration demanderait ensuite directement au modèle :

- ses bornes ;
- ses valeurs initiales ;
- ses pas de proposition ;
- ses lois a priori.

Elle n'aurait plus besoin de savoir si le YAML vient de PyAges, d'un plugin ou
d'un répertoire choisi par l'utilisateur.

### Remplacer les paramètres du plugin

Il doit rester possible d'utiliser d'autres bornes pour une étude particulière :

```python
lpm = build_lpm(
    "lognormal",
    directory_lpm="mes_parametres_lpm",
)
```

La règle de priorité pourrait être :

```text
1. Répertoire fourni explicitement par l'utilisateur
2. Paramètres fournis par le plugin
3. Paramètres intégrés à PyAges
```

Ainsi, le plugin fournit un comportement utilisable immédiatement, sans
empêcher une configuration propre à un site ou à une étude.

## 12. Comment garder le code du modèle court

Il existe deux types principaux de modèles.

### Cas A — La distribution existe déjà dans SciPy

PyAges possède déjà `LpmScipy`, qui fournit automatiquement :

- `pdf()` ;
- `cdf()` ;
- `cdf_inv()` ;
- `mean()` ;
- `std()`.

L'auteur doit principalement indiquer :

1. la distribution SciPy utilisée ;
2. la correspondance entre les paramètres scientifiques et ceux de SciPy ;
3. le calcul du moment partiel nécessaire à la convolution.

Un futur raccourci pourrait ressembler à :

```python
definition = scipy_lpm(
    distribution=lognorm,
    parameters="groundwater_lpms:data_lpm/lognormal/params.yaml",
    scipy_parameters=scipy_parameters,
    partial_first_moment=partial_first_moment,
)
```

Ce raccourci éviterait de réécrire une classe complète pour une distribution
SciPy ordinaire.

### Cas B — Le modèle est discret, mixte ou vraiment particulier

L'auteur utiliserait directement `LpmBase`, comme le font actuellement les
modèles Dirac ou shape-free. Il préciserait aussi la stratégie de convolution :

- continue ;
- Dirac simple ;
- Dirac double ;
- mélange Dirac–continu.

Le mécanisme de plugin ne change pas les mathématiques. Il change seulement la
manière dont PyAges trouve le modèle et ses paramètres.

## 13. Pourquoi le moment partiel reste nécessaire

Pour les distributions continues, PyAges ne demande pas seulement la densité
`pdf(t)`. Le moteur de convolution utilise également :

```text
F(t)  = probabilité que l'âge soit inférieur ou égal à t
M₁(t) = moyenne non normalisée des âges inférieurs ou égaux à t
```

Dans le code, ces deux quantités sont renvoyées ensemble par :

```python
cdf_and_partial_first_moment(t)
```

C'est une exigence scientifique du moteur de convolution, pas une complication
propre aux plugins. Une distribution externe continue doit donc fournir ce
calcul de manière fiable.

Pour certaines distributions, la formule est analytique et courte. Pour une
distribution plus complexe, elle peut demander un traitement numérique
spécifique et des tests supplémentaires.

## 14. Une variante plus simple pour le développement

Avant de publier et d'installer un véritable paquet, une fonction explicite
pourrait faciliter les essais :

```python
from pyages.lpm import load_lpm_plugin

load_lpm_plugin("groundwater_lpms.lognormal")
lpm = build_lpm("lognormal")
```

Cette solution a deux avantages pédagogiques :

- on voit clairement quel module est chargé ;
- les erreurs sont faciles à relier au module testé.

Elle demande toutefois une ligne supplémentaire dans chaque programme. Elle
serait donc adaptée au développement, tandis que l'annonce automatique dans
`pyproject.toml` serait préférable pour distribuer un modèle terminé.

`load_lpm_plugin()` est également une proposition et n'existe pas actuellement.

## 15. Pourquoi ne pas chercher automatiquement tous les fichiers `.py`

PyAges pourrait en théorie parcourir un dossier libre et importer tout ce qu'il
y trouve. Ce mécanisme paraît simple, mais pose plusieurs problèmes :

- on ne sait pas clairement quels fichiers seront exécutés ;
- deux fichiers peuvent utiliser le même nom de modèle ;
- une erreur dans un fichier peut bloquer tous les autres ;
- le résultat peut dépendre de l'ordinateur et de ses dossiers ;
- il devient difficile de conserver la version exacte d'un modèle utilisé pour
  une publication.

L'installation d'un paquet et son annonce explicite demandent un petit effort
supplémentaire, mais donnent un résultat plus prévisible et reproductible.

## 16. Cas des modèles décrits uniquement en YAML

Pour quelques distributions simples, on pourrait imaginer :

```yaml
model: gamma_externe
distribution: scipy.stats.gamma
parameters:
  - name: shape
  - name: scale
```

Cela fonctionnerait seulement si PyAges connaissait déjà la manière exacte de
transformer ces paramètres et de calculer le moment partiel.

Il faudrait éviter de mettre des formules Python sous forme de texte dans le
YAML, par exemple avec `eval`. Une telle solution serait difficile à lire, à
valider et à sécuriser.

Une bonne séparation serait donc :

- YAML pour les données et les réglages ;
- petit module Python pour les formules ;
- fiche de plugin pour relier les deux.

## 17. Règles importantes pour un mécanisme robuste

### Noms en double

Si deux paquets proposent `lognormal`, PyAges doit arrêter le chargement et
indiquer les deux fournisseurs. Il ne doit pas choisir en fonction de l'ordre
d'installation.

### Version du contrat

La fiche devrait déclarer une version, par exemple `api_version=1`. PyAges
pourrait alors expliquer clairement qu'un vieux plugin doit être mis à jour.

### Erreurs isolées

Une erreur dans un plugin ne devrait apparaître que lorsqu'on demande ce
plugin. Les modèles internes doivent rester utilisables.

### Confiance

Installer un plugin revient à installer du code Python : ce code peut être
exécuté sur l'ordinateur. Il faut donc installer seulement des paquets dont on
connaît l'origine.

### Reproductibilité

Les résultats devraient mémoriser :

- le nom du modèle ;
- le paquet qui le fournit ;
- la version du paquet ;
- idéalement une empreinte du fichier de paramètres.

Cela permettrait de savoir exactement quelle implémentation a produit un
résultat scientifique.

## 18. Vérifier un modèle externe

Un futur outil pourrait proposer :

```bash
pyages check lpm lognormal
```

Il vérifierait notamment :

1. que le nom annoncé et le nom du modèle correspondent ;
2. que les paramètres Python et YAML sont les mêmes ;
3. que les valeurs initiales respectent les bornes ;
4. que la densité et la fonction de répartition sont finies ;
5. que la fonction de répartition est croissante ;
6. que la distribution est correctement normalisée ;
7. que les moments partiels sont compatibles avec la distribution ;
8. que la stratégie de convolution possède toutes les fonctions nécessaires.

Ce contrôle ne remplacerait pas la validation scientifique du modèle, mais il
détecterait de nombreuses erreurs d'intégration.

## 19. Modifications conceptuelles nécessaires dans PyAges

Sans entrer dans les détails de programmation, PyAges aurait besoin de quatre
évolutions :

1. **Élargir le registre** pour connaître les annonces de paquets externes.
2. **Conserver une fiche complète** comprenant le constructeur et les
   paramètres, au lieu de conserver seulement une classe.
3. **Attacher le schéma de paramètres au modèle** pour que la calibration ne
   dépende plus d'un répertoire central.
4. **Valider le contrat du plugin** au moment où le modèle est construit.

Les fonctions publiques pourraient rester identiques :

```python
list_available_lpms()
build_lpm("nom")
build_random_lpm("nom")
```

C'est un point important : la complexité nécessaire à l'extension resterait
derrière ces fonctions simples.

### Quelle quantité de changements dans PyAges ?

Il faut distinguer un prototype minimal d'une solution durable. Les chiffres
ci-dessous sont des **ordres de grandeur**, pas un devis exact. Ils supposent
que les modèles existants et le moteur de convolution conservent leurs
interfaces actuelles.

#### Option 1 — Prototype explicite

Le prototype introduirait seulement une fonction du genre :

```python
load_lpm_plugin("groundwater_lpms.lognormal")
```

Estimation :

| Partie | Modification estimée |
| --- | ---: |
| Chargement et enregistrement du module | 30 à 50 lignes |
| Messages d'erreur | 10 à 20 lignes |
| Tests | 60 à 100 lignes |
| Total approximatif | 100 à 170 lignes, tests compris |

Ce prototype serait facile à comprendre, mais ne résoudrait pas complètement
la découverte automatique ni le transport propre des paramètres.

#### Option 2 — Plugins automatiques complets

Pour obtenir réellement :

```python
pip install pyages-lpm-lognormal
lpm = build_lpm("lognormal")
```

il faudrait approximativement :

| Partie de PyAges | Rôle | Code de production estimé |
| --- | --- | ---: |
| Nouvelle `LpmDefinition` | Relier classe, paramètres et version | 30 à 50 lignes |
| Registre | Lire les points d'entrée, détecter les doublons, charger à la demande | 50 à 90 lignes |
| Fabrique `build_lpm()` | Choisir les paramètres intégrés, externes ou remplacés | 20 à 40 lignes |
| Paramètres | Attacher le schéma au modèle et adapter ses consommateurs | 50 à 90 lignes |
| Erreurs et informations de provenance | Expliquer la source du modèle | 20 à 40 lignes |
| **Total de production estimé** | | **170 à 310 lignes** |

À cela s'ajouteraient vraisemblablement :

- 200 à 350 lignes de tests ;
- 80 à 150 lignes de documentation et d'exemple ;
- éventuellement une petite commande de validation, à chiffrer séparément.

Ces plages sont volontairement prudentes. Dans le code actuel, le schéma de
paramètres est relu directement par seulement quelques consommateurs
importants, notamment les lois a priori et les pas de proposition
Metropolis–Hastings. La modification resterait donc concentrée autour du
registre, de la fabrique et de la gestion des paramètres.

### Quelles parties resteraient inchangées ?

Le mécanisme ne devrait pas nécessiter de modifier :

- les douze modèles LPM existants, en dehors d'une éventuelle adaptation
  mécanique de leur enregistrement ;
- les formules de convolution continue ;
- les stratégies Dirac et mixtes ;
- l'appel public `build_lpm("nom")` ;
- les fichiers de configuration des études existantes ;
- les boucles de calcul et de calibration.

Le code supplémentaire serait donc localisé. Il n'ajouterait pas une couche à
chaque évaluation de `pdf()`, `cdf()` ou à chaque convolution.

### Quel alourdissement pendant l'exécution ?

Il y aurait trois petits coûts :

1. lire la liste des annonces des paquets installés lors de la première
   consultation du registre ;
2. importer le plugin sélectionné lors de sa première utilisation ;
3. conserver une petite fiche `LpmDefinition` en mémoire.

Une fois le modèle construit, les calculs appelleraient directement ses
méthodes comme aujourd'hui. Il ne devrait donc y avoir **aucun surcoût dans la
boucle de convolution ou de calibration**. Le temps de découverte initial
devrait être mesuré par un test de performance avant de fixer cette affirmation
comme garantie, mais le travail réalisé est petit comparé à une calibration.

Le mécanisme repose sur `importlib.metadata`, déjà inclus dans Python. Il
n'ajouterait donc pas de nouvelle bibliothèque aux dépendances de PyAges.

### Quel alourdissement pour l'auteur du modèle externe ?

Pour un modèle log-normal comme celui de l'exemple :

| Élément externe | Taille typique |
| --- | ---: |
| Formules du modèle | 50 à 80 lignes Python |
| Déclaration `LpmDefinition` | 5 à 8 lignes Python |
| `params.yaml` | 25 à 50 lignes |
| `pyproject.toml` | 15 à 25 lignes |
| Tests scientifiques | 50 à 120 lignes |

Les formules et leurs tests seraient nécessaires même si le modèle était
ajouté directement dans PyAges. Le véritable coût propre au système de plugins
est donc surtout la courte déclaration `LpmDefinition` et quelques lignes dans
`pyproject.toml`.

### Le vrai coût n'est pas la quantité de code

Le principal engagement de maintenance serait de stabiliser le contrat entre
PyAges et les plugins :

- conserver la compatibilité de `LpmDefinition` ;
- produire de bons messages lorsqu'un plugin est trop ancien ;
- empêcher les conflits de noms silencieux ;
- enregistrer la version du plugin dans les résultats scientifiques.

C'est pour cela qu'une version explicite comme `api_version=1` est utile. Le
volume de code resterait modéré, mais cette petite interface deviendrait une
promesse publique à maintenir.

## 20. Proposition finale

Le compromis le plus lisible serait le suivant :

1. Un modèle externe est un petit paquet Python autonome.
2. Le paquet contient le code scientifique et son `params.yaml`.
3. Une ligne de `pyproject.toml` annonce le nom du modèle à PyAges.
4. PyAges charge uniquement le modèle demandé.
5. L'utilisateur continue d'appeler `build_lpm("nom")`.
6. Un répertoire explicitement fourni permet de remplacer les paramètres du
   plugin.
7. Une commande de contrôle vérifie le contrat avant une calibration.

Pour un premier développement, on pourrait commencer par le chargement
explicite `load_lpm_plugin()`, plus facile à comprendre et à tester. La
découverte automatique par paquet installé pourrait être ajoutée ensuite sans
changer `build_lpm()` ni le code scientifique des plugins.

## 21. Résumé très court

```text
Auteur du modèle
    crée un paquet externe avec Python + params.yaml
                    ↓
Le paquet annonce le nom du modèle lors de son installation
                    ↓
PyAges ajoute ce nom à son registre
                    ↓
L'utilisateur appelle build_lpm("nom")
```

Le principe essentiel est donc de séparer :

- **ce qu'est le modèle**, fourni par le paquet externe ;
- **la manière de le trouver**, gérée par le registre ;
- **la manière de l'utiliser**, qui reste la fonction simple `build_lpm()`.
