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
