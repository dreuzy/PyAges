# Audit du sous-package `concentrations`

**Date :** 27 août 2026  
**Périmètre :** `pyages/concentrations`, tests unitaires et documentation de son
contrat public  
**Nature :** refactoring défensif sans modification des résultats numériques
pour les entrées valides existantes

## Synthèse

L'audit a séparé trois responsabilités auparavant entremêlées : le conteneur
d'observations validé, la normalisation/fusion des chroniques et leur
présentation. Les calculs de convolution et de calibration restent hors de ce
périmètre.

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
- validation des modes de tracé, du nombre d'axes, des strides et de la
  cohérence des grilles temporelles entre réalisations ;
- export public concis depuis `pyages.concentrations` et nouveau guide du schéma
  d'observations.

## Rupture pré-1.0

Les noms historiques et imports profonds ont été supprimés sans alias de
compatibilité. L'attribut `cv` devient `frame`, `ConcentrationTime` devient
`ConcentrationChronicle`, et les anciennes méthodes `error_affect_*`,
`names_dates`, `figure_concentrations` et `cv_key_name_date` sont remplacées par
des noms explicites. Les modules `concentrations.py` et
`concentrations_time.py` ne sont pas conservés comme façades.

Le schéma tabulaire et les résultats numériques restent inchangés. Le tirage
gaussien reste non tronqué et peut donc produire une valeur négative ; un autre
modèle d'erreur demanderait une décision scientifique distincte.

## Validation

Résultats finaux dans l'arbre stabilisé après renommage du paquet en `pyages` :

- `python -m pytest -q` : **787 réussis, 5 ignorés** ;
- tests ciblés du sous-package, de son API et de sa documentation :
  **32 réussis** ;
- `python -m ruff check pyages/concentrations tests/concentrations` : réussi ;
- `python -m compileall -q pyages/concentrations` : réussi ;
- construction Sphinx stricte (`-W --keep-going`) : réussie sans avertissement.
