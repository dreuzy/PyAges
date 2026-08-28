# Audit du sous-package `concentrations`

**Date :** 27 août 2026  
**Relance achevée :** 28 août 2026
**Périmètre :** `pyages/concentrations`, tests unitaires et documentation de son
contrat public  
**Nature :** refactoring défensif sans modification des résultats numériques
pour les entrées valides existantes

## Synthèse

L'audit a séparé le conteneur d'observations, les séries, les calculs temporels,
le tracé, la sérialisation et l'orchestration des exports. Les primitives de
convolution et de calibration restent hors de `pyages.concentrations` ; les
workflows sont désormais les seuls à coordonner ces domaines.

Les principaux risques constatés étaient des entrées scientifiques non finies
acceptées jusqu'à un calcul aval, des erreurs négatives possibles, un
constructeur temporel ambigu, des références mutables partagées, des fusions
many-to-many capables de multiplier silencieusement les lignes, et des options
de tracé invalides interprétées comme un autre mode.

## Corrections réalisées

- validation explicite du schéma, des doublons de colonnes, des tables vides,
  des noms de traceurs et des valeurs numériques finies ;
- validation des fractions d'erreur et de la dimension des moyennes, avec
  incertitudes toujours non négatives ;
- exigence d'un `numpy.random.Generator` explicite pour les tirages gaussiens ;
- constructeur `ConcentrationChronicle` exigeant exactement une représentation
  d'entrée et réalisant des copies défensives ;
- normalisation commune des dictionnaires de chroniques, ordre des traceurs
  préservé et dates triées ;
- fusion large validée en `one_to_one`, union déterministe des dates et rejet
  des collisions de noms de colonnes ;
- rejet documenté des répétitions traceur/date uniquement aux frontières qui
  exportent une table large ; elles restent autorisées dans le format long ;
- validation des modes de tracé, du nombre d'axes, des ensembles de traceurs,
  des strides et de la cohérence des grilles temporelles entre réalisations ;
- export public concis depuis `pyages.concentrations` et nouveau guide du schéma
  d'observations.

## Ré-audit de la structure des fichiers

**Verdict :** le découpage est maintenant cohérent avec l'architecture de
`pyages.lpm` : le paquet de données ne dépend plus de la convolution ou des
résultats LPM, et les noms de modules expriment leur responsabilité.

| Responsabilité | Emplacement retenu |
| --- | --- |
| observations validées | `pyages.concentrations._container` |
| schéma tabulaire | `pyages.concentrations.schema` |
| chroniques, normalisation et fusion | `pyages.concentrations.series` |
| prédictions et quantiles temporels | `pyages.concentrations.temporal` |
| rendu sur axes fournis | `pyages.concentrations.plotting` |
| sérialisation TSV | `pyages.data_io.concentrations` |
| sélection LPM, convolution et export | `pyages.reporting.chronicles` |

Le répertoire générique `concentrations/utils` et le module mixte
`concentrations/chronicles.py` ont été supprimés sans alias pré-1.0. Le tracé
par paire est délégué avec un import paresseux : l'import public du conteneur ne
charge plus `matplotlib.pyplot`.

Les deux lacunes de contrat relevées pendant la relance sont corrigées. Le
résumé temporel exige assez d'axes et un ensemble de traceurs identique aux
observations. `normalize_series()` rejette désormais les tables vides, colonnes
dupliquées, valeurs non numériques ou non finies, clés non normalisées et
désaccords entre clé et colonne `element`.

Enfin, les convolutions temporelles sont évaluées une seule fois par
réalisation. Les mêmes tables alimentent les quantiles, les figures et l'export
large, ce qui supprime le double calcul lorsque les figures sont activées.

## Style des commentaires

Les commentaires de `concentrations` suivent désormais la convention employée
dans les parties explicatives de `lpm` : ils documentent une raison, un
invariant ou une frontière de responsabilité. Les intertitres qui répétaient
simplement l'instruction suivante (`Load`, `Save`, `Tracers`, `LPM selection`)
ont été supprimés ou remplacés par l'explication du contrat de reproductibilité,
de la grille temporelle commune, de l'union déterministe des dates ou de
l'indépendance entre affichage et export numérique.

## Rupture pré-1.0

Les noms historiques et imports profonds ont été supprimés sans alias de
compatibilité. L'attribut `cv` devient `frame`, `ConcentrationTime` devient
`ConcentrationChronicle`, et les anciennes méthodes `error_affect_*`,
`names_dates`, `figure_concentrations` et `cv_key_name_date` sont remplacées par
des noms explicites. Les modules `concentrations.py` et
`concentrations_time.py` ne sont pas conservés comme façades. La relance retire
également `concentrations.chronicles`, `concentrations.utils` et la méthode
ambiguë `tracer_names()` ; leurs consommateurs utilisent les modules
sémantiques et les méthodes `observation_tracer_names()` ou
`unique_tracer_names()`.

Le schéma tabulaire reste inchangé. À la suite de la décision scientifique de
ce suivi, le tirage d'erreur suit désormais une vraie loi gaussienne tronquée à
zéro. Les valeurs négatives ne sont ni conservées ni simplement écrêtées : la
masse de probabilité admissible est renormalisée, sans accumulation artificielle
de valeurs exactement nulles. Cette décision modifie volontairement les tirages
numériques reproductibles qui possèdent une erreur strictement positive.

Le calcul des prédictions temporelles est également centralisé : les deux
familles de figures utilisent maintenant les mêmes contrôles de traceurs et de
grilles de dates, puis les mêmes quantiles 10, 25, 50, 75 et 90 %. Les workflows
ne conservent que leurs choix de présentation.

Le contrat d'unités est maintenant évalué aux frontières de l'API. Une unité
explicite et canonique est exigée à la lecture, chaque traceur ne peut avoir
qu'une unité par table, puis l'unité d'observation est comparée exactement à
celle du traceur avant calibration ou tracé temporel. Aucune conversion ou
vérification d'unité n'est exécutée dans les convolutions, objectifs,
optimisations ou boucles d'échantillonnage. Les conversions physiques restent
des opérations de prétraitement explicites.

## Nettoyage de suivi

La recherche finale des noms supprimés a révélé un contrôle `.cv` encore actif
dans le tracé optionnel d'une concentration de référence, ainsi que trois
notebooks qui utilisaient toujours les anciens constructeurs. Le contrôle de
tracé repose désormais sur le contrat canonique `.frame`, couvert par un test
avec un véritable objet `Concentrations`.

Les notebooks Albuquerque, Ploemeur et Ploemeur temporel utilisent maintenant
`Concentrations.from_file()`, `Concentrations.from_dataframe()`, `.frame`,
`observation_tracer_names()` et `observation_keys()`. Les anciens imports
profonds et les anciens mots-clés de `SystematicSampling` ont été supprimés.
Les variables
internes `cv` et `cdata` ont également été renommées. Enfin, le contrôle
d'unités s'appelle `require_matching_units()` afin d'indiquer qu'il exige une
égalité exacte et ne réalise aucune conversion ; aucun alias de l'ancien nom
n'est conservé.

## Validation initiale

Résultats finaux dans l'arbre stabilisé après renommage du paquet en `pyages` :

- `python -m pytest -q` : **943 réussis, 5 ignorés** ;
- tests ciblés du sous-package, de son API et de sa documentation :
  **49 réussis** pour les contrats de concentration, d'unités, de tracé et de
  documentation, complétés par **221 réussis** pour les workflows, la
  convolution et l'API publique ;
- les trois notebooks modifiés sont des documents JSON valides, leurs cellules
  Python compilent et leurs jeux de données se chargent avec l'API canonique ;
- `python -m ruff check .` : réussi ;
- `python -m compileall -q pyages` : réussi ;
- construction Sphinx stricte (`-W --keep-going`) : réussie sans avertissement.

## Validation de la relance

La relance a été exécutée dans un arbre de travail contenant d'autres
refactorings non stabilisés :

- contrats ciblés de concentration et non-régression associée : **60 réussis** ;
- consommateurs `tests/concentrations`, `tests/convolution` et
  `tests/workflows` : **295 réussis** ;
- suite globale : **1 012 réussis, 5 ignorés** ;
- couverture ciblée du nouveau périmètre concentration, sérialisation et export :
  **81 %** au total, dont **91 %** pour le conteneur et les résumés temporels ;
- `python -m ruff check .` : réussi ;
- `python -m ruff format --check` sur les fichiers Python concernés : réussi ;
- `python -m compileall -q pyages` : réussi ;
- `git diff --check` sur le périmètre modifié : réussi ;
- construction Sphinx HTML stricte (`-E -a -W --keep-going`) : réussie sans
  avertissement ;
- les trois notebooks naturels sont des documents JSON valides et leurs cellules
  transformées par IPython compilent.
